import uuid
import datetime
import json
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from db.database import get_db
from db.models import (
    Recommendation, RecommendationEdit, Approval, Instrument,
    QuoteSnapshot, PaperOrder, CircuitBreaker, RiskLimit, Position
)
from services.api.schemas import (
    RecommendationApproveRequest, RecommendationRejectRequest,
    RecommendationEditRequest
)
from services.api.auth import get_current_user, record_audit
from packages.quant.opportunity import OpportunityCalculator
from packages.quant.black_scholes import bs_greeks
from packages.risk.engine import RiskEngine
from services.simulator.engine import PaperTradingSimulator

router = APIRouter(tags=["Recommendations"])
opp_calc = OpportunityCalculator()
risk_engine = RiskEngine()
simulator = PaperTradingSimulator()

@router.get("/recommendations")
def get_recommendations(
    request: Request,
    status: Optional[str] = Query(None),
    underlying: Optional[str] = Query(None),
    min_edge: Optional[float] = Query(None),
    watchlist_only: Optional[bool] = Query(None),
    db: Session = Depends(get_db)
):
    query = db.query(Recommendation)
    if status:
        query = query.filter(Recommendation.status == status)
    if underlying:
        query = query.filter(Recommendation.underlying == underlying)
    if min_edge is not None:
        query = query.filter(Recommendation.net_edge >= min_edge)
    if watchlist_only:
        query = query.filter(Recommendation.is_watchlist == True)

    recs = query.order_by(Recommendation.net_edge.desc()).all()
    res = []
    for r in recs:
        res.append({
            "id": r.id,
            "underlying": r.underlying,
            "strategy_type": r.strategy_type,
            "legs": json.loads(r.legs_json),
            "implied_volatility": r.implied_volatility,
            "forecast_volatility": r.forecast_volatility,
            "gross_edge": r.gross_edge,
            "net_edge": r.net_edge,
            "costs": {
                "spread": r.spread_cost,
                "fee": r.fee_cost,
                "slippage": r.slippage_cost,
                "hedge": r.hedge_cost,
                "carry": r.carry_cost,
                "uncertainty_penalty": r.uncertainty_penalty
            },
            "greeks": {
                "delta": r.delta,
                "gamma": r.gamma,
                "vega": r.vega,
                "theta": r.theta
            },
            "initial_margin": r.initial_margin,
            "stress_max_loss": r.stress_max_loss,
            "confidence": r.confidence,
            "rationale": r.rationale,
            "status": r.status,
            "is_watchlist": bool(r.is_watchlist),
            "expiry_at": r.expiry_at.isoformat() if r.expiry_at else "",
            "created_at": r.created_at.isoformat() if r.created_at else ""
        })

    return {
        "request_id": getattr(request.state, "request_id", "req_unknown"),
        "data": res
    }

@router.get("/recommendations/{rec_id}")
def get_recommendation_by_id(
    rec_id: str,
    request: Request,
    db: Session = Depends(get_db)
):
    r = db.query(Recommendation).filter_by(id=rec_id).first()
    if not r:
        raise HTTPException(status_code=404, detail=f"Recommendation {rec_id} not found")

    return {
        "request_id": getattr(request.state, "request_id", "req_unknown"),
        "data": {
            "id": r.id,
            "underlying": r.underlying,
            "strategy_type": r.strategy_type,
            "legs": json.loads(r.legs_json),
            "implied_volatility": r.implied_volatility,
            "forecast_volatility": r.forecast_volatility,
            "gross_edge": r.gross_edge,
            "net_edge": r.net_edge,
            "costs": {
                "spread": r.spread_cost,
                "fee": r.fee_cost,
                "slippage": r.slippage_cost,
                "hedge": r.hedge_cost,
                "carry": r.carry_cost,
                "uncertainty_penalty": r.uncertainty_penalty
            },
            "greeks": {
                "delta": r.delta,
                "gamma": r.gamma,
                "vega": r.vega,
                "theta": r.theta
            },
            "initial_margin": r.initial_margin,
            "stress_max_loss": r.stress_max_loss,
            "confidence": r.confidence,
            "rationale": r.rationale,
            "status": r.status,
            "is_watchlist": bool(r.is_watchlist),
            "expiry_at": r.expiry_at.isoformat() if r.expiry_at else "",
            "created_at": r.created_at.isoformat() if r.created_at else ""
        }
    }

