import uuid
import datetime
import json
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from db.database import get_db
from db.models import RiskLimit, CircuitBreaker, Position, StressRun, Recommendation
from services.api.schemas import StressRunRequest, EmergencyStopRequest, ModeSwitchRequest
from services.api.auth import get_current_user, record_audit
from packages.risk.engine import RiskEngine
from services.simulator.engine import PaperTradingSimulator

router = APIRouter(tags=["Risk & Controls"])
risk_engine = RiskEngine()
simulator = PaperTradingSimulator()

CURRENT_OPERATING_MODE = "recommendation"

@router.get("/portfolio/risk")
def get_portfolio_risk(request: Request, db: Session = Depends(get_db)):
    positions_db = db.query(Position).all()
    positions = [
        {
            "strike": p.instrument.strike if p.instrument else 65000.0,
            "expiry_years": 30/365,
            "option_type": p.instrument.option_type if p.instrument else "call",
            "quantity": p.quantity,
            "implied_vol": 0.55,
            "mark_price": p.current_mark_price,
            "delta": p.delta,
            "gamma": p.gamma,
            "vega": p.vega,
            "theta": p.theta,
            "margin": abs(p.quantity) * p.current_mark_price,
            "unrealized_pnl": p.unrealized_pnl
        }
        for p in positions_db
    ]

    limits = {rl.limit_name: rl.limit_value for rl in db.query(RiskLimit).filter_by(is_active=True).all()}
    summary = risk_engine.calculate_portfolio_risk(
        positions=positions,
        spot=65000.0,
        total_capital=500000.0,
        limits=limits
    )

    breakers = [
        {
            "name": cb.name,
            "is_tripped": cb.is_tripped,
            "tripped_at": cb.tripped_at.isoformat() if cb.tripped_at else None,
            "reason": cb.reason
        }
        for cb in db.query(CircuitBreaker).all()
    ]
    summary["circuit_breakers"] = breakers
    summary["operating_mode"] = CURRENT_OPERATING_MODE

    return {
        "request_id": getattr(request.state, "request_id", "req_unknown"),
        "data": summary
    }

