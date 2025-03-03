# app/models/entity.py
from sqlalchemy import Column, Integer, String, Text, JSON, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base
from app.models.mixins import TimestampMixin, generate_uuid

class Entity(Base, TimestampMixin):
    __tablename__ = "entities"
    
    id = Column(String(36), primary_key=True, default=generate_uuid, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    properties = Column(JSON, nullable=True)
    zone_id = Column(String(36), ForeignKey("zones.id"), nullable=False, index=True)
    type = Column(String(50), nullable=False)

    tier = Column(Integer, nullable=False, default=1)
    
    # Relationships
    zone = relationship("Zone", back_populates="entities")
    targeted_events = relationship("GameEvent", back_populates="target_entity", cascade="all, delete-orphan")
    
    __mapper_args__ = {
        "polymorphic_on": type,
        "polymorphic_identity": "entity",
    }
    
    def __repr__(self):
        return f"<Entity {self.id} - {self.name} ({self.type})>"
