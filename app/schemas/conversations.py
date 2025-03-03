from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
from app.schemas.base import PaginatedResponse

class ConversationBase(BaseModel):
    title: Optional[str] = Field(None, max_length=100)

class ConversationCreate(BaseModel):
    title: Optional[str] = Field(None, max_length=100)
    user_character_ids: List[str] = Field(..., min_items=1)
    agent_character_ids: Optional[List[str]] = None

class ConversationUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=100)

class ConversationResponse(ConversationBase):
    id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class ParticipantAddRequest(BaseModel):
    character_id: str
    user_id: Optional[str] = None
    agent_id: Optional[str] = None

class ParticipantResponse(BaseModel):
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
    character: Dict[str, Any]
    user: Optional[Dict[str, Any]] = None
    agent: Optional[Dict[str, Any]] = None

class ConversationDetailResponse(ConversationResponse):
    participants: List[ParticipantDetailResponse]

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

class ConversationList(PaginatedResponse):
    items: List[ConversationResponse]
