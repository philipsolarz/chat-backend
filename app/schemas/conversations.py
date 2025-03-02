from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime

from app.schemas.base import PaginatedResponse

class ConversationBase(BaseModel):
    """Base conversation properties"""
    title: Optional[str] = Field(None, max_length=100)

class ConversationCreate(BaseModel):
    """Properties required to create a conversation"""
    title: Optional[str] = Field(None, max_length=100)
    user_character_ids: List[str] = Field(..., min_items=1)
    agent_character_ids: Optional[List[str]] = None

class ConversationUpdate(BaseModel):
    """Properties that can be updated"""
    title: Optional[str] = Field(None, max_length=100)

class ConversationResponse(ConversationBase):
    """Response model with conversation properties"""
    id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class ParticipantAddRequest(BaseModel):
    """Request to add a participant to conversation"""
    character_id: str
    user_id: Optional[str] = None
    agent_id: Optional[str] = None

class ParticipantResponse(BaseModel):
    """Response with participant properties"""
    id: str
    conversation_id: str
    character_id: str
    user_id: Optional[str] = None
    agent_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class ParticipantDetailResponse(ParticipantResponse):
    """Detailed participant response with related objects"""
    character: Dict[str, Any]
    user: Optional[Dict[str, Any]] = None
    agent: Optional[Dict[str, Any]] = None

class ConversationDetailResponse(ConversationResponse):
    """Detailed conversation response with participants"""
    participants: List[ParticipantDetailResponse]

class ConversationSummaryResponse(BaseModel):
    """Summary of a conversation for listing"""
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

class ConversationList(PaginatedResponse):
    """Paginated list of conversations"""
    items: List[ConversationResponse]