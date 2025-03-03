from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
from app.schemas.base import PaginatedResponse

class ZoneBase(BaseModel):
    """Base zone properties"""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    properties: Optional[Dict[str, Any]] = None  # renamed from settings

class ZoneCreate(ZoneBase):
    """Properties required to create a zone"""
    world_id: str
    parent_zone_id: Optional[str] = None

class ZoneUpdate(BaseModel):
    """Properties that can be updated"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    properties: Optional[Dict[str, Any]] = None  # renamed from settings
    parent_zone_id: Optional[str] = None

class ZoneResponse(ZoneBase):
    """Response model with all zone properties"""
    id: str
    world_id: str
    parent_zone_id: Optional[str] = None
    tier: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class ZoneDetailResponse(ZoneResponse):
    """Detailed zone response including counts"""
    sub_zone_count: int
    entity_count: int
    entity_limit: int
    remaining_capacity: int

class ZoneTreeNode(ZoneResponse):
    """Recursive zone node for hierarchy"""
    sub_zones: List['ZoneTreeNode'] = []

ZoneTreeNode.update_forward_refs()

class ZoneHierarchyResponse(BaseModel):
    """Response containing the zone hierarchy"""
    zones: List[ZoneTreeNode]

class ZoneList(PaginatedResponse):
    """Paginated list of zones"""
    items: List[ZoneResponse]
