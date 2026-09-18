import datetime
from sqlalchemy import Column, String, Float, Integer, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from db.database import Base

class ModelVersion(Base):
    __tablename__ = "model_versions"

    id = Column(String(64), primary_key=True)
    model_name = Column(String(64), nullable=False)  # e.g., 'surface_bilinear', 'rv_ridge'
    version = Column(String(32), nullable=False)
    description = Column(String(256), nullable=True)
    parameters_json = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class FeatureSnapshot(Base):
    __tablename__ = "feature_snapshots"

    id = Column(String(64), primary_key=True)
    underlying = Column(String(32), nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    market_event_id = Column(String(64), ForeignKey("market_events.id"), nullable=True)
    features_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class SurfaceRun(Base):
    __tablename__ = "surface_runs"

    id = Column(String(64), primary_key=True)
    underlying = Column(String(32), nullable=False)
    model_version_id = Column(String(64), ForeignKey("model_versions.id"), nullable=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    points_json = Column(Text, nullable=False)
    structural_status = Column(String(32), default="valid")  # valid, arbitrage_violated, fallback
    confidence = Column(Float, default=1.0)
    error_metrics_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    model_version = relationship("ModelVersion")

class ForecastRun(Base):
    __tablename__ = "forecast_runs"

    id = Column(String(64), primary_key=True)
    underlying = Column(String(32), nullable=False)
    model_version_id = Column(String(64), ForeignKey("model_versions.id"), nullable=True)
    feature_snapshot_id = Column(String(64), ForeignKey("feature_snapshots.id"), nullable=True)
    horizon_seconds = Column(Integer, default=3600)
    forecast_value = Column(Float, nullable=False)
    uncertainty = Column(Float, default=0.05)
    regime = Column(String(32), default="normal")  # low, normal, elevated, extreme
    valid_until = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    model_version = relationship("ModelVersion")
    feature_snapshot = relationship("FeatureSnapshot")
