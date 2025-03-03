# app/models/character.py
from sqlalchemy import Column, JSON, String, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import relationship
from app.database import Base
from app.models.mixins import TimestampMixin
from app.models.entity import Entity
from app.models.enums import CharacterType

class Character(Entity):
    __tablename__ = "characters"
    id = Column(String(36), ForeignKey("entities.id"), primary_key=True)
    
    character_type = Column(SAEnum(CharacterType), nullable=False)
    settings = Column(JSON, nullable=True)
    player_id = Column(String(36), ForeignKey("players.id"), nullable=True)
    agent_id = Column(String(36), ForeignKey("agents.id"), nullable=True)
    
    # Relationships
    player = relationship("Player", back_populates="character")
    agent = relationship("Agent", back_populates="character", uselist=False)
    initiated_events = relationship("GameEvent", foreign_keys="[GameEvent.character_id]", back_populates="character", cascade="all, delete-orphan")
    event_participations = relationship("EventParticipant", back_populates="character", cascade="all, delete-orphan")
    conversation_participations = relationship("ConversationParticipant", back_populates="character", cascade="all, delete-orphan")
    
    __mapper_args__ = {
        "polymorphic_identity": "character",
    }
    
    def __repr__(self):
        return f"<Character {self.id} - {self.name} ({self.character_type})>"
