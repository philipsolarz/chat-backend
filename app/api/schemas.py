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


# User schemas
class UserBase(BaseModel):
    email: EmailStr
    first_name: Optional[str] = None
    last_name: Optional[str] = None


class UserCreate(UserBase):
    password: str = Field(..., min_length=8)


class UserUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None


class UserResponse(UserBase):
    id: str
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


# Character schemas
class CharacterBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    is_public: bool = False


class CharacterCreate(CharacterBase):
    pass


class CharacterUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    is_public: Optional[bool] = None


class CharacterResponse(CharacterBase):
    id: str
    user_id: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class CharacterList(PaginatedResponse):
    items: List[CharacterResponse]


# Agent schemas
class AgentBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    system_prompt: Optional[str] = None


class AgentCreate(AgentBase):
    is_active: bool = True


class AgentUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    is_active: Optional[bool] = None


class AgentResponse(AgentBase):
    id: str
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class AgentList(PaginatedResponse):
    items: List[AgentResponse]


# Participant schemas
class ParticipantBase(BaseModel):
    character_id: str
    user_id: Optional[str] = None
    agent_id: Optional[str] = None


class ParticipantCreate(ParticipantBase):
    pass


class ParticipantResponse(ParticipantBase):
    id: str
    conversation_id: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class ParticipantDetailResponse(ParticipantResponse):
    character: CharacterResponse
    user: Optional[UserResponse] = None
    agent: Optional[AgentResponse] = None
    
    class Config:
        from_attributes = True


# Conversation schemas
class ConversationBase(BaseModel):
    title: Optional[str] = None


class ConversationCreate(ConversationBase):
    # Initial participants to add
    user_character_ids: List[str] = Field(..., min_items=1)  # User characters
    agent_character_ids: Optional[List[str]] = None  # Agent characters
    user_id: str  # Required for user-controlled characters


class ParticipantAddRequest(BaseModel):
    character_id: str
    user_id: Optional[str] = None
    agent_id: Optional[str] = None
    
    @validator('user_id', 'agent_id')
    def exclusive_controllers(cls, v, values):
        # Ensure exactly one of user_id or agent_id is provided
        if 'user_id' in values and 'agent_id' in values:
            if values['user_id'] is not None and values['agent_id'] is not None:
                raise ValueError('Only one of user_id or agent_id should be provided')
            if values['user_id'] is None and values['agent_id'] is None:
                raise ValueError('Either user_id or agent_id must be provided')
        return v


class ConversationUpdate(BaseModel):
    title: Optional[str] = None


class ConversationResponse(ConversationBase):
    id: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class ConversationDetailResponse(ConversationResponse):
    participants: List[ParticipantDetailResponse]
    
    class Config:
        from_attributes = True


class ConversationList(PaginatedResponse):
    items: List[ConversationResponse]


class ConversationSummaryResponse(BaseModel):
    id: str
    title: Optional[str] = None
    latest_message: Optional[str] = None
    latest_message_time: datetime
    latest_message_sender: Optional[str] = None
    total_participants: int
    user_participants: int
    agent_participants: int
    created_at: datetime
    updated_at: datetime


# Message schemas
class MessageCreate(BaseModel):
    content: str = Field(..., min_length=1)
    participant_id: str


class MessageResponse(BaseModel):
    id: str
    content: str
    conversation_id: str
    participant_id: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class MessageDetailResponse(MessageResponse):
    character_id: str
    character_name: str
    user_id: Optional[str] = None
    agent_id: Optional[str] = None
    is_ai: bool
    
    class Config:
        from_attributes = True


class MessageList(PaginatedResponse):
    items: List[MessageDetailResponse]


# Auth schemas
class SignUpRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    first_name: Optional[str] = None
    last_name: Optional[str] = None


class SignInRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    user_id: str
    email: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str

class ResendVerificationRequest(BaseModel):
    email: EmailStr
    redirect_url: Optional[str] = None

# AI response schemas
class AIResponse(BaseModel):
    message_id: str
    participant_id: str
    character_id: str
    character_name: str
    agent_id: str
    agent_name: str
    content: str
    created_at: str


class AIResponseList(BaseModel):
    responses: List[AIResponse]


# WebSocket message schemas
class WebSocketMessage(BaseModel):
    type: str  # e.g., "message", "typing", "read"
    content: Optional[str] = None
    participant_id: str
    conversation_id: str


# Search schemas
class SearchFilters(BaseModel):
    search_term: str = Field(..., min_length=1)
    include_characters: bool = True
    include_agents: bool = True
    include_conversations: bool = True
    include_messages: bool = False  # Default to False as it could be slow
    user_id: Optional[str] = None  # Limit to user's content
    limit_per_type: int = 5


class SearchResultItem(BaseModel):
    id: str
    type: str  # "character", "agent", "conversation", "message"
    name: Optional[str] = None  # For characters/agents
    title: Optional[str] = None  # For conversations
    content: Optional[str] = None  # For messages
    created_at: datetime


class SearchResults(BaseModel):
    characters: List[SearchResultItem] = []
    agents: List[SearchResultItem] = []
    conversations: List[SearchResultItem] = []
    messages: List[SearchResultItem] = []
    total_results: int

# Add these schemas to app/api/schemas.py

# World schemas
class WorldBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    genre: Optional[str] = None
    settings: Optional[str] = None
    default_prompt: Optional[str] = None
    is_public: bool = False


class WorldCreate(WorldBase):
    is_premium: bool = False


class PremiumWorldCreate(WorldBase):
    """Schema for initiating premium world creation (which requires payment)"""
    pass


class WorldUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    genre: Optional[str] = None
    settings: Optional[str] = None
    default_prompt: Optional[str] = None
    is_public: Optional[bool] = None
    is_premium: Optional[bool] = None


class WorldResponse(WorldBase):
    id: str
    owner_id: Optional[str] = None
    is_starter: bool
    is_premium: bool
    price: Optional[float] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class WorldDetailResponse(WorldResponse):
    member_count: int
    
    class Config:
        from_attributes = True


class WorldList(PaginatedResponse):
    items: List[WorldResponse]

# Zone schemas
class ZoneBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    zone_type: Optional[str] = None
    coordinates: Optional[str] = None
    properties: Optional[str] = None


class ZoneCreate(ZoneBase):
    world_id: str
    parent_zone_id: Optional[str] = None


class ZoneUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    zone_type: Optional[str] = None
    coordinates: Optional[str] = None
    properties: Optional[str] = None
    parent_zone_id: Optional[str] = None


class ZoneResponse(ZoneBase):
    id: str
    world_id: str
    parent_zone_id: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class ZoneDetailResponse(ZoneResponse):
    sub_zone_count: int
    character_count: int
    agent_count: int
    
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


# Update character schemas to include zone information
class CharacterCreate(CharacterBase):
    world_id: str
    zone_id: Optional[str] = None


class CharacterResponse(CharacterBase):
    id: str
    user_id: Optional[str] = None
    world_id: str
    zone_id: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


# Update agent schemas to include zone information
class AgentCreate(AgentBase):
    zone_id: Optional[str] = None


class AgentResponse(AgentBase):
    id: str
    is_active: bool
    zone_id: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True