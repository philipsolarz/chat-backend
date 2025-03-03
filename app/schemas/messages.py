# app/schemas/message.py
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime

from app.schemas.base import PaginatedResponse

class MessageBase(BaseModel):
    """Base message properties."""
    content: str = Field(..., min_length=1)

class MessageCreate(MessageBase):
    """Properties required to create a message."""
    participant_id: str

class MessageResponse(MessageBase):
    """Response model with basic message properties."""
    id: str
    conversation_id: str
    participant_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class MessageDetailResponse(MessageResponse):
    """Detailed message response including sender information."""
    character_id: str
    character_name: str
    user_id: Optional[str] = None
    agent_id: Optional[str] = None
    is_ai: bool

class MessageList(PaginatedResponse):
    """Paginated list of messages."""
    items: List[MessageDetailResponse]
