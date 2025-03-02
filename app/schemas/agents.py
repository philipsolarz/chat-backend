from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime

from app.schemas.base import PaginatedResponse

class AgentBase(BaseModel):
    """Base agent properties"""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None

class AgentCreate(AgentBase):
    """Properties required to create an agent"""
    zone_id: Optional[str] = None
    world_id: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None

class AgentUpdate(BaseModel):
    """Properties that can be updated"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None

class AgentResponse(AgentBase):
    """Response model with all agent properties"""
    id: str
    world_id: Optional[str] = None
    zone_id: Optional[str] = None
    entity_id: Optional[str] = None
    character_id: Optional[str] = None
    tier: int
    properties: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class AgentList(PaginatedResponse):
    """Paginated list of agents"""
    items: List[AgentResponse]