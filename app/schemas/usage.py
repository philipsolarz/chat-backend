# app/schemas/usage.py
from typing import List, Dict, Any
from pydantic import BaseModel

class DailyUsageResponse(BaseModel):
    """Response model for usage on a specific day."""
    date: str
    message_count: int
    ai_response_count: int
    message_limit: int
    messages_remaining: int

class UsageStatsResponse(BaseModel):
    """Comprehensive usage statistics response."""
    is_premium: bool
    today: Dict[str, Any]
    totals: Dict[str, int]
    current: Dict[str, Any]
    recent_daily: List[DailyUsageResponse]
    features: Dict[str, bool]

class LimitsResponse(BaseModel):
    """Response model for current usage limits and remaining capacity."""
    is_premium: bool
    limits: Dict[str, Dict[str, int]]
    premium_features: Dict[str, bool]
