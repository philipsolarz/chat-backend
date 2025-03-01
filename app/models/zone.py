# app/models/zone.py
from sqlalchemy import Column, String, Text, ForeignKey, Integer, Boolean, Float, Table
from sqlalchemy.orm import relationship

from app.database import Base
from app.models.mixins import TimestampMixin, generate_uuid


class Zone(Base, TimestampMixin):
    """
    Model representing a geographical or logical zone within a world
    Zones can be nested (a zone can have sub-zones)
    """
    __tablename__ = "zones"
    
    id = Column(String(36), primary_key=True, default=generate_uuid, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    
    # Zone type (city, dungeon, forest, etc)
    zone_type = Column(String(50), nullable=True)
    
    # Geographic info (could be expanded in a real implementation)
    coordinates = Column(String(100), nullable=True)
    
    # Zone properties (could be JSON in a real implementation)
    properties = Column(Text, nullable=True)
    
    # Foreign keys for relationships
    world_id = Column(String(36), ForeignKey("worlds.id"), nullable=False, index=True)
    parent_zone_id = Column(String(36), ForeignKey("zones.id"), nullable=True, index=True)
    
    # Relationships
    world = relationship("World", back_populates="zones")
    
    # Self-referential relationship for sub-zones
    parent_zone = relationship("Zone", back_populates="sub_zones", remote_side=[id])
    sub_zones = relationship("Zone", back_populates="parent_zone")
    
    # Characters in this zone
    characters = relationship("Character", back_populates="zone")
    
    # Agents (NPCs) in this zone
    agents = relationship("Agent", back_populates="zone")
    
    def __repr__(self):
        return f"<Zone {self.id} - {self.name} (World: {self.world_id})>"