import datetime
from sqlalchemy import Column, String, Float, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from db.database import Base

class Recommendation(Base):
    __tablename__ = "recommendations"

    id = Column(String(64), primary_key=True)
    underlying = Column(String(32), nullable=False)
    strategy_type = Column(String(64), nullable=False)  # e.g., 'long_vol_straddle', 'vol_arbitrage_calendar', etc.
    legs_json = Column(Text, nullable=False)
    implied_volatility = Column(Float, nullable=False)
    forecast_volatility = Column(Float, nullable=False)
    gross_edge = Column(Float, nullable=False)
    net_edge = Column(Float, nullable=False)
    spread_cost = Column(Float, default=0.0)
    fee_cost = Column(Float, default=0.0)
    slippage_cost = Column(Float, default=0.0)
    hedge_cost = Column(Float, default=0.0)
    carry_cost = Column(Float, default=0.0)
    uncertainty_penalty = Column(Float, default=0.0)
    delta = Column(Float, default=0.0)
    gamma = Column(Float, default=0.0)
    vega = Column(Float, default=0.0)
    theta = Column(Float, default=0.0)
    initial_margin = Column(Float, default=0.0)
    stress_max_loss = Column(Float, default=0.0)
    confidence = Column(Float, default=1.0)
    rationale = Column(Text, nullable=True)
    expiry_at = Column(DateTime, nullable=False)
    status = Column(String(32), default="pending")  # pending, approved, rejected, expired, watchlisted, executed
    is_watchlist = Column(Boolean, default=False)
    surface_run_id = Column(String(64), ForeignKey("surface_runs.id"), nullable=True)
    forecast_run_id = Column(String(64), ForeignKey("forecast_runs.id"), nullable=True)
    model_version_id = Column(String(64), ForeignKey("model_versions.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    edits = relationship("RecommendationEdit", back_populates="recommendation")
    approvals = relationship("Approval", back_populates="recommendation")

class RecommendationEdit(Base):
    __tablename__ = "recommendation_edits"

    id = Column(String(64), primary_key=True)
    recommendation_id = Column(String(64), ForeignKey("recommendations.id"), nullable=False)
    user_id = Column(String(64), ForeignKey("users.id"), nullable=True)
    original_parameters_json = Column(Text, nullable=False)
    edited_parameters_json = Column(Text, nullable=False)
    recalculated_metrics_json = Column(Text, nullable=False)
    edit_reason = Column(String(256), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    recommendation = relationship("Recommendation", back_populates="edits")

class Approval(Base):
    __tablename__ = "approvals"

    id = Column(String(64), primary_key=True)
    recommendation_id = Column(String(64), ForeignKey("recommendations.id"), nullable=False)
    user_id = Column(String(64), ForeignKey("users.id"), nullable=True)
    decision = Column(String(32), nullable=False)  # approved, rejected, watchlisted
    mode = Column(String(32), default="paper")  # paper only
    quantity_override = Column(Float, nullable=True)
    price_limit_override = Column(Float, nullable=True)
    hedge_permission = Column(String(64), default="within_mandate")
    reason_comment = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    recommendation = relationship("Recommendation", back_populates="approvals")
