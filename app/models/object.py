# app/models/object.py
import enum
from sqlalchemy import JSON, Column, Boolean, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from app.database import Base
from app.models.entity import EntityType
from app.models.mixins import TimestampMixin, generate_uuid

class ObjectType(str, enum.Enum):
    """Types of objects that can exist"""
    GENERIC = "generic"

class Object(Base, TimestampMixin):
    """
    Model representing objects in the world
    Objects are static entities that can be interacted with
    """
    __tablename__ = "objects"
    
    id = Column(String(36), primary_key=True, default=generate_uuid, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    
    # Object type discriminator
    type = Column(Enum(ObjectType), nullable=False)
    
    # JSON properties for object-specific properties
    properties = Column(JSON, nullable=True)
    
    tier = Column(Integer, default=1)
    
    # world_id = Column(String(36), ForeignKey("worlds.id"), nullable=True)
    # zone_id = Column(String(36), ForeignKey("zones.id"), nullable=True)
    entity_id = Column(String(36), ForeignKey("entities.id"), nullable=True)

    # zone = relationship("Zone", back_populates="objects")
    # world = relationship("World", back_populates="objects")
    entity = relationship("Entity", back_populates="object")

    def __repr__(self):
        return f"<Object {self.id} - {self.name}>"