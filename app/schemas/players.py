from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime

class PlayerBase(BaseModel):
    """Base player properties"""
    email: EmailStr
    first_name: Optional[str] = None
    last_name: Optional[str] = None

class PlayerCreate(PlayerBase):
    """Properties required to create a player"""
    password: str = Field(..., min_length=8)

class PlayerUpdate(BaseModel):
    """Properties that can be updated"""
    email: Optional[EmailStr] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None

class PlayerResponse(PlayerBase):
    """Response model with all player properties"""
    id: str
    is_active: bool
    is_premium: bool
    premium_since: Optional[datetime] = None
    is_admin: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True