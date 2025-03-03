from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime
import enum

class EventType(str, enum.Enum):
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
    PUBLIC = "public"
    PRIVATE = "private"
    GLOBAL = "global"

class EventParticipantBase(BaseModel):
    character_id: str
    is_read: bool = False

class EventParticipantResponse(EventParticipantBase):
    id: str
    event_id: str
    created_at: datetime

    class Config:
        orm_mode = True

class GameEventBase(BaseModel):
    type: EventType
    data: Dict[str, Any]
    character_id: Optional[str] = None
    zone_id: Optional[str] = None
    world_id: Optional[str] = None
    target_entity_id: Optional[str] = None
    scope: EventScope = EventScope.PUBLIC

class GameEventCreate(GameEventBase):
    participant_ids: Optional[List[str]] = None

class GameEventResponse(GameEventBase):
    id: str
    created_at: datetime
    participants: Optional[List[EventParticipantResponse]] = None
    character_name: Optional[str] = None
    target_entity_name: Optional[str] = None

    class Config:
        orm_mode = True

class MessageEventCreate(BaseModel):
    content: str
    character_id: str
    zone_id: Optional[str] = None
    world_id: Optional[str] = None
    target_character_id: Optional[str] = None
    scope: EventScope = EventScope.PUBLIC

class ZoneEventsRequest(BaseModel):
    character_id: str
    event_types: Optional[List[EventType]] = None
    limit: int = 50
    before: Optional[datetime] = None

class PrivateEventsRequest(BaseModel):
    character_id: str
    other_character_id: Optional[str] = None
    event_types: Optional[List[EventType]] = None
    limit: int = 50
    before: Optional[datetime] = None

class MarkEventReadRequest(BaseModel):
    character_id: str

class UnreadCountResponse(BaseModel):
    character_id: str
    unread_count: int

class ConversationSummary(BaseModel):
    character_id: str
    character_name: str
    latest_message: str
    latest_timestamp: datetime
    unread_count: int
