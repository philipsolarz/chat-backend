# app/models/object.py
from sqlalchemy import Column, Integer, String, ForeignKey, Enum as SAEnum
from app.database import Base
from app.models.entity import Entity
from app.models.enums import ObjectType

class Object(Entity):
    __tablename__ = "objects"
    id = Column(String(36), ForeignKey("entities.id"), primary_key=True)
    
    object_type = Column(SAEnum(ObjectType), nullable=False)
    # tier = Column(Integer, default=1)
    
    __mapper_args__ = {
        "polymorphic_identity": "object",
    }
    
    def __repr__(self):
        return f"<Object {self.id} - {self.name} ({self.object_type})>"
