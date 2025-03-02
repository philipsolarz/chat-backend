# app/models/entity.py
from sqlalchemy import Column, Integer, String, Text, ForeignKey, JSON, Enum
from sqlalchemy.orm import relationship
import enum

from app.database import Base
from app.models.mixins import TimestampMixin, generate_uuid


class EntityType(str, enum.Enum):
    """Types of entities that can exist in zones"""
    CHARACTER = "character"
    OBJECT = "object"

class Entity(Base, TimestampMixin):
    """
    Base model for all entities in the world
    Entities are things that can exist in zones
    """
    __tablename__ = "entities"
    
    id = Column(String(36), primary_key=True, default=generate_uuid, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    
    # Entity type discriminator
    type = Column(Enum(EntityType), nullable=False)
    
    # JSON properties for entity-specific properties
    properties = Column(JSON, nullable=True)
    
    # Foreign keys
    # world_id = Column(String(36), ForeignKey("worlds.id"), nullable=True)
    zone_id = Column(String(36), ForeignKey("zones.id"), nullable=True)
    # character_id = Column(String(36), ForeignKey("characters.id"), nullable=True)
    # object_id = Column(String(36), ForeignKey("objects.id"), nullable=True)

    # agent_id = Column(String(36), ForeignKey("agents.id"), nullable=True)
    # player_id = Column(String(36), ForeignKey("players.id"), nullable=True)

    # Relationships
    zone = relationship("Zone", back_populates="entities")
    # world = relationship("World", back_populates="entities")

    character = relationship("Character", back_populates="entity")
    object = relationship("Object", back_populates="entity")

    # agent = relationship("Agent", back_populates="entity")
    # player = relationship("Player", back_populates="entity")

    targeted_events = relationship("GameEvent", foreign_keys="GameEvent.target_entity_id", back_populates="target_entity")
    
    def __repr__(self):
        return f"<Entity {self.id} - {self.name} ({self.type})>"