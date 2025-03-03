from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum

from app.schemas import PaginatedResponse

class CharacterType(str, Enum):
    """Types of characters"""
    PLAYER = "player"
    AGENT = "agent"

class CharacterBase(BaseModel):
    """Base character properties"""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None

class CharacterCreate(CharacterBase):
    """Properties required to create a character"""
    # world_id: str
    # zone_id: Optional[str] = None
    user_id: Optional[str] = None

class CharacterUpdate(BaseModel):
    """Properties that can be updated"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None

class CharacterResponse(CharacterBase):
    """Response model with all character properties"""
    id: str
    player_id: Optional[str] = None
    # world_id: str
    # zone_id: Optional[str] = None
    entity_id: Optional[str] = None
    type: CharacterType
    tier: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
        
class CharacterList(PaginatedResponse):
    """Paginated list of characters"""
    items: List[CharacterResponse]