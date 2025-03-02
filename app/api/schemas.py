# app/api/schemas.py
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, EmailStr, Field, validator
from datetime import datetime
import re

# Base response model with pagination info
class PaginatedResponse(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int

# World schemas
class WorldBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None

class WorldCreate(WorldBase):
    pass

class WorldUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None

class WorldResponse(WorldBase):
    id: str
    owner_id: Optional[str] = None
    zone_limit: int
    zone_limit_upgrades: int
    created_at: datetime
    
    class Config:
        from_attributes = True

class WorldList(PaginatedResponse):
    items: List[WorldResponse]

# Zone schemas
class ZoneBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None

class ZoneCreate(ZoneBase):
    world_id: str
    parent_zone_id: Optional[str] = None

class ZoneUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None
    parent_zone_id: Optional[str] = None

class ZoneResponse(ZoneBase):
    id: str
    world_id: str
    parent_zone_id: Optional[str] = None
    entity_limit: int
    entity_limit_upgrades: int
    created_at: datetime
    
    class Config:
        from_attributes = True

class ZoneDetailResponse(ZoneResponse):
    sub_zone_count: int
    entity_count: int
    
    class Config:
        from_attributes = True

class ZoneList(PaginatedResponse):
    items: List[ZoneResponse]

class ZoneTreeNode(ZoneResponse):
    sub_zones: List['ZoneTreeNode'] = []
    
    class Config:
        from_attributes = True

# Add this to enable recursive typing for ZoneTreeNode
ZoneTreeNode.update_forward_refs()

class ZoneHierarchyResponse(BaseModel):
    zones: List[ZoneTreeNode]

# Entity schemas
class EntityBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None

class EntityType(str):
    AGENT = "agent"
    OBJECT = "object"
    CHARACTER = "character"

class EntityResponse(EntityBase):
    id: str
    type: str
    zone_id: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

class EntityList(PaginatedResponse):
    items: List[EntityResponse]

# Object schemas
class ObjectBase(EntityBase):
    is_interactive: bool = False
    object_type: Optional[str] = None

class ObjectCreate(ObjectBase):
    zone_id: Optional[str] = None

class ObjectUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None
    is_interactive: Optional[bool] = None
    object_type: Optional[str] = None

class ObjectResponse(ObjectBase, EntityResponse):
    class Config:
        from_attributes = True

class ObjectList(PaginatedResponse):
    items: List[ObjectResponse]

# Updated Agent schemas
class AgentBase(EntityBase):
    system_prompt: Optional[str] = None
    is_active: bool = True

class AgentCreate(AgentBase):
    zone_id: Optional[str] = None

class AgentUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None
    system_prompt: Optional[str] = None
    is_active: Optional[bool] = None

class AgentResponse(AgentBase, EntityResponse):
    class Config:
        from_attributes = True

class AgentList(PaginatedResponse):
    items: List[AgentResponse]

# Character schemas (if needed)
class CharacterBase(EntityBase):
    template: Optional[str] = None
    is_template: bool = False
    is_public: bool = False

class CharacterCreate(CharacterBase):
    user_id: Optional[str] = None
    zone_id: Optional[str] = None
    world_id: str

class CharacterUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None
    template: Optional[str] = None
    is_template: Optional[bool] = None
    is_public: Optional[bool] = None

class CharacterResponse(CharacterBase, EntityResponse):
    user_id: Optional[str] = None
    world_id: str
    
    class Config:
        from_attributes = True

class CharacterList(PaginatedResponse):
    items: List[CharacterResponse]

# Game Event schemas
class EventParticipantBase(BaseModel):
    """Schema for event participants"""
    character_id: str
    is_read: bool = False


class EventParticipantResponse(EventParticipantBase):
    """Response schema for event participants"""
    event_id: str
    id: str
    created_at: datetime

    class Config:
        from_attributes = True


class GameEventBase(BaseModel):
    """Base schema for game events"""
    type: str
    data: Dict[str, Any]
    character_id: Optional[str] = None
    zone_id: Optional[str] = None
    world_id: Optional[str] = None
    target_entity_id: Optional[str] = None
    scope: str = "public"


class GameEventCreate(GameEventBase):
    """Schema for creating a game event"""
    participant_ids: Optional[List[str]] = None


class GameEventResponse(GameEventBase):
    """Response schema for game events"""
    id: str
    created_at: datetime
    participants: Optional[List[EventParticipantResponse]] = None
    
    # Additional fields populated based on relationships
    character_name: Optional[str] = None
    target_entity_name: Optional[str] = None

    class Config:
        from_attributes = True


class MessageEventCreate(BaseModel):
    """Schema for creating a message event"""
    content: str
    character_id: str
    zone_id: Optional[str] = None
    world_id: Optional[str] = None
    target_character_id: Optional[str] = None
    scope: str = "public"


class ZoneEventsRequest(BaseModel):
    """Schema for requesting zone events"""
    character_id: str
    event_types: Optional[List[str]] = None
    limit: int = 50
    before: Optional[datetime] = None


class PrivateEventsRequest(BaseModel):
    """Schema for requesting private events"""
    character_id: str
    other_character_id: Optional[str] = None
    event_types: Optional[List[str]] = None
    limit: int = 50
    before: Optional[datetime] = None


class MarkEventReadRequest(BaseModel):
    """Schema for marking an event as read"""
    character_id: str


class UnreadCountResponse(BaseModel):
    """Schema for unread event count response"""
    character_id: str
    unread_count: int


class ConversationSummary(BaseModel):
    """Schema for conversation summary"""
    character_id: str
    character_name: str
    latest_message: str
    latest_timestamp: datetime
    unread_count: int