# app/models/zone.py
from sqlalchemy import Column, String, Text, ForeignKey, Integer, JSON
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
    
    # JSON properties for zone configuration
    properties = Column(JSON, nullable=True)
    
    tier = Column(Integer, default=1)

    # Entity limit configuration
    # entity_limit = Column(Integer, default=25)  # Default limit of 25 entities
    # entity_limit_upgrades = Column(Integer, default=0)  # Number of upgrades purchased
    
    # Foreign keys for relationships
    world_id = Column(String(36), ForeignKey("worlds.id"), nullable=False, index=True)
    parent_zone_id = Column(String(36), ForeignKey("zones.id"), nullable=True, index=True)
    
    # Relationships
    world = relationship("World", back_populates="zones")
    entities = relationship("Entity", back_populates="zone")
    characters = relationship("Character", back_populates="zone")
    objects = relationship("Object", back_populates="zone")
    agents = relationship("Agent", back_populates="zone")
    players = relationship("Player", back_populates="zone")
    
    # Self-referential relationship for sub-zones
    parent_zone = relationship("Zone", back_populates="sub_zones", remote_side=[id])
    sub_zones = relationship("Zone", back_populates="parent_zone")

    def __repr__(self):
        return f"<Zone {self.id} - {self.name} (World: {self.world_id})>"
    
    @property
    def total_entity_limit(self):
        """Calculate total entity limit with upgrades"""
        return self.entity_limit + (self.entity_limit_upgrades * 10)