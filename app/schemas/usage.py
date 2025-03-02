from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from datetime import date, datetime

class DailyUsageResponse(BaseModel):
    """Response with usage for a specific day"""
    date: str
    message_count: int
    ai_response_count: int
    message_limit: int
    messages_remaining: int

class UsageStatsResponse(BaseModel):
    """Response with comprehensive usage statistics"""
    is_premium: bool
    today: Dict[str, Any]
    totals: Dict[str, int]
    current: Dict[str, Any]
    recent_daily: List[DailyUsageResponse]
    features: Dict[str, bool]

class LimitsResponse(BaseModel):
    """Response with usage limits"""
    can_send_messages: bool
    messages_remaining_today: int
    is_premium: bool