# app/models/character.py
from sqlalchemy import Column, String, Text, ForeignKey, Boolean
from sqlalchemy.orm import relationship

from app.models.entity import Entity, EntityType


class Character(Entity):
    """
    Model representing characters in the system
    Characters can be controlled by users (private) or available to agents (public)
    """
    # Character-specific fields
    template = Column(Text, nullable=True)  # Character template for AI voice
    is_template = Column(Boolean, default=False)  # Whether this is a template character
    
    # Whether the character is publicly available for agents
    is_public = Column(Boolean, default=False)
    
    # User relationship (can be null for system-created public characters)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    
    # World relationship
    world_id = Column(String(36), ForeignKey("worlds.id"), nullable=True)
    
    __mapper_args__ = {
        'polymorphic_identity': EntityType.CHARACTER
    }
    
    # Relationships
    user = relationship("User", back_populates="characters")
    world = relationship("World", back_populates="characters")
    
    # Participation in conversations
    conversation_participations = relationship(
        "ConversationParticipant",
        back_populates="character",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self):
        return f"<Character {self.id} - {self.name}>"