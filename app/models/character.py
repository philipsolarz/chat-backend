# app/models/character.py
import enum
from sqlalchemy import JSON, Column, Integer, String, Text, ForeignKey, Boolean, Enum
from sqlalchemy.orm import relationship

from app.database import Base
from app.models.entity import Entity, EntityType
from app.models.mixins import TimestampMixin, generate_uuid

class CharacterType(str, enum.Enum):
    """Types of characters"""
    PLAYER = "player"
    AGENT = "agent"

class Character(Base, TimestampMixin):
    """
    Model representing characters in the system
    Characters can be controlled by players or agents.
    """

    __tablename__ = "characters"
    
    id = Column(String(36), primary_key=True, default=generate_uuid, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)

    type = Column(Enum(CharacterType), nullable=False)
    
    # JSON settings for object-specific properties
    settings = Column(JSON, nullable=True)
    
    tier = Column(Integer, default=1)

    world_id = Column(String(36), ForeignKey("worlds.id"), nullable=True)
    zone_id = Column(String(36), ForeignKey("zones.id"), nullable=True)
    entity_id = Column(String(36), ForeignKey("entities.id"), nullable=True)
    player_id = Column(String(36), ForeignKey("players.id"), nullable=True)
    agent_id = Column(String(36), ForeignKey("agents.id"), nullable=True)

    world = relationship("World", back_populates="characters")
    zone = relationship("Zone", back_populates="characters")
    entity = relationship("Entity", back_populates="characters")

    player = relationship("Zone", back_populates="characters")
    agent = relationship("Zone", back_populates="character")

    # Participation in conversations
    # conversation_participations = relationship(
    #     "ConversationParticipant",
    #     back_populates="character",
    #     cascade="all, delete-orphan"
    # )
    
    def __repr__(self):
        return f"<Character {self.id} - {self.name}>"