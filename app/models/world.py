# app/models/world.py
from sqlalchemy import Column, Integer, String, Text, ForeignKey, JSON, Boolean
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
    
    # JSON properties for world configuration
    properties = Column(JSON, nullable=True)

    tier = Column(Integer, default=1)
    
    # New fields for world status
    is_official = Column(Boolean, default=False, nullable=False)
    is_private = Column(Boolean, default=False, nullable=False)
    
    # Creator/owner of the world
    owner_id = Column(String(36), ForeignKey("players.id"), nullable=True)
    
    # Relationships
    owner = relationship("Player", back_populates="owned_worlds", foreign_keys=[owner_id])

    zones = relationship("Zone", back_populates="world", cascade="all, delete-orphan")
    # entities = relationship("Entity", back_populates="world")
    # characters = relationship("Character", back_populates="world")
    # objects = relationship("Object", back_populates="world")
    # agents = relationship("Agent", back_populates="world")
    # players = relationship("Player", back_populates="world")

    events = relationship("GameEvent", back_populates="world", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<World {self.id} - {self.name}>"