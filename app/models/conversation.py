# app/models/conversation.py
from sqlalchemy import Column, String, ForeignKey, Text, Boolean, CheckConstraint
from sqlalchemy.orm import relationship

from app.database import Base
from app.models.mixins import TimestampMixin, generate_uuid


class Conversation(Base, TimestampMixin):
    """Model representing a chat conversation"""
    __tablename__ = "conversations"
    
    id = Column(String(36), primary_key=True, default=generate_uuid, index=True)
    title = Column(String(100), nullable=True)  # Optional title for the conversation
    
    # Relationships
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")
    participants = relationship("ConversationParticipant", back_populates="conversation", cascade="all, delete-orphan")


class ConversationParticipant(Base, TimestampMixin):
    """
    Join table for participants in conversations
    
    Each participant has:
    1. A character (required) - the persona in the conversation
    2. Either a user OR an agent controlling the character (mutually exclusive)
    """
    __tablename__ = "conversation_participants"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    conversation_id = Column(String(36), ForeignKey("conversations.id"), nullable=False, index=True)
    
    # The character being used in the conversation (required)
    character_id = Column(String(36), ForeignKey("characters.id"), nullable=False)
    
    # Either user_id or agent_id must be set, but not both
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    agent_id = Column(String(36), ForeignKey("agents.id"), nullable=True)
    
    # Ensure that exactly one of user_id or agent_id is set
    __table_args__ = (
        CheckConstraint('(user_id IS NULL) != (agent_id IS NULL)', 
                        name='check_mutually_exclusive_participant'),
    )
    
    # Relationships
    conversation = relationship("Conversation", back_populates="participants")
    character = relationship("Character", back_populates="conversation_participations")
    user = relationship("User", back_populates="conversation_participations")
    agent = relationship("Agent", back_populates="conversation_participations")