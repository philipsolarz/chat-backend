# app/models/agent.py
from sqlalchemy import Column, Boolean, Text
from sqlalchemy.orm import relationship

from app.models.entity import Entity, EntityType


class Agent(Entity):
    """
    Model representing AI agents in the system (NPCs)
    Agents are dynamic entities that can participate in conversations
    """
    # Agent system prompt (AI instructions)
    system_prompt = Column(Text, nullable=True)
    
    # Whether the agent is enabled
    is_active = Column(Boolean, default=True)
    
    __mapper_args__ = {
        'polymorphic_identity': EntityType.AGENT
    }
    
    # Relationships - agent participations in conversations
    conversation_participations = relationship(
        "ConversationParticipant",
        back_populates="agent",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self):
        return f"<Agent {self.id} - {self.name}>"