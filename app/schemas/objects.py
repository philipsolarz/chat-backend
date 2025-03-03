from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
import enum

from app.schemas.base import PaginatedResponse

class ObjectType(str, enum.Enum):
    """Types of objects"""
    GENERIC = "generic"

class ObjectBase(BaseModel):
    """Base object properties"""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None

class ObjectCreate(ObjectBase):
    """Properties required to create an object"""
    # zone_id: Optional[str] = None
    # world_id: Optional[str] = None

class ObjectUpdate(BaseModel):
    """Properties that can be updated"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None

class ObjectResponse(ObjectBase):
    """Response model with all object properties"""
    id: str
    # world_id: Optional[str] = None
    # zone_id: Optional[str] = None
    entity_id: Optional[str] = None
    type: ObjectType
    properties: Optional[Dict[str, Any]] = None
    tier: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class ObjectList(PaginatedResponse):
    """Paginated list of conversations"""
    items: List[ObjectResponse]