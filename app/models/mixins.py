# app/models/mixins.py
from sqlalchemy import Column, DateTime
from sqlalchemy.sql import func
import uuid
from sqlalchemy import Column, String


def generate_uuid():
    """Generate a UUID string for use as a primary key"""
    return str(uuid.uuid4())


class TimestampMixin:
    """Mixin to add created_at and updated_at columns to models"""
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)