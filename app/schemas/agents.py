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
    zone_id: Optional[str] = None  # Required to place the agent's character in a zone
    settings: Optional[Dict[str, Any]] = None

class AgentUpdate(BaseModel):
    """Properties that can be updated"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None
    zone_id: Optional[str] = None  # Allow moving the agent by updating the associated character's zone

class AgentResponse(AgentBase):
    """Response model with all agent properties"""
    id: str
    character_id: Optional[str] = None  # Derived from the associated Character
    zone_id: Optional[str] = None       # Derived from agent.character.zone_id
    tier: int
    properties: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True

class AgentList(PaginatedResponse):
    """Paginated list of agents"""
    items: List[AgentResponse]