@router.post("/recommendations/{rec_id}/approve")
def approve_recommendation(
    rec_id: str,
    body: RecommendationApproveRequest,
    request: Request,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    r = db.query(Recommendation).filter_by(id=rec_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Recommendation not found")

    if r.status != "pending":
        raise HTTPException(status_code=409, detail=f"Recommendation cannot be approved from status '{r.status}'")

    # Independent Risk Check before approval!
    breakers = [
        {"name": cb.name, "is_tripped": cb.is_tripped, "reason": cb.reason}
        for cb in db.query(CircuitBreaker).all()
    ]
    limits = {rl.limit_name: rl.limit_value for rl in db.query(RiskLimit).filter_by(is_active=True).all()}

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
            "margin": abs(p.quantity) * p.current_mark_price
        }
        for p in db.query(Position).all()
    ]

    portfolio_state = {
        "total_capital": 500000.0,
        "used_margin": sum(p["margin"] for p in positions),
        "delta": sum(p["delta"] for p in positions),
        "gamma": sum(p["gamma"] for p in positions),
        "vega": sum(p["vega"] for p in positions),
        "theta": sum(p["theta"] for p in positions),
        "positions": positions
    }

    legs = json.loads(r.legs_json)
    primary_leg = legs[0] if legs else {}
    qty = body.quantity_override if body.quantity_override else primary_leg.get("quantity", 1.0)
    qty_scale = (body.quantity_override / primary_leg.get("quantity", 1.0)) if (body.quantity_override and primary_leg.get("quantity")) else 1.0
    spot_ref = 65000.0 if r.underlying == "BTC" else 3500.0

    proposed_trade = {
        "strike": primary_leg.get("strike", spot_ref),
        "expiry_years": primary_leg.get("expiry_years", 30/365),
        "option_type": primary_leg.get("option_type", "call"),
        "direction": primary_leg.get("direction", "buy"),
        "quantity": qty,
        "order_price": body.price_limit_override or primary_leg.get("order_price", 2000.0),
        "initial_margin": r.initial_margin * qty_scale,
        "delta": r.delta * qty_scale,
        "gamma": r.gamma * qty_scale,
        "vega": r.vega * qty_scale,
        "theta": r.theta * qty_scale,
        "implied_volatility": r.implied_volatility
    }

    market_health = {"quote_age_seconds": 2.0, "is_connected": True, "sequence_gap_detected": False, "spot_price": spot_ref}

    risk_result = risk_engine.evaluate_proposed_action(
        portfolio_state, proposed_trade, limits, breakers, market_health
    )

    if not risk_result.is_approved:
        raise HTTPException(
            status_code=422,
            detail={"message": "Independent risk check rejected approval", "violations": risk_result.rejections}
        )

    # Record Approval
    appr_id = f"appr_{uuid.uuid4().hex[:10]}"
    appr = Approval(
        id=appr_id,
        recommendation_id=r.id,
        user_id=current_user.id if current_user else "user_dev_01",
        decision="approved",
        mode="paper",
        quantity_override=body.quantity_override,
        price_limit_override=body.price_limit_override,
        hedge_permission=body.hedge_permission,
        reason_comment=body.comment
    )
    db.add(appr)
    r.status = "approved"

    # Create Paper Orders for all legs
    created_orders = []
    mandate_id = f"mandate_{r.underlying.lower()}_vol_01"

    for leg in legs:
        leg_qty = (leg.get("quantity", 1.0) or 1.0) * qty_scale
        inst_id = leg.get("instrument_id")
        if not inst_id:
            inst = db.query(Instrument).filter_by(
                underlying=r.underlying,
                strike=leg.get("strike", spot_ref),
                option_type=leg.get("option_type", "call")
            ).first()
            inst_id = inst.id if inst else "inst_default"

        order_id = f"order_{uuid.uuid4().hex[:10]}"
        leg_px_limit = body.price_limit_override if len(legs) == 1 else None
        paper_order = PaperOrder(
            id=order_id,
            recommendation_id=r.id,
            mandate_id=mandate_id,
            instrument_id=inst_id,
            direction=leg.get("direction", "buy"),
            order_type="limit" if leg_px_limit else "market",
            quantity=leg_qty,
            price_limit=leg_px_limit,
            status="pending"
        )
        db.add(paper_order)
        created_orders.append(paper_order)

    db.commit()

    # Execute paper orders through simulator (atomic multi-leg if >1 leg)
    order_ids = [o.id for o in created_orders]
    if len(order_ids) > 1:
        sim_result = simulator.execute_multi_leg_order(order_ids, db_session=db)
    else:
        sim_result = simulator.execute_order(order_ids[0], db_session=db)

    record_audit(
        db,
        actor_id=current_user.id if current_user else "user_dev_01",
        action="approve_recommendation",
        object_type="recommendation",
        object_id=r.id,
        request_id=getattr(request.state, "request_id", None),
        before_state={"status": "pending"},
        after_state={"status": "approved", "paper_order_ids": order_ids, "fill": sim_result}
    )

    return {
        "request_id": getattr(request.state, "request_id", "req_unknown"),
        "data": {
            "approval_id": appr_id,
            "status": "approved",
            "paper_order_id": order_ids[0],
            "paper_order_ids": order_ids,
            "execution": sim_result,
            "risk_check": {
                "approved": True,
                "warnings": risk_result.warnings,
                "post_trade_greeks": risk_result.post_trade_greeks
            }
        }
    }

