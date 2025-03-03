from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
from app.schemas.base import PaginatedResponse

class WorldBase(BaseModel):
    """Base world properties"""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    # Externally we use "settings" but internally the model uses "properties"
    settings: Optional[Dict[str, Any]] = Field(None, alias="properties")
    is_official: bool = False
    is_private: bool = False

    class Config:
        # Allow population by the field name and alias
        allow_population_by_field_name = True

class WorldCreate(WorldBase):
    """Properties required to create a world"""
    pass

class WorldUpdate(BaseModel):
    """Properties that can be updated"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    settings: Optional[Dict[str, Any]] = Field(None, alias="properties")
    is_official: Optional[bool] = None
    is_private: Optional[bool] = None

    class Config:
        allow_population_by_field_name = True

class WorldResponse(WorldBase):
    """Response model with all world properties"""
    id: str
    owner_id: Optional[str] = None
    tier: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
        allow_population_by_field_name = True

class WorldList(PaginatedResponse):
    """Paginated list of worlds"""
    items: List[WorldResponse]
