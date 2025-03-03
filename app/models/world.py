# app/models/world.py
from sqlalchemy import Column, Integer, String, Text, JSON, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base
from app.models.mixins import TimestampMixin, generate_uuid

class World(Base, TimestampMixin):
    __tablename__ = "worlds"
    
    id = Column(String(36), primary_key=True, default=generate_uuid, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    properties = Column(JSON, nullable=True)
    tier = Column(Integer, default=1)
    is_official = Column(Boolean, default=False, nullable=False)
    is_private = Column(Boolean, default=False, nullable=False)
    
    owner_id = Column(String(36), ForeignKey("players.id"), nullable=True)
    
    # Relationships
    owner = relationship("Player", back_populates="owned_worlds")
    zones = relationship("Zone", back_populates="world", cascade="all, delete-orphan")
    events = relationship("GameEvent", back_populates="world", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<World {self.id} - {self.name}>"