@router.post("/recommendations/{rec_id}/reject")
def reject_recommendation(
    rec_id: str,
    body: RecommendationRejectRequest,
    request: Request,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    r = db.query(Recommendation).filter_by(id=rec_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Recommendation not found")

    appr = Approval(
        id=f"appr_{uuid.uuid4().hex[:10]}",
        recommendation_id=r.id,
        user_id=current_user.id if current_user else "user_dev_01",
        decision="rejected",
        mode="paper",
        reason_comment=body.reason
    )
    db.add(appr)
    r.status = "rejected"
    db.commit()

    record_audit(
        db,
        actor_id=current_user.id if current_user else "user_dev_01",
        action="reject_recommendation",
        object_type="recommendation",
        object_id=r.id,
        request_id=getattr(request.state, "request_id", None),
        before_state={"status": "pending"},
        after_state={"status": "rejected", "reason": body.reason}
    )

    return {
        "request_id": getattr(request.state, "request_id", "req_unknown"),
        "data": {"status": "rejected", "reason": body.reason}
    }

@router.post("/recommendations/{rec_id}/watchlist")
def toggle_watchlist(
    rec_id: str,
    request: Request,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    r = db.query(Recommendation).filter_by(id=rec_id).first()
    if not r:
        raise HTTPException(status_code=404, detail=f"Recommendation {rec_id} not found")

    r.is_watchlist = not bool(r.is_watchlist)
    db.commit()

    record_audit(
        db,
        actor_id=current_user.id if current_user else "user_dev_01",
        action="toggle_watchlist",
        object_type="recommendation",
        object_id=r.id,
        request_id=getattr(request.state, "request_id", None),
        after_state={"is_watchlist": r.is_watchlist}
    )

    return {
        "request_id": getattr(request.state, "request_id", "req_unknown"),
        "data": {"id": r.id, "is_watchlist": r.is_watchlist}
    }

@router.post("/recommendations/{rec_id}/edit")
def edit_recommendation(
    rec_id: str,
    body: RecommendationEditRequest,
    request: Request,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    r = db.query(Recommendation).filter_by(id=rec_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Recommendation not found")

    legs = json.loads(r.legs_json)
    original_legs = list(legs)
    qty_ratio = body.quantity / (legs[0].get("quantity", 1.0) or 1.0)

    legs[0]["quantity"] = body.quantity
    if body.price_limit:
        legs[0]["order_price"] = body.price_limit

    # Recalculate Greeks, margin, stress loss, net edge
    recalc_delta = round(r.delta * qty_ratio, 4)
    recalc_gamma = round(r.gamma * qty_ratio, 6)
    recalc_vega = round(r.vega * qty_ratio, 2)
    recalc_theta = round(r.theta * qty_ratio, 2)
    recalc_margin = round(r.initial_margin * qty_ratio, 2)
    recalc_stress = round(r.stress_max_loss * qty_ratio, 2)

    # Slippage increases slightly with quantity
    slippage_bump = 0.0002 * (1.0 + 0.1 * body.quantity)
    new_net_edge = round(max(0.001, r.gross_edge - (r.spread_cost + r.fee_cost + slippage_bump + r.hedge_cost + r.carry_cost + r.uncertainty_penalty)), 4)

    edit_rec = RecommendationEdit(
        id=f"edit_{uuid.uuid4().hex[:10]}",
        recommendation_id=r.id,
        user_id=current_user.id if current_user else "user_dev_01",
        original_parameters_json=json.dumps({"legs": original_legs, "net_edge": r.net_edge}),
        edited_parameters_json=json.dumps({"quantity": body.quantity, "price_limit": body.price_limit}),
        recalculated_metrics_json=json.dumps({
            "delta": recalc_delta,
            "gamma": recalc_gamma,
            "vega": recalc_vega,
            "theta": recalc_theta,
            "initial_margin": recalc_margin,
            "stress_max_loss": recalc_stress,
            "net_edge": new_net_edge
        }),
        edit_reason=body.edit_reason
    )
    db.add(edit_rec)

    r.legs_json = json.dumps(legs)
    r.delta = recalc_delta
    r.gamma = recalc_gamma
    r.vega = recalc_vega
    r.theta = recalc_theta
    r.initial_margin = recalc_margin
    r.stress_max_loss = recalc_stress
    r.net_edge = new_net_edge
    db.commit()

    return {
        "request_id": getattr(request.state, "request_id", "req_unknown"),
        "data": {
            "recommendation_id": r.id,
            "net_edge": new_net_edge,
            "greeks": {"delta": recalc_delta, "gamma": recalc_gamma, "vega": recalc_vega, "theta": recalc_theta},
            "initial_margin": recalc_margin,
            "stress_max_loss": recalc_stress
        }
    }

@router.post("/recommendations/generate")
def trigger_generation(
    request: Request,
    underlying: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Runs opportunity discovery across available instruments and quotes (single-leg, straddles, calendar spreads)."""
    now = datetime.datetime.now(datetime.timezone.utc)
    underlyings = [underlying.upper()] if underlying else ["BTC", "ETH"]
    created_recs = []

    for und in underlyings:
        instruments = db.query(Instrument).filter_by(underlying=und, is_active=True).all()
        if not instruments:
            continue

        inst_map = {}
        quotes_by_inst = {}
        for inst in instruments:
            inst_map[inst.id] = inst
            quote = (
                db.query(QuoteSnapshot)
                .filter_by(instrument_id=inst.id)
                .order_by(QuoteSnapshot.timestamp.desc())
                .first()
            )
            if quote and quote.best_bid_price and quote.best_ask_price:
                quotes_by_inst[inst.id] = quote

        # 1. Single-Leg Opportunities
        for inst_id, quote in quotes_by_inst.items():
            inst = inst_map[inst_id]
            exp = inst.expiry
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=datetime.timezone.utc)
            T = max(0.005, (exp - now).total_seconds() / (365.25 * 86400.0))

            spot = quote.underlying_price or (65000.0 if und == "BTC" else 3500.0)
            iv = quote.implied_volatility or 0.55
            forecast_vol = iv + 0.08  # Divergence for opportunity generation

            opp = opp_calc.evaluate_opportunity(
                underlying=und,
                spot=spot,
                strike=inst.strike,
                expiry_years=T,
                option_type=inst.option_type,
                best_bid=quote.best_bid_price,
                best_ask=quote.best_ask_price,
                implied_vol=iv,
                forecast_vol=forecast_vol,
                uncertainty=0.04,
                surface_confidence=0.95,
                surface_status="valid",
                quantity=1.0
            )

            if opp:
                rec_id = f"rec_{uuid.uuid4().hex[:10]}"
                leg = {
                    "instrument_id": inst.id,
                    "symbol": inst.symbol,
                    "direction": opp["direction"],
                    "option_type": opp["option_type"],
                    "strike": opp["strike"],
                    "expiry_years": opp["expiry_years"],
                    "order_price": opp["order_price"],
                    "quantity": opp["quantity"]
                }
                rec = Recommendation(
                    id=rec_id,
                    underlying=und,
                    strategy_type=opp["strategy_type"],
                    legs_json=json.dumps([leg]),
                    implied_volatility=opp["implied_volatility"],
                    forecast_volatility=opp["forecast_volatility"],
                    gross_edge=opp["gross_edge"],
                    net_edge=opp["net_edge"],
                    spread_cost=opp["spread_cost"],
                    fee_cost=opp["fee_cost"],
                    slippage_cost=opp["slippage_cost"],
                    hedge_cost=opp["hedge_cost"],
                    carry_cost=opp["carry_cost"],
                    uncertainty_penalty=opp["uncertainty_penalty"],
                    delta=opp["delta"],
                    gamma=opp["gamma"],
                    vega=opp["vega"],
                    theta=opp["theta"],
                    initial_margin=opp["initial_margin"],
                    stress_max_loss=opp["stress_max_loss"],
                    confidence=opp["confidence"],
                    rationale=opp["rationale"],
                    expiry_at=datetime.datetime.fromisoformat(opp["expiry_at"]),
                    status="pending",
                    is_watchlist=False
                )
                db.add(rec)
                created_recs.append(rec_id)

        # 2. Multi-Leg Straddle Evaluation (ATM strike at 30d tenor)
        spot_ref = 65000.0 if und == "BTC" else 3500.0
        strikes = sorted(list(set(inst.strike for inst in instruments)))
        if strikes:
            atm_strike = min(strikes, key=lambda k: abs(k - spot_ref))
            call_inst = next((i for i in instruments if i.strike == atm_strike and i.option_type == "call" and i.id in quotes_by_inst), None)
            put_inst = next((i for i in instruments if i.strike == atm_strike and i.option_type == "put" and i.id in quotes_by_inst), None)
            if call_inst and put_inst:
                c_q = quotes_by_inst[call_inst.id]
                p_q = quotes_by_inst[put_inst.id]
                exp = call_inst.expiry
                if exp.tzinfo is None:
                    exp = exp.replace(tzinfo=datetime.timezone.utc)
                T = max(0.005, (exp - now).total_seconds() / (365.25 * 86400.0))
                c_dict = {
                    "instrument_id": call_inst.id,
                    "symbol": call_inst.symbol,
                    "best_bid_price": c_q.best_bid_price,
                    "best_ask_price": c_q.best_ask_price,
                    "implied_vol": c_q.implied_volatility or 0.55
                }
                p_dict = {
                    "instrument_id": put_inst.id,
                    "symbol": put_inst.symbol,
                    "best_bid_price": p_q.best_bid_price,
                    "best_ask_price": p_q.best_ask_price,
                    "implied_vol": p_q.implied_volatility or 0.55
                }
                avg_iv = (c_dict["implied_vol"] + p_dict["implied_vol"]) / 2.0
                straddle_opp = opp_calc.evaluate_straddle(
                    underlying=und,
                    spot=c_q.underlying_price or spot_ref,
                    strike=atm_strike,
                    expiry_years=T,
                    call_quote=c_dict,
                    put_quote=p_dict,
                    forecast_vol=avg_iv + 0.10,
                    uncertainty=0.03,
                    quantity=1.0
                )
                if straddle_opp:
                    rec_id = f"rec_{uuid.uuid4().hex[:10]}"
                    rec = Recommendation(
                        id=rec_id,
                        underlying=und,
                        strategy_type=straddle_opp["strategy_type"],
                        legs_json=json.dumps(straddle_opp["legs"]),
                        implied_volatility=straddle_opp["implied_volatility"],
                        forecast_volatility=straddle_opp["forecast_volatility"],
                        gross_edge=straddle_opp["gross_edge"],
                        net_edge=straddle_opp["net_edge"],
                        spread_cost=straddle_opp["spread_cost"],
                        fee_cost=straddle_opp["fee_cost"],
                        slippage_cost=straddle_opp["slippage_cost"],
                        hedge_cost=straddle_opp["hedge_cost"],
                        carry_cost=straddle_opp["carry_cost"],
                        uncertainty_penalty=straddle_opp["uncertainty_penalty"],
                        delta=straddle_opp["delta"],
                        gamma=straddle_opp["gamma"],
                        vega=straddle_opp["vega"],
                        theta=straddle_opp["theta"],
                        initial_margin=straddle_opp["initial_margin"],
                        stress_max_loss=straddle_opp["stress_max_loss"],
                        confidence=straddle_opp["confidence"],
                        rationale=straddle_opp["rationale"],
                        expiry_at=datetime.datetime.fromisoformat(straddle_opp["expiry_at"]),
                        status="pending",
                        is_watchlist=False
                    )
                    db.add(rec)
                    created_recs.append(rec_id)

        # 3. Multi-Leg Calendar Spread Evaluation (near vs far tenor call at ATM strike)
        if strikes:
            atm_strike = min(strikes, key=lambda k: abs(k - spot_ref))
            calls_atm = [i for i in instruments if i.strike == atm_strike and i.option_type == "call" and i.id in quotes_by_inst]
            calls_atm.sort(key=lambda i: i.expiry)
            if len(calls_atm) >= 2:
                near_inst = calls_atm[0]
                far_inst = calls_atm[1]
                near_q = quotes_by_inst[near_inst.id]
                far_q = quotes_by_inst[far_inst.id]

                exp_n = near_inst.expiry if near_inst.expiry.tzinfo else near_inst.expiry.replace(tzinfo=datetime.timezone.utc)
                exp_f = far_inst.expiry if far_inst.expiry.tzinfo else far_inst.expiry.replace(tzinfo=datetime.timezone.utc)

                T_n = max(0.005, (exp_n - now).total_seconds() / (365.25 * 86400.0))
                T_f = max(0.010, (exp_f - now).total_seconds() / (365.25 * 86400.0))

                near_dict = {
                    "instrument_id": near_inst.id,
                    "symbol": near_inst.symbol,
                    "best_bid_price": near_q.best_bid_price,
                    "best_ask_price": near_q.best_ask_price,
                    "T": T_n,
                    "implied_vol": (near_q.implied_volatility or 0.55) + 0.06
                }
                far_dict = {
                    "instrument_id": far_inst.id,
                    "symbol": far_inst.symbol,
                    "best_bid_price": far_q.best_bid_price,
                    "best_ask_price": far_q.best_ask_price,
                    "T": T_f,
                    "implied_vol": far_q.implied_volatility or 0.50
                }
                cal_opp = opp_calc.evaluate_calendar_spread(
                    underlying=und,
                    spot=near_q.underlying_price or spot_ref,
                    strike=atm_strike,
                    near_quote=near_dict,
                    far_quote=far_dict,
                    forecast_vol=far_dict["implied_vol"],
                    uncertainty=0.03,
                    quantity=1.0
                )
                if cal_opp:
                    rec_id = f"rec_{uuid.uuid4().hex[:10]}"
                    rec = Recommendation(
                        id=rec_id,
                        underlying=und,
                        strategy_type=cal_opp["strategy_type"],
                        legs_json=json.dumps(cal_opp["legs"]),
                        implied_volatility=cal_opp["implied_volatility"],
                        forecast_volatility=cal_opp["forecast_volatility"],
                        gross_edge=cal_opp["gross_edge"],
                        net_edge=cal_opp["net_edge"],
                        spread_cost=cal_opp["spread_cost"],
                        fee_cost=cal_opp["fee_cost"],
                        slippage_cost=cal_opp["slippage_cost"],
                        hedge_cost=cal_opp["hedge_cost"],
                        carry_cost=cal_opp["carry_cost"],
                        uncertainty_penalty=cal_opp["uncertainty_penalty"],
                        delta=cal_opp["delta"],
                        gamma=cal_opp["gamma"],
                        vega=cal_opp["vega"],
                        theta=cal_opp["theta"],
                        initial_margin=cal_opp["initial_margin"],
                        stress_max_loss=cal_opp["stress_max_loss"],
                        confidence=cal_opp["confidence"],
                        rationale=cal_opp["rationale"],
                        expiry_at=datetime.datetime.fromisoformat(cal_opp["expiry_at"]),
                        status="pending",
                        is_watchlist=False
                    )
                    db.add(rec)
                    created_recs.append(rec_id)

    db.commit()
    return {
        "request_id": getattr(request.state, "request_id", "req_unknown"),
        "data": {"generated_count": len(created_recs), "recommendation_ids": created_recs}
    }
