# app/models/entity.py
from sqlalchemy import Column, String, Text, ForeignKey, JSON, Enum
from sqlalchemy.orm import relationship
import enum

from app.database import Base
from app.models.mixins import TimestampMixin, generate_uuid


class EntityType(str, enum.Enum):
    """Types of entities that can exist in zones"""
    AGENT = "agent"
    OBJECT = "object"
    # CHARACTER = "character"


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
    
    # JSON settings for entity-specific properties
    settings = Column(JSON, nullable=True)
    
    # Foreign keys
    zone_id = Column(String(36), ForeignKey("zones.id"), nullable=True)
    
    # Discriminator column for inheritance
    __mapper_args__ = {
        'polymorphic_on': type,
        'polymorphic_identity': None
    }
    
    # Relationships
    zone = relationship("Zone", back_populates="entities")
    
    def __repr__(self):
        return f"<Entity {self.id} - {self.name} ({self.type})>"