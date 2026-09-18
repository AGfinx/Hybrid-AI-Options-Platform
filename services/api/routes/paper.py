import uuid
import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from db.database import get_db
from db.models import PaperOrder, Position, Instrument, CircuitBreaker
from services.api.schemas import PaperOrderCreateRequest
from services.api.auth import get_current_user, record_audit
from services.simulator.engine import PaperTradingSimulator

router = APIRouter(tags=["Paper Trading"])
simulator = PaperTradingSimulator()

@router.get("/paper/orders")
def list_paper_orders(request: Request, db: Session = Depends(get_db)):
    orders = db.query(PaperOrder).order_by(PaperOrder.created_at.desc()).all()
    res = [
        {
            "id": o.id,
            "recommendation_id": o.recommendation_id,
            "instrument_id": o.instrument_id,
            "symbol": o.instrument.symbol if o.instrument else "",
            "direction": o.direction,
            "order_type": o.order_type,
            "quantity": o.quantity,
            "price_limit": o.price_limit,
            "filled_quantity": o.filled_quantity,
            "avg_fill_price": o.avg_fill_price,
            "status": o.status,
            "fee_assumed": o.fee_assumed,
            "slippage_assumed": o.slippage_assumed,
            "created_at": o.created_at.isoformat() if o.created_at else ""
        }
        for o in orders
    ]
    return {
        "request_id": getattr(request.state, "request_id", "req_unknown"),
        "data": res
    }

@router.get("/paper/orders/{order_id}")
def get_paper_order(order_id: str, request: Request, db: Session = Depends(get_db)):
    o = db.query(PaperOrder).filter_by(id=order_id).first()
    if not o:
        raise HTTPException(status_code=404, detail="Order not found")

    return {
        "request_id": getattr(request.state, "request_id", "req_unknown"),
        "data": {
            "id": o.id,
            "recommendation_id": o.recommendation_id,
            "instrument_id": o.instrument_id,
            "symbol": o.instrument.symbol if o.instrument else "",
            "direction": o.direction,
            "order_type": o.order_type,
            "quantity": o.quantity,
            "price_limit": o.price_limit,
            "filled_quantity": o.filled_quantity,
            "avg_fill_price": o.avg_fill_price,
            "status": o.status,
            "fee_assumed": o.fee_assumed,
            "slippage_assumed": o.slippage_assumed,
            "created_at": o.created_at.isoformat() if o.created_at else ""
        }
    }

@router.post("/paper/orders")
def create_paper_order(
    body: PaperOrderCreateRequest,
    request: Request,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Check circuit breakers
    emergency = db.query(CircuitBreaker).filter_by(name="emergency_stop", is_tripped=True).first()
    if emergency:
        raise HTTPException(status_code=422, detail="Emergency Stop is active. New paper orders cannot be created.")

    inst = db.query(Instrument).filter_by(id=body.instrument_id).first()
    if not inst:
        raise HTTPException(status_code=404, detail=f"Instrument {body.instrument_id} not found")

    order_id = f"order_{uuid.uuid4().hex[:10]}"
    order = PaperOrder(
        id=order_id,
        recommendation_id=body.recommendation_id,
        mandate_id="mandate_btc_vol_01",
        instrument_id=body.instrument_id,
        direction=body.direction.lower(),
        order_type=body.order_type.lower(),
        quantity=body.quantity,
        price_limit=body.price_limit,
        status="pending"
    )
    db.add(order)
    db.commit()

    # Immediately simulate fill
    sim_result = simulator.execute_order(order_id, db_session=db)

    record_audit(
        db,
        actor_id=current_user.id if current_user else "user_dev_01",
        action="create_paper_order",
        object_type="paper_order",
        object_id=order_id,
        request_id=getattr(request.state, "request_id", None),
        after_state={"order_id": order_id, "status": sim_result.get("status"), "fill": sim_result}
    )

    return {
        "request_id": getattr(request.state, "request_id", "req_unknown"),
        "data": {
            "order_id": order_id,
            "status": sim_result.get("status"),
            "execution": sim_result
        }
    }

@router.get("/paper/positions")
def list_paper_positions(request: Request, db: Session = Depends(get_db)):
    positions = db.query(Position).all()
    res = [
        {
            "id": p.id,
            "instrument_id": p.instrument_id,
            "symbol": p.instrument.symbol if p.instrument else "",
            "option_type": p.instrument.option_type if p.instrument else "call",
            "strike": p.instrument.strike if p.instrument else 0.0,
            "quantity": p.quantity,
            "avg_entry_price": p.avg_entry_price,
            "current_mark_price": p.current_mark_price,
            "delta": p.delta,
            "gamma": p.gamma,
            "vega": p.vega,
            "theta": p.theta,
            "unrealized_pnl": p.unrealized_pnl,
            "realized_pnl": p.realized_pnl
        }
        for p in positions
        if p.quantity != 0.0
    ]
    return {
        "request_id": getattr(request.state, "request_id", "req_unknown"),
        "data": res
    }
