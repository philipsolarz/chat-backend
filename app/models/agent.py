# app/models/agent.py
from sqlalchemy import Column, String, Text, Boolean
from sqlalchemy.orm import relationship

from app.database import Base
from app.models.mixins import TimestampMixin, generate_uuid


class Agent(Base, TimestampMixin):
    """
    Model representing AI agents in the system
    Agents use characters to participate in conversations
    """
    __tablename__ = "agents"
    
    id = Column(String(36), primary_key=True, default=generate_uuid, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    
    # Agent system prompt (AI instructions)
    system_prompt = Column(Text, nullable=True)
    
    # Whether the agent is enabled
    is_active = Column(Boolean, default=True)
    
    # Relationships - agent participations in conversations
    conversation_participations = relationship(
        "ConversationParticipant",
        back_populates="agent",
        cascade="all, delete-orphan"
    )