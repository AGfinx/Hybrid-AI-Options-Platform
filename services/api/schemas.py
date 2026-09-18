from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class StandardResponse(BaseModel):
    request_id: str
    data: Any

class MarketHealthResponse(BaseModel):
    venue: str
    is_connected: bool
    live_feed_enabled: bool
    last_event_time: str
    quote_age_seconds: float
    sequence_status: str
    data_quality: str
    spot_price: float

class InstrumentResponse(BaseModel):
    id: str
    symbol: str
    underlying: str
    option_type: str
    strike: float
    expiry: str
    currency: str
    is_active: bool

class SurfacePointModel(BaseModel):
    strike: float
    expiry_years: float
    moneyness: float
    implied_vol: float
    option_type: str
    price: float
    delta: float
    vega: float
    confidence: float
    is_valid: bool

class SurfaceResponse(BaseModel):
    underlying: str
    spot: float
    structural_status: str
    confidence: float
    violations: List[str]
    point_count: int
    points: List[SurfacePointModel]

class ForecastRequest(BaseModel):
    underlying: str = "BTC"
    horizon_seconds: int = 3600
    feature_snapshot_id: Optional[str] = None
    model_version: str = "rv_forecaster_v1"

class ForecastResponse(BaseModel):
    forecast_id: str
    underlying: str
    forecast: float
    uncertainty: float
    regime: str
    valid_until: str
    model_version: str

class RecommendationApproveRequest(BaseModel):
    mode: str = "paper"
    quantity_override: Optional[float] = None
    price_limit_override: Optional[float] = None
    hedge_permission: str = "within_mandate"
    comment: Optional[str] = None

class RecommendationRejectRequest(BaseModel):
    reason: str

class RecommendationEditRequest(BaseModel):
    quantity: float
    price_limit: Optional[float] = None
    edit_reason: Optional[str] = None

class MandateCreateRequest(BaseModel):
    strategy: str
    allowed_instruments: List[str] = ["BTC-*"]
    venues: List[str] = ["deribit"]
    mode: str = "recommendation"
    capital_limit: float = 500000.0
    max_drawdown_limit: float = 0.15
    max_delta_limit: float = 5.0
    max_vega_limit: float = 50000.0
    max_var_limit: float = 100000.0
    hedge_permissions: str = "within_mandate"
    expiry_days: int = 90

class StressRunRequest(BaseModel):
    target_type: str = "portfolio"  # portfolio, recommendation
    target_id: Optional[str] = None

class EmergencyStopRequest(BaseModel):
    reason: str
    confirmed: bool = True

class PaperOrderCreateRequest(BaseModel):
    recommendation_id: Optional[str] = None
    instrument_id: str
    direction: str  # buy, sell
    order_type: str = "limit"
    quantity: float
    price_limit: Optional[float] = None

class ModeSwitchRequest(BaseModel):
    mode: str  # analytics, recommendation, assisted, bounded_automation
    reason: Optional[str] = None
