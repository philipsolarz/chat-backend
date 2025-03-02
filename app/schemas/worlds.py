# app/schemas/worlds.py
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime

from app.schemas.base import PaginatedResponse

class WorldBase(BaseModel):
    """Base world properties"""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None
    is_official: bool = False
    is_private: bool = False

class WorldCreate(WorldBase):
    """Properties required to create a world"""
    pass

class WorldUpdate(BaseModel):
    """Properties that can be updated"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None
    is_official: Optional[bool] = None
    is_private: Optional[bool] = None

class WorldResponse(WorldBase):
    """Response model with all world properties"""
    id: str
    owner_id: Optional[str] = None
    tier: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class WorldList(PaginatedResponse):
    """Paginated list of conversations"""
    items: List[WorldResponse]