import datetime
from sqlalchemy import Column, String, Float, Integer, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from db.database import Base

class Venue(Base):
    __tablename__ = "venues"

    id = Column(String(64), primary_key=True)
    name = Column(String(128), unique=True, nullable=False)
    venue_type = Column(String(32), default="deribit")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    instruments = relationship("Instrument", back_populates="venue")

class Instrument(Base):
    __tablename__ = "instruments"

    id = Column(String(64), primary_key=True)
    venue_id = Column(String(64), ForeignKey("venues.id"), nullable=False)
    symbol = Column(String(128), unique=True, nullable=False)
    underlying = Column(String(32), nullable=False)  # e.g., BTC
    option_type = Column(String(16), nullable=False)  # call, put
    strike = Column(Float, nullable=False)
    expiry = Column(DateTime, nullable=False)
    currency = Column(String(16), default="USD")
    tick_size = Column(Float, default=0.5)
    contract_size = Column(Float, default=1.0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    venue = relationship("Venue", back_populates="instruments")
    versions = relationship("InstrumentVersion", back_populates="instrument")
    quote_snapshots = relationship("QuoteSnapshot", back_populates="instrument")

class InstrumentVersion(Base):
    __tablename__ = "instrument_versions"

    id = Column(String(64), primary_key=True)
    instrument_id = Column(String(64), ForeignKey("instruments.id"), nullable=False)
    version = Column(Integer, default=1)
    parameters_json = Column(Text, nullable=True)
    effective_from = Column(DateTime, default=datetime.datetime.utcnow)
    effective_to = Column(DateTime, nullable=True)

    instrument = relationship("Instrument", back_populates="versions")

class MarketEvent(Base):
    __tablename__ = "market_events"

    id = Column(String(64), primary_key=True)
    venue_id = Column(String(64), ForeignKey("venues.id"), nullable=False)
    sequence_id = Column(Integer, nullable=True)
    event_type = Column(String(32), nullable=False)  # quote, orderbook, trade
    received_at = Column(DateTime, default=datetime.datetime.utcnow)
    exchange_timestamp = Column(DateTime, nullable=True)
    raw_payload_json = Column(Text, nullable=True)
    is_replayed = Column(Boolean, default=False)

class QuoteSnapshot(Base):
    __tablename__ = "quote_snapshots"

    id = Column(String(64), primary_key=True)
    instrument_id = Column(String(64), ForeignKey("instruments.id"), nullable=False)
    market_event_id = Column(String(64), ForeignKey("market_events.id"), nullable=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    best_bid_price = Column(Float, nullable=True)
    best_bid_amount = Column(Float, nullable=True)
    best_ask_price = Column(Float, nullable=True)
    best_ask_amount = Column(Float, nullable=True)
    mark_price = Column(Float, nullable=True)
    underlying_price = Column(Float, nullable=True)
    implied_volatility = Column(Float, nullable=True)
    delta = Column(Float, nullable=True)
    vega = Column(Float, nullable=True)

    instrument = relationship("Instrument", back_populates="quote_snapshots")

class TradeEvent(Base):
    __tablename__ = "trade_events"

    id = Column(String(64), primary_key=True)
    instrument_id = Column(String(64), ForeignKey("instruments.id"), nullable=False)
    market_event_id = Column(String(64), ForeignKey("market_events.id"), nullable=True)
    trade_id = Column(String(64), nullable=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    price = Column(Float, nullable=False)
    amount = Column(Float, nullable=False)
    direction = Column(String(16), nullable=False)  # buy, sell
