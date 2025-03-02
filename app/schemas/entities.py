from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
import enum

from app.schemas.base import PaginatedResponse

class EntityType(str, enum.Enum):
    """Types of entities that can exist in zones"""
    CHARACTER = "character"
    OBJECT = "object"

class EntityBase(BaseModel):
    """Base entity properties"""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    type: EntityType

class EntityResponse(EntityBase):
    """Response model with all entity properties"""
    id: str
    world_id: Optional[str] = None
    zone_id: Optional[str] = None
    properties: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class EntityList(PaginatedResponse):
    """Paginated list of entities"""
    items: List[EntityResponse]