# app/schemas/character.py
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum

from app.schemas import PaginatedResponse

class CharacterType(str, Enum):
    PLAYER = "player"
    AGENT = "agent"

class CharacterBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None

class CharacterCreate(CharacterBase):
    """
    Fields required to create a character.
    The client must pass the zone_id where the character should be created.
    """
    zone_id: Optional[str] = None
    user_id: Optional[str] = None  # Usually taken from auth

class CharacterUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None

class CharacterResponse(CharacterBase):
    id: str
    player_id: Optional[str] = None
    zone_id: str  # Inherited from Entity
    character_type: CharacterType
    tier: int
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True

class CharacterList(PaginatedResponse):
    items: List[CharacterResponse]
