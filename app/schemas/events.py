from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
import enum

class EventType(str, enum.Enum):
    """Types of game events"""
    MESSAGE = "message"
    MOVEMENT = "movement"
    INTERACTION = "interaction"
    SYSTEM = "system"
    EMOTE = "emote"
    QUEST = "quest"
    COMBAT = "combat"
    TRADE = "trade"
    INVENTORY = "inventory"
    SKILL = "skill"

class EventScope(str, enum.Enum):
    """Scope of the event visibility"""
    PUBLIC = "public"
    PRIVATE = "private"
    GLOBAL = "global"

class EventParticipantBase(BaseModel):
    """Base event participant properties"""
    character_id: str
    is_read: bool = False

class EventParticipantResponse(EventParticipantBase):
    """Response model with event participant properties"""
    id: str
    event_id: str
    created_at: datetime

    class Config:
        from_attributes = True

class GameEventBase(BaseModel):
    """Base game event properties"""
    type: str
    data: Dict[str, Any]
    character_id: Optional[str] = None
    zone_id: Optional[str] = None
    world_id: Optional[str] = None
    target_entity_id: Optional[str] = None
    scope: str = "public"

class GameEventCreate(GameEventBase):
    """Properties required to create a game event"""
    participant_ids: Optional[List[str]] = None

class GameEventResponse(GameEventBase):
    """Response model with game event properties"""
    id: str
    created_at: datetime
    participants: Optional[List[EventParticipantResponse]] = None
    character_name: Optional[str] = None
    target_entity_name: Optional[str] = None

    class Config:
        from_attributes = True

class MessageEventCreate(BaseModel):
    """Properties required to create a message event"""
    content: str
    character_id: str
    zone_id: Optional[str] = None
    world_id: Optional[str] = None
    target_character_id: Optional[str] = None
    scope: str = "public"

class ZoneEventsRequest(BaseModel):
    """Request for zone events"""
    character_id: str
    event_types: Optional[List[str]] = None
    limit: int = 50
    before: Optional[datetime] = None

class PrivateEventsRequest(BaseModel):
    """Request for private events"""
    character_id: str
    other_character_id: Optional[str] = None
    event_types: Optional[List[str]] = None
    limit: int = 50
    before: Optional[datetime] = None

class MarkEventReadRequest(BaseModel):
    """Request to mark an event as read"""
    character_id: str

class UnreadCountResponse(BaseModel):
    """Response with unread event count"""
    character_id: str
    unread_count: int

class ConversationSummary(BaseModel):
    """Summary of conversation events"""
    character_id: str
    character_name: str
    latest_message: str
    latest_timestamp: datetime
    unread_count: int