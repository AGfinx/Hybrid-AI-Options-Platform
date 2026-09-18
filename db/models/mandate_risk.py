import datetime
from sqlalchemy import Column, String, Float, Boolean, DateTime, Text
from db.database import Base

class Mandate(Base):
    __tablename__ = "mandates"

    id = Column(String(64), primary_key=True)
    strategy = Column(String(64), nullable=False)
    allowed_instruments_json = Column(Text, nullable=False)
    venues_json = Column(Text, nullable=False)
    mode = Column(String(32), default="recommendation")
    capital_limit = Column(Float, nullable=False)
    max_drawdown_limit = Column(Float, default=0.15)
    max_delta_limit = Column(Float, default=5.0)
    max_vega_limit = Column(Float, default=50000.0)
    max_var_limit = Column(Float, default=100000.0)
    hedge_permissions = Column(String(64), default="within_mandate")
    is_active = Column(Boolean, default=True)
    status = Column(String(32), default="active")  # active, paused, terminated
    start_time = Column(DateTime, default=datetime.datetime.utcnow)
    expiry_time = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

class RiskLimit(Base):
    __tablename__ = "risk_limits"

    id = Column(String(64), primary_key=True)
    scope = Column(String(64), default="global")  # global, portfolio, strategy
    limit_name = Column(String(64), nullable=False)  # max_delta, max_vega, max_loss, etc.
    limit_value = Column(Float, nullable=False)
    warning_threshold = Column(Float, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class StressRun(Base):
    __tablename__ = "stress_runs"

    id = Column(String(64), primary_key=True)
    target_type = Column(String(32), default="portfolio")  # portfolio, recommendation
    target_id = Column(String(64), nullable=True)
    base_portfolio_value = Column(Float, default=0.0)
    spot_shocks_json = Column(Text, nullable=False)
    vol_shocks_json = Column(Text, nullable=False)
    scenario_results_json = Column(Text, nullable=False)
    max_loss = Column(Float, nullable=False)
    margin_impact = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class CircuitBreaker(Base):
    __tablename__ = "circuit_breakers"

    id = Column(String(64), primary_key=True)
    name = Column(String(64), nullable=False)  # emergency_stop, max_drawdown, stale_quote
    trigger_condition = Column(String(128), nullable=False)
    is_tripped = Column(Boolean, default=False)
    tripped_at = Column(DateTime, nullable=True)
    reset_at = Column(DateTime, nullable=True)
    reason = Column(Text, nullable=True)

class Alert(Base):
    __tablename__ = "alerts"

    id = Column(String(64), primary_key=True)
    severity = Column(String(16), default="warning")  # info, warning, critical
    alert_type = Column(String(64), nullable=False)
    message = Column(Text, nullable=False)
    context_json = Column(Text, nullable=True)
    is_acknowledged = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
