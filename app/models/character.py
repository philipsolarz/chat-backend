# app/models/character.py
from sqlalchemy import Column, String, Text, ForeignKey, Boolean
from sqlalchemy.orm import relationship

from app.database import Base
from app.models.mixins import TimestampMixin, generate_uuid


class Character(Base, TimestampMixin):
    """
    Model representing characters in the system
    Characters can be controlled by users (private) or available to agents (public)
    """
    __tablename__ = "characters"
    
    id = Column(String(36), primary_key=True, default=generate_uuid, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)  # Includes personality description
    
    # Whether the character is publicly available for agents
    is_public = Column(Boolean, default=False)
    
    # User relationship (can be null for system-created public characters)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="characters")
    
    # Participation in conversations
    conversation_participations = relationship(
        "ConversationParticipant",
        back_populates="character",
        cascade="all, delete-orphan"
    )