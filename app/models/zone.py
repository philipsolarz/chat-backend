# app/models/zone.py
from sqlalchemy import Column, String, Text, Integer, JSON, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base
from app.models.mixins import TimestampMixin, generate_uuid

class Zone(Base, TimestampMixin):
    __tablename__ = "zones"
    
    id = Column(String(36), primary_key=True, default=generate_uuid, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    properties = Column(JSON, nullable=True)
    tier = Column(Integer, default=1)
    
    world_id = Column(String(36), ForeignKey("worlds.id"), nullable=False, index=True)
    parent_zone_id = Column(String(36), ForeignKey("zones.id"), nullable=True, index=True)
    
    # Relationships
    world = relationship("World", back_populates="zones")
    parent_zone = relationship("Zone", remote_side=[id], back_populates="sub_zones")
    sub_zones = relationship("Zone", back_populates="parent_zone", cascade="all, delete-orphan")
    entities = relationship("Entity", back_populates="zone", cascade="all, delete-orphan")
    events = relationship("GameEvent", back_populates="zone", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Zone {self.id} - {self.name} (World: {self.world_id})>"
