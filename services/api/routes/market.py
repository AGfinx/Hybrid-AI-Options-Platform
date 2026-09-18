import datetime
import json
from typing import Optional
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session
from db.database import get_db
from db.models import Instrument, QuoteSnapshot, SurfaceRun, ModelVersion
from services.market_data.collector import DeribitMarketDataCollector
from packages.quant.surface import VolatilitySurface

router = APIRouter(tags=["Market & Analytics"])
collector = DeribitMarketDataCollector(live_enabled=False)

@router.get("/market/health")
def get_market_health(request: Request, db: Session = Depends(get_db)):
    health = collector.get_health_status()
    # Check latest quote from database
    latest_quote = db.query(QuoteSnapshot).order_by(QuoteSnapshot.timestamp.desc()).first()
    if latest_quote and latest_quote.timestamp:
        now = datetime.datetime.now(datetime.timezone.utc)
        # Handle naive or aware
        ts = latest_quote.timestamp
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=datetime.timezone.utc)
        diff = (now - ts).total_seconds()
        health["quote_age_seconds"] = round(diff, 2)
        health["last_event_time"] = ts.isoformat()
        if latest_quote.underlying_price:
            health["spot_price"] = latest_quote.underlying_price

    return {
        "request_id": getattr(request.state, "request_id", "req_unknown"),
        "data": health
    }

@router.get("/instruments")
def get_instruments(
    request: Request,
    venue: Optional[str] = Query(None),
    underlying: Optional[str] = Query("BTC"),
    expiry: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    query = db.query(Instrument)
    if venue:
        query = query.filter(Instrument.venue_id == venue)
    if underlying:
        query = query.filter(Instrument.underlying == underlying)
    if state == "active":
        query = query.filter(Instrument.is_active == True)

    instruments = query.all()
    res = [
        {
            "id": inst.id,
            "symbol": inst.symbol,
            "underlying": inst.underlying,
            "option_type": inst.option_type,
            "strike": inst.strike,
            "expiry": inst.expiry.isoformat() if inst.expiry else "",
            "currency": inst.currency,
            "is_active": inst.is_active
        }
        for inst in instruments
    ]
    return {
        "request_id": getattr(request.state, "request_id", "req_unknown"),
        "data": res
    }

@router.get("/surfaces/{underlying}")
def get_volatility_surface(
    underlying: str,
    request: Request,
    model_version: Optional[str] = Query("surface_bilinear_v1"),
    db: Session = Depends(get_db)
):
    # Fetch recent quote snapshots for this underlying
    quotes = (
        db.query(QuoteSnapshot, Instrument)
        .join(Instrument, QuoteSnapshot.instrument_id == Instrument.id)
        .filter(Instrument.underlying == underlying)
        .order_by(QuoteSnapshot.timestamp.desc())
        .limit(200)
        .all()
    )

    spot = 65000.0 if underlying.upper() == "BTC" else 3500.0
    quote_dicts = []
    now = datetime.datetime.now(datetime.timezone.utc)

    for qs, inst in quotes:
        if qs.underlying_price:
            spot = qs.underlying_price
        # Time to expiry in years
        exp = inst.expiry
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=datetime.timezone.utc)
        T = max(0.001, (exp - now).total_seconds() / (365.25 * 86400.0))

        iv = qs.implied_volatility or 0.55
        quote_dicts.append({
            "strike": inst.strike,
            "T": T,
            "implied_vol": iv,
            "option_type": inst.option_type,
            "best_bid_price": qs.best_bid_price,
            "best_ask_price": qs.best_ask_price
        })

    surface = VolatilitySurface(underlying=underlying, spot=spot)
    surface.build_from_quotes(quote_dicts)
    surf_data = surface.to_dict()

    # Record or update surface run in DB
    run = SurfaceRun(
        id=f"srun_{datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d%H%M%S')}",
        underlying=underlying,
        model_version_id=model_version,
        timestamp=now,
        points_json=json.dumps(surf_data["points"]),
        structural_status=surf_data["structural_status"],
        confidence=surf_data["confidence"],
        error_metrics_json=json.dumps({"violations": surf_data["violations"]})
    )
    db.add(run)
    db.commit()

    return {
        "request_id": getattr(request.state, "request_id", "req_unknown"),
        "data": surf_data
    }
