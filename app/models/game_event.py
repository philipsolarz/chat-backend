# app/models/game_event.py
from sqlalchemy import Boolean, Column, String, JSON, ForeignKey, Enum, Index
from sqlalchemy.orm import relationship
import enum

from app.database import Base
from app.models.mixins import TimestampMixin, generate_uuid


class EventType(str, enum.Enum):
    """Types of game events"""
    MESSAGE = "message"           # Chat messages
    MOVEMENT = "movement"         # Character movement between zones
    INTERACTION = "interaction"   # Character interacting with entities
    SYSTEM = "system"             # System announcements and notifications
    EMOTE = "emote"               # Character emotes and expressions
    QUEST = "quest"               # Quest related updates
    COMBAT = "combat"             # Combat actions and results
    TRADE = "trade"               # Trading between characters
    INVENTORY = "inventory"       # Inventory changes
    SKILL = "skill"               # Skill usage and learning


class EventScope(str, enum.Enum):
    """Scope of the event visibility"""
    PUBLIC = "public"    # Visible to all in the zone
    PRIVATE = "private"  # Visible only to specific participants
    GLOBAL = "global"    # Visible to all in the world


class GameEvent(Base, TimestampMixin):
    """Model representing any event that happens in the game"""
    __tablename__ = "game_events"
    
    id = Column(String(36), primary_key=True, default=generate_uuid, index=True)
    type = Column(Enum(EventType), nullable=False)
    scope = Column(Enum(EventScope), nullable=False, default=EventScope.PUBLIC)
    
    # Where the event happened
    world_id = Column(String(36), ForeignKey("worlds.id"), nullable=True)
    zone_id = Column(String(36), ForeignKey("zones.id"), nullable=True)
    
    # Who initiated the event
    character_id = Column(String(36), ForeignKey("characters.id"), nullable=True)
    
    # Optional target entity (character or object)
    target_entity_id = Column(String(36), ForeignKey("entities.id"), nullable=True)
    
    # Event data stored as JSON
    data = Column(JSON, nullable=False)
    
    # Relationships
    world = relationship("World", back_populates="events")
    zone = relationship("Zone", back_populates="events")
    character = relationship("Character", foreign_keys=[character_id], back_populates="initiated_events")
    target_entity = relationship("Entity", back_populates="targeted_events")
    
    # For private events, track who can see it
    event_participants = relationship("EventParticipant", back_populates="event", cascade="all, delete-orphan")
    
    # Indexes for efficient queries
    __table_args__ = (
        Index('ix_game_events_zone_created', "zone_id", "created_at"),
        Index('ix_game_events_character_created', "character_id", "created_at"),
    )
    
    def __repr__(self):
        return f"<GameEvent {self.id} - {self.type} in zone {self.zone_id}>"


class EventParticipant(Base, TimestampMixin):
    """Model tracking participants for private events"""
    __tablename__ = "event_participants"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    event_id = Column(String(36), ForeignKey("game_events.id"), nullable=False, index=True)
    character_id = Column(String(36), ForeignKey("characters.id"), nullable=False, index=True)
    
    # Whether the participant has read the event
    is_read = Column(Boolean, default=False)
    
    # Relationships
    event = relationship("GameEvent", back_populates="event_participants")
    character = relationship("Character", back_populates="event_participations")
    
    __table_args__ = (
        Index('ix_event_participants_event_character', "event_id", "character_id", unique=True),
    )
    
    def __repr__(self):
        return f"<EventParticipant {self.id} - Event: {self.event_id}, Character: {self.character_id}>"