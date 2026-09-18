import datetime
from sqlalchemy import Column, String, Float, DateTime, ForeignKey, Integer
from sqlalchemy.orm import relationship
from db.database import Base

class PaperOrder(Base):
    __tablename__ = "paper_orders"

    id = Column(String(64), primary_key=True)
    recommendation_id = Column(String(64), ForeignKey("recommendations.id"), nullable=True)
    mandate_id = Column(String(64), ForeignKey("mandates.id"), nullable=True)
    instrument_id = Column(String(64), ForeignKey("instruments.id"), nullable=False)
    direction = Column(String(16), nullable=False)  # buy, sell
    order_type = Column(String(16), default="limit")  # market, limit
    quantity = Column(Float, nullable=False)
    price_limit = Column(Float, nullable=True)
    filled_quantity = Column(Float, default=0.0)
    avg_fill_price = Column(Float, nullable=True)
    status = Column(String(32), default="pending")  # pending, filled, partially_filled, cancelled, rejected
    slippage_assumed = Column(Float, default=0.0)
    fee_assumed = Column(Float, default=0.0)
    latency_ms_assumed = Column(Integer, default=50)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    fills = relationship("PaperFill", back_populates="order")
    instrument = relationship("Instrument")

class PaperFill(Base):
    __tablename__ = "paper_fills"

    id = Column(String(64), primary_key=True)
    paper_order_id = Column(String(64), ForeignKey("paper_orders.id"), nullable=False)
    fill_price = Column(Float, nullable=False)
    fill_quantity = Column(Float, nullable=False)
    fee_paid = Column(Float, default=0.0)
    slippage_incurred = Column(Float, default=0.0)
    executed_at = Column(DateTime, default=datetime.datetime.utcnow)

    order = relationship("PaperOrder", back_populates="fills")

class Position(Base):
    __tablename__ = "positions"

    id = Column(String(64), primary_key=True)
    instrument_id = Column(String(64), ForeignKey("instruments.id"), nullable=False)
    quantity = Column(Float, default=0.0)
    avg_entry_price = Column(Float, default=0.0)
    current_mark_price = Column(Float, default=0.0)
    delta = Column(Float, default=0.0)
    gamma = Column(Float, default=0.0)
    vega = Column(Float, default=0.0)
    theta = Column(Float, default=0.0)
    unrealized_pnl = Column(Float, default=0.0)
    realized_pnl = Column(Float, default=0.0)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    instrument = relationship("Instrument")

class HedgeAction(Base):
    __tablename__ = "hedge_actions"

    id = Column(String(64), primary_key=True)
    position_id = Column(String(64), ForeignKey("positions.id"), nullable=True)
    paper_order_id = Column(String(64), ForeignKey("paper_orders.id"), nullable=True)
    underlying = Column(String(32), default="BTC")
    hedge_type = Column(String(32), default="spot_delta")
    quantity = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    executed_at = Column(DateTime, default=datetime.datetime.utcnow)

class PnLAttribution(Base):
    __tablename__ = "pnl_attributions"

    id = Column(String(64), primary_key=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    delta_pnl = Column(Float, default=0.0)
    gamma_pnl = Column(Float, default=0.0)
    vega_pnl = Column(Float, default=0.0)
    theta_pnl = Column(Float, default=0.0)
    fee_pnl = Column(Float, default=0.0)
    slippage_pnl = Column(Float, default=0.0)
    hedge_pnl = Column(Float, default=0.0)
    residual_pnl = Column(Float, default=0.0)
    total_pnl = Column(Float, default=0.0)