@router.post("/portfolio/rebalance")
def rebalance_portfolio(
    underlying: str = "BTC",
    request: Request = None,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    rebalance_res = simulator.rebalance_portfolio_delta(underlying=underlying.upper(), db_session=db)
    if not rebalance_res:
        return {
            "request_id": getattr(request.state, "request_id", "req_unknown") if request else "req_unknown",
            "data": {
                "status": "within_tolerance",
                "message": f"Portfolio delta for {underlying.upper()} is within hedging threshold (±0.50). No rebalance required."
            }
        }

    record_audit(
        db,
        actor_id=current_user.id if current_user else "user_dev_01",
        action="rebalance_portfolio_delta",
        object_type="portfolio",
        object_id=f"rebalance_{underlying.lower()}",
        request_id=getattr(request.state, "request_id", None) if request else None,
        after_state=rebalance_res
    )

    return {
        "request_id": getattr(request.state, "request_id", "req_unknown") if request else "req_unknown",
        "data": {
            "status": "rebalanced",
            "message": f"Successfully hedged delta drift for {underlying.upper()}.",
            "details": rebalance_res
        }
    }

@router.post("/risk/stress-runs")
def run_stress_test(
    body: StressRunRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    positions = []
    if body.target_type == "portfolio":
        positions_db = db.query(Position).all()
        positions = [
            {
                "strike": p.instrument.strike if p.instrument else 65000.0,
                "expiry_years": 30/365,
                "option_type": p.instrument.option_type if p.instrument else "call",
                "quantity": p.quantity,
                "implied_vol": 0.55,
                "mark_price": p.current_mark_price
            }
            for p in positions_db
        ]
    elif body.target_type == "recommendation" and body.target_id:
        r = db.query(Recommendation).filter_by(id=body.target_id).first()
        if r:
            legs = json.loads(r.legs_json)
            for leg in legs:
                qty = leg.get("quantity", 1.0) * (1.0 if leg.get("direction", "buy") == "buy" else -1.0)
                positions.append({
                    "strike": leg.get("strike", 65000.0),
                    "expiry_years": leg.get("expiry_years", 30/365),
                    "option_type": leg.get("option_type", "call"),
                    "quantity": qty,
                    "implied_vol": r.implied_volatility,
                    "mark_price": leg.get("order_price", 2000.0)
                })

    res = risk_engine.stress_engine.evaluate_portfolio(positions, spot=65000.0)
    run_id = f"stress_{uuid.uuid4().hex[:10]}"

    db_run = StressRun(
        id=run_id,
        target_type=body.target_type,
        target_id=body.target_id,
        base_portfolio_value=500000.0,
        spot_shocks_json=json.dumps(res["spot_shocks"]),
        vol_shocks_json=json.dumps(res["vol_shocks"]),
        scenario_results_json=json.dumps(res["scenario_grid"]),
        max_loss=res["max_loss"],
        margin_impact=res["max_loss"] * 0.15
    )
    db.add(db_run)
    db.commit()

    return {
        "request_id": getattr(request.state, "request_id", "req_unknown"),
        "data": {
            "stress_run_id": run_id,
            "target_type": body.target_type,
            "target_id": body.target_id,
            "results": res
        }
    }

@router.post("/controls/emergency-stop")
def trigger_emergency_stop(
    body: EmergencyStopRequest,
    request: Request,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    cb = db.query(CircuitBreaker).filter_by(name="emergency_stop").first()
    now = datetime.datetime.now(datetime.timezone.utc)
    if not cb:
        cb = CircuitBreaker(id="cb_emergency_stop", name="emergency_stop", trigger_condition="manual")
        db.add(cb)

    cb.is_tripped = True
    cb.tripped_at = now
    cb.reason = body.reason
    db.commit()

    record_audit(
        db,
        actor_id=current_user.id if current_user else "user_dev_01",
        action="emergency_stop_tripped",
        object_type="circuit_breaker",
        object_id=cb.id,
        request_id=getattr(request.state, "request_id", None),
        after_state={"is_tripped": True, "reason": body.reason}
    )

    return {
        "request_id": getattr(request.state, "request_id", "req_unknown"),
        "data": {
            "status": "emergency_stop_active",
            "message": "All new risk submission disabled immediately.",
            "tripped_at": now.isoformat()
        }
    }

@router.post("/controls/emergency-stop/reset")
def reset_emergency_stop(
    request: Request,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    cb = db.query(CircuitBreaker).filter_by(name="emergency_stop").first()
    if cb:
        cb.is_tripped = False
        cb.reset_at = datetime.datetime.now(datetime.timezone.utc)
        cb.reason = None
        db.commit()

        record_audit(
            db,
            actor_id=current_user.id if current_user else "user_dev_01",
            action="emergency_stop_reset",
            object_type="circuit_breaker",
            object_id=cb.id,
            request_id=getattr(request.state, "request_id", None),
            after_state={"is_tripped": False}
        )

    return {
        "request_id": getattr(request.state, "request_id", "req_unknown"),
        "data": {"status": "normal", "message": "Emergency stop has been reset."}
    }

@router.get("/controls/mode")
def get_operating_mode(request: Request):
    return {
        "request_id": getattr(request.state, "request_id", "req_unknown"),
        "data": {
            "operating_mode": CURRENT_OPERATING_MODE,
            "live_trading_enabled": False,
            "description": "System is in Human-in-the-Loop Recommendation Mode. Live order submission is strictly disabled."
        }
    }

@router.post("/controls/mode")
def switch_operating_mode(
    body: ModeSwitchRequest,
    request: Request,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    global CURRENT_OPERATING_MODE
    allowed_modes = ["analytics", "recommendation", "assisted", "bounded_automation"]
    if body.mode not in allowed_modes:
        raise HTTPException(status_code=400, detail=f"Mode '{body.mode}' is invalid. Allowed: {allowed_modes}")

    prev = CURRENT_OPERATING_MODE
    CURRENT_OPERATING_MODE = body.mode

    record_audit(
        db,
        actor_id=current_user.id if current_user else "user_dev_01",
        action="switch_operating_mode",
        object_type="system_controls",
        request_id=getattr(request.state, "request_id", None),
        before_state={"mode": prev},
        after_state={"mode": body.mode, "reason": body.reason}
    )

    return {
        "request_id": getattr(request.state, "request_id", "req_unknown"),
        "data": {
            "operating_mode": CURRENT_OPERATING_MODE,
            "live_trading_enabled": False,
            "message": f"Operating mode switched to '{body.mode}'."
        }
    }
