import json
from typing import Optional
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session
from db.database import get_db
from db.models import PnLAttribution, AuditEvent
from services.replay.engine import ReplayEngine

router = APIRouter(tags=["Reports & Audit"])
replay_engine = ReplayEngine()

@router.get("/reports/pnl")
def get_pnl_report(request: Request, db: Session = Depends(get_db)):
    records = db.query(PnLAttribution).order_by(PnLAttribution.timestamp.desc()).limit(100).all()
    if not records:
        # Provide clean zero-baseline if no orders executed yet
        return {
            "request_id": getattr(request.state, "request_id", "req_unknown"),
            "data": {
                "total_pnl": 0.0,
                "delta_pnl": 0.0,
                "gamma_pnl": 0.0,
                "vega_pnl": 0.0,
                "theta_pnl": 0.0,
                "fee_pnl": 0.0,
                "slippage_pnl": 0.0,
                "hedge_pnl": 0.0,
                "residual_pnl": 0.0,
                "history": []
            }
        }

    latest = records[0]
    total_delta = sum(r.delta_pnl for r in records)
    total_gamma = sum(r.gamma_pnl for r in records)
    total_vega = sum(r.vega_pnl for r in records)
    total_theta = sum(r.theta_pnl for r in records)
    total_fee = sum(r.fee_pnl for r in records)
    total_slippage = sum(r.slippage_pnl for r in records)
    total_hedge = sum(r.hedge_pnl for r in records)
    total_residual = sum(r.residual_pnl for r in records)
    net_total = sum(r.total_pnl for r in records)

    history = [
        {
            "timestamp": r.timestamp.isoformat() if r.timestamp else "",
            "total_pnl": round(r.total_pnl, 2),
            "delta_pnl": round(r.delta_pnl, 2),
            "gamma_pnl": round(r.gamma_pnl, 2),
            "vega_pnl": round(r.vega_pnl, 2),
            "theta_pnl": round(r.theta_pnl, 2),
            "fee_pnl": round(r.fee_pnl, 2),
            "slippage_pnl": round(r.slippage_pnl, 2),
            "hedge_pnl": round(r.hedge_pnl, 2)
        }
        for r in reversed(records[:30])
    ]

    return {
        "request_id": getattr(request.state, "request_id", "req_unknown"),
        "data": {
            "total_pnl": round(net_total, 2),
            "delta_pnl": round(total_delta, 2),
            "gamma_pnl": round(total_gamma, 2),
            "vega_pnl": round(total_vega, 2),
            "theta_pnl": round(total_theta, 2),
            "fee_pnl": round(total_fee, 2),
            "slippage_pnl": round(total_slippage, 2),
            "hedge_pnl": round(total_hedge, 2),
            "residual_pnl": round(total_residual, 2),
            "history": history
        }
    }

@router.get("/audit/events")
def list_audit_events(
    request: Request,
    action: Optional[str] = Query(None),
    object_type: Optional[str] = Query(None),
    limit: int = Query(50),
    db: Session = Depends(get_db)
):
    query = db.query(AuditEvent)
    if action:
        query = query.filter(AuditEvent.action == action)
    if object_type:
        query = query.filter(AuditEvent.object_type == object_type)

    events = query.order_by(AuditEvent.timestamp.desc()).limit(limit).all()
    res = [
        {
            "id": e.id,
            "actor_id": e.actor_id,
            "action": e.action,
            "object_type": e.object_type,
            "object_id": e.object_id,
            "timestamp": e.timestamp.isoformat() if e.timestamp else "",
            "request_id": e.request_id,
            "before_state": json.loads(e.before_state_json) if e.before_state_json else None,
            "after_state": json.loads(e.after_state_json) if e.after_state_json else None,
            "details": json.loads(e.details_json) if e.details_json else None
        }
        for e in events
    ]
    return {
        "request_id": getattr(request.state, "request_id", "req_unknown"),
        "data": res
    }

@router.post("/replay/tick")
def replay_tick(
    request: Request,
    batch_size: int = Query(10),
    db: Session = Depends(get_db)
):
    """Replays deterministic synthetic market events into the platform."""
    replayed = []
    for _ in range(batch_size):
        ev = replay_engine.replay_tick_to_db(db_session=db)
        if ev:
            replayed.append(ev["instrument_name"])
        else:
            replay_engine.reset()

    return {
        "request_id": getattr(request.state, "request_id", "req_unknown"),
        "data": {
            "replayed_count": len(replayed),
            "instruments_updated": list(set(replayed))
        }
    }
