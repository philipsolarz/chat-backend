# app/models/agent.py
from sqlalchemy import Column, Integer, String, Text, JSON
from sqlalchemy.orm import relationship
from app.database import Base
from app.models.mixins import TimestampMixin, generate_uuid

class Agent(Base, TimestampMixin):
    __tablename__ = "agents"
    
    id = Column(String(36), primary_key=True, default=generate_uuid, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    properties = Column(JSON, nullable=True)
    tier = Column(Integer, default=1)
    
    # One-to-one relationship with the corresponding character record (for agent-controlled characters)
    character = relationship("Character", back_populates="agent", uselist=False)
    
    # Relationships for conversation participation
    conversation_participations = relationship("ConversationParticipant", back_populates="agent", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Agent {self.id} - {self.name}>"
