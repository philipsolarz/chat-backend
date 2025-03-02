# app/models/agent.py
from sqlalchemy import JSON, Column, Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base
from app.models.entity import Entity, EntityType
from app.models.mixins import TimestampMixin, generate_uuid


class Agent(Base, TimestampMixin):
    """
    Model representing AI agents in the system (NPCs)
    Agents are dynamic entities that can participate in conversations
    """
    __tablename__ = "agents"
    
    id = Column(String(36), primary_key=True, default=generate_uuid, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)

    properties = Column(JSON, nullable=True)
    
    tier = Column(Integer, default=1)
    
    world_id = Column(String(36), ForeignKey("worlds.id"), nullable=True)
    zone_id = Column(String(36), ForeignKey("zones.id"), nullable=True)
    entity_id = Column(String(36), ForeignKey("entities.id"), nullable=True)
    character_id = Column(String(36), ForeignKey("characters.id"), nullable=True)

    world = relationship("World", back_populates="characters")
    zone = relationship("Zone", back_populates="characters")
    entity = relationship("Entity", back_populates="characters")
    character = relationship("Character", back_populates="agent")

    # Relationships - agent participations in conversations
    # conversation_participations = relationship(
    #     "ConversationParticipant",
    #     back_populates="agent",
    #     cascade="all, delete-orphan"
    # )
    
    def __repr__(self):
        return f"<Agent {self.id} - {self.name}>"