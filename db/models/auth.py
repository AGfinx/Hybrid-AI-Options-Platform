import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Table
from sqlalchemy.orm import relationship
from db.database import Base

role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", String(64), ForeignKey("roles.id"), primary_key=True),
    Column("permission_id", String(64), ForeignKey("permissions.id"), primary_key=True),
)

user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", String(64), ForeignKey("users.id"), primary_key=True),
    Column("role_id", String(64), ForeignKey("roles.id"), primary_key=True),
)

class Permission(Base):
    __tablename__ = "permissions"

    id = Column(String(64), primary_key=True)
    name = Column(String(128), unique=True, nullable=False)
    description = Column(String(256), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class Role(Base):
    __tablename__ = "roles"

    id = Column(String(64), primary_key=True)
    name = Column(String(64), unique=True, nullable=False)
    description = Column(String(256), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    permissions = relationship("Permission", secondary=role_permissions, backref="roles")

class User(Base):
    __tablename__ = "users"

    id = Column(String(64), primary_key=True)
    username = Column(String(64), unique=True, nullable=False)
    email = Column(String(128), unique=True, nullable=False)
    hashed_token = Column(String(256), nullable=True)
    is_active = Column(String(16), default="active")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    roles = relationship("Role", secondary=user_roles, backref="users")
