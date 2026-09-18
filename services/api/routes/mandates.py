import uuid
import datetime
import json
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from db.database import get_db
from db.models import Mandate
from services.api.schemas import MandateCreateRequest
from services.api.auth import get_current_user, record_audit

router = APIRouter(tags=["Mandates"])

@router.get("/mandates")
def list_mandates(request: Request, db: Session = Depends(get_db)):
    mandates = db.query(Mandate).all()
    res = [
        {
            "id": m.id,
            "strategy": m.strategy,
            "allowed_instruments": json.loads(m.allowed_instruments_json),
            "venues": json.loads(m.venues_json),
            "mode": m.mode,
            "capital_limit": m.capital_limit,
            "max_drawdown_limit": m.max_drawdown_limit,
            "max_delta_limit": m.max_delta_limit,
            "max_vega_limit": m.max_vega_limit,
            "max_var_limit": m.max_var_limit,
            "hedge_permissions": m.hedge_permissions,
            "status": m.status,
            "start_time": m.start_time.isoformat() if m.start_time else "",
            "expiry_time": m.expiry_time.isoformat() if m.expiry_time else ""
        }
        for m in mandates
    ]
    return {
        "request_id": getattr(request.state, "request_id", "req_unknown"),
        "data": res
    }

@router.post("/mandates")
def create_mandate(
    body: MandateCreateRequest,
    request: Request,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    now = datetime.datetime.now(datetime.timezone.utc)
    exp = now + datetime.timedelta(days=body.expiry_days)
    m_id = f"mandate_{uuid.uuid4().hex[:10]}"

    mandate = Mandate(
        id=m_id,
        strategy=body.strategy,
        allowed_instruments_json=json.dumps(body.allowed_instruments),
        venues_json=json.dumps(body.venues),
        mode=body.mode,
        capital_limit=body.capital_limit,
        max_drawdown_limit=body.max_drawdown_limit,
        max_delta_limit=body.max_delta_limit,
        max_vega_limit=body.max_vega_limit,
        max_var_limit=body.max_var_limit,
        hedge_permissions=body.hedge_permissions,
        status="active",
        start_time=now,
        expiry_time=exp
    )
    db.add(mandate)
    db.commit()

    record_audit(
        db,
        actor_id=current_user.id if current_user else "user_dev_01",
        action="create_mandate",
        object_type="mandate",
        object_id=m_id,
        request_id=getattr(request.state, "request_id", None),
        after_state={"id": m_id, "strategy": body.strategy, "capital_limit": body.capital_limit}
    )

    return {
        "request_id": getattr(request.state, "request_id", "req_unknown"),
        "data": {"id": m_id, "status": "active"}
    }

@router.post("/mandates/{mandate_id}/pause")
def pause_mandate(
    mandate_id: str,
    request: Request,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    m = db.query(Mandate).filter_by(id=mandate_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Mandate not found")

    m.status = "paused"
    db.commit()

    record_audit(
        db,
        actor_id=current_user.id if current_user else "user_dev_01",
        action="pause_mandate",
        object_type="mandate",
        object_id=mandate_id,
        request_id=getattr(request.state, "request_id", None),
        after_state={"status": "paused"}
    )

    return {
        "request_id": getattr(request.state, "request_id", "req_unknown"),
        "data": {"id": mandate_id, "status": "paused"}
    }

@router.post("/mandates/{mandate_id}/terminate")
def terminate_mandate(
    mandate_id: str,
    request: Request,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    m = db.query(Mandate).filter_by(id=mandate_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Mandate not found")

    m.status = "terminated"
    m.is_active = False
    db.commit()

    record_audit(
        db,
        actor_id=current_user.id if current_user else "user_dev_01",
        action="terminate_mandate",
        object_type="mandate",
        object_id=mandate_id,
        request_id=getattr(request.state, "request_id", None),
        after_state={"status": "terminated"}
    )

    return {
        "request_id": getattr(request.state, "request_id", "req_unknown"),
        "data": {"id": mandate_id, "status": "terminated"}
    }

@router.post("/mandates/{mandate_id}/activate")
def activate_mandate(
    mandate_id: str,
    request: Request,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    m = db.query(Mandate).filter_by(id=mandate_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Mandate not found")

    m.status = "active"
    m.is_active = True
    db.commit()

    record_audit(
        db,
        actor_id=current_user.id if current_user else "user_dev_01",
        action="activate_mandate",
        object_type="mandate",
        object_id=mandate_id,
        request_id=getattr(request.state, "request_id", None),
        after_state={"status": "active"}
    )

    return {
        "request_id": getattr(request.state, "request_id", "req_unknown"),
        "data": {"id": mandate_id, "status": "active"}
    }
