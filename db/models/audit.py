import datetime
from sqlalchemy import Column, String, DateTime, Text
from db.database import Base

class AuditEvent(Base):
    __tablename__ = "audit_events"

    id = Column(String(64), primary_key=True)
    actor_id = Column(String(64), nullable=True)  # user ID or system component
    action = Column(String(64), nullable=False)  # e.g., 'approve_recommendation', 'emergency_stop', 'edit_parameters'
    object_type = Column(String(64), nullable=False)  # e.g., 'recommendation', 'circuit_breaker', 'order'
    object_id = Column(String(64), nullable=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    request_id = Column(String(64), nullable=True)
    before_state_json = Column(Text, nullable=True)
    after_state_json = Column(Text, nullable=True)
    details_json = Column(Text, nullable=True)
