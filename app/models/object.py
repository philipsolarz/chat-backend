# app/models/object.py
from sqlalchemy import Column, Boolean, String

from app.models.entity import Entity, EntityType


class Object(Entity):
    """
    Model representing objects in the world
    Objects are static entities that can be interacted with
    """
    # Additional object-specific columns
    is_interactive = Column(Boolean, default=False)
    object_type = Column(String(50), nullable=True)  # e.g., "item", "furniture", "landmark"
    
    __mapper_args__ = {
        'polymorphic_identity': EntityType.OBJECT
    }
    
    def __repr__(self):
        return f"<Object {self.id} - {self.name}>"