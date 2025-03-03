# app/models/conversation.py
from sqlalchemy import Column, String, ForeignKey, Text, CheckConstraint
from sqlalchemy.orm import relationship
from app.database import Base
from app.models.mixins import TimestampMixin, generate_uuid

class Conversation(Base, TimestampMixin):
    __tablename__ = "conversations"
    
    id = Column(String(36), primary_key=True, default=generate_uuid, index=True)
    title = Column(String(100), nullable=True)
    
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")
    participants = relationship("ConversationParticipant", back_populates="conversation", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Conversation {self.id} - {self.title}>"

class ConversationParticipant(Base, TimestampMixin):
    __tablename__ = "conversation_participants"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    conversation_id = Column(String(36), ForeignKey("conversations.id"), nullable=False, index=True)
    character_id = Column(String(36), ForeignKey("characters.id"), nullable=False)
    user_id = Column(String(36), ForeignKey("players.id"), nullable=True)
    agent_id = Column(String(36), ForeignKey("agents.id"), nullable=True)
    
    __table_args__ = (
        CheckConstraint('(user_id IS NULL) != (agent_id IS NULL)', name='check_mutually_exclusive_participant'),
    )
    
    conversation = relationship("Conversation", back_populates="participants")
    character = relationship("Character", back_populates="conversation_participations")
    player = relationship("Player", back_populates="conversation_participations")
    agent = relationship("Agent", back_populates="conversation_participations")
    
    def __repr__(self):
        return f"<ConversationParticipant {self.id} - Conversation: {self.conversation_id}>"
