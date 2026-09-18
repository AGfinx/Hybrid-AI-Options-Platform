import uuid
import datetime
import json
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from db.database import get_db
from db.models import ForecastRun, FeatureSnapshot, ModelVersion
from services.api.schemas import ForecastRequest
from packages.quant.rv_forecast import RealizedVolForecaster

router = APIRouter(tags=["Forecasts"])
forecaster = RealizedVolForecaster()

@router.post("/forecasts/realized-volatility")
def generate_forecast(
    body: ForecastRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    features = {
        "rv_7d": 0.52,
        "rv_14d": 0.55,
        "rv_30d": 0.58,
        "return_skew": -0.12
    }

    if body.feature_snapshot_id:
        fs = db.query(FeatureSnapshot).filter_by(id=body.feature_snapshot_id).first()
        if fs:
            try:
                features = json.loads(fs.features_json)
            except Exception:
                pass

    res = forecaster.forecast(
        features=features,
        horizon_seconds=body.horizon_seconds,
        underlying=body.underlying
    )

    f_id = f"fc_{uuid.uuid4().hex[:10]}"
    valid_until_dt = datetime.datetime.fromisoformat(res["valid_until"])

    run = ForecastRun(
        id=f_id,
        underlying=body.underlying,
        model_version_id=body.model_version,
        feature_snapshot_id=body.feature_snapshot_id,
        horizon_seconds=body.horizon_seconds,
        forecast_value=res["forecast"],
        uncertainty=res["uncertainty"],
        regime=res["regime"],
        valid_until=valid_until_dt
    )
    db.add(run)
    db.commit()

    return {
        "request_id": getattr(request.state, "request_id", "req_unknown"),
        "data": {
            "forecast_id": f_id,
            "underlying": body.underlying,
            "forecast": res["forecast"],
            "uncertainty": res["uncertainty"],
            "regime": res["regime"],
            "valid_until": res["valid_until"],
            "model_version": body.model_version
        }
    }
