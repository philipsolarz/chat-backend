# app/models/world.py
from sqlalchemy import Column, Integer, String, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship

from app.database import Base
from app.models.mixins import TimestampMixin, generate_uuid


class World(Base, TimestampMixin):
    """
    Model representing a game world where entities exist
    """
    __tablename__ = "worlds"
    
    id = Column(String(36), primary_key=True, default=generate_uuid, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    
    # JSON settings for world configuration
    settings = Column(JSON, nullable=True)

    # Zone management
    zone_limit = Column(Integer, default=100)
    zone_limit_upgrades = Column(Integer, default=0)
    
    # Creator/owner of the world
    owner_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    
    # Relationships
    owner = relationship("User", back_populates="owned_worlds", foreign_keys=[owner_id])
    zones = relationship("Zone", back_populates="world", cascade="all, delete-orphan")
    
    # Optional relationships (may be kept or removed based on needs)
    characters = relationship("Character", back_populates="world")
    conversations = relationship("Conversation", back_populates="world")
    
    def __repr__(self):
        return f"<World {self.id} - {self.name}>"
    
    @property
    def total_zone_limit(self):
        """Calculate total zone limit with upgrades"""
        return self.zone_limit + (self.zone_limit_upgrades * 100)