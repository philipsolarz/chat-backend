# app/api/v1/usage.py
from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Dict, Any, Optional
from datetime import date
from app.database import get_db
from app.api.auth import get_current_user
from app.api.dependencies import get_service
from app.models.player import Player as User
from app.services.usage_service import UsageService
from app.schemas.usage import DailyUsageResponse, UsageStatsResponse, LimitsResponse
from app.config import get_settings

router = APIRouter()


@router.get("/stats", response_model=UsageStatsResponse)
async def get_usage_stats(
    current_user: User = Depends(get_current_user),
    usage_service: UsageService = Depends(get_service(UsageService))
):
    """
    Get comprehensive usage statistics for the current user.
    
    Returns detailed stats including limits, totals, and recent daily usage.
    """
    stats = usage_service.get_usage_stats(current_user.id)
    return stats


@router.get("/daily", response_model=DailyUsageResponse)
async def get_daily_usage(
    date_str: Optional[str] = Query(
        None, description="Date in YYYY-MM-DD format (defaults to today)"
    ),
    current_user: User = Depends(get_current_user),
    usage_service: UsageService = Depends(get_service(UsageService))
):
    """
    Get daily usage for a specified date.
    
    Returns usage details including message counts and remaining limits.
    """
    usage_date = None
    if date_str:
        try:
            usage_date = date.fromisoformat(date_str)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid date format. Use YYYY-MM-DD"
            )
    
    usage = usage_service.get_or_create_daily_usage(current_user.id, usage_date)
    
    # Get message limit from settings based on premium status.
    settings = get_settings()
    is_premium = usage_service.payment_service.is_premium(current_user.id)
    daily_limit = settings.PREMIUM_MESSAGES_PER_DAY if is_premium else settings.FREE_MESSAGES_PER_DAY
    
    return DailyUsageResponse(
        date=usage.date.isoformat(),
        message_count=usage.message_count,
        ai_response_count=usage.ai_response_count,
        message_limit=daily_limit,
        messages_remaining=max(0, daily_limit - usage.message_count)
    )


@router.get("/weekly", response_model=Dict[str, Any])
async def get_weekly_usage(
    current_user: User = Depends(get_current_user),
    usage_service: UsageService = Depends(get_service(UsageService))
):
    """
    Get usage statistics for the last 7 days.
    
    Returns daily message counts and premium status.
    """
    stats = usage_service.get_usage_stats(current_user.id)
    return {"recent_daily": stats["recent_daily"], "is_premium": stats["is_premium"]}


@router.get("/limits", response_model=LimitsResponse)
async def get_usage_limits(
    current_user: User = Depends(get_current_user),
    usage_service: UsageService = Depends(get_service(UsageService))
):
    """
    Get current usage limits and remaining capacity.
    
    Returns limits for messages per day, conversations, and characters,
    along with premium feature details.
    """
    is_premium = usage_service.payment_service.is_premium(current_user.id)
    summary = usage_service.get_or_create_usage_summary(current_user.id)
    daily_usage = usage_service.get_or_create_daily_usage(current_user.id)
    settings = get_settings()
    
    daily_limit = settings.PREMIUM_MESSAGES_PER_DAY if is_premium else settings.FREE_MESSAGES_PER_DAY
    conversation_limit = settings.PREMIUM_CONVERSATIONS_LIMIT if is_premium else settings.FREE_CONVERSATIONS_LIMIT
    character_limit = settings.PREMIUM_CHARACTERS_LIMIT if is_premium else settings.FREE_CHARACTERS_LIMIT
    
    limits = {
        "messages_per_day": {
            "limit": daily_limit,
            "used": daily_usage.message_count,
            "remaining": max(0, daily_limit - daily_usage.message_count)
        },
        "conversations": {
            "limit": conversation_limit,
            "used": summary.active_conversations,
            "remaining": max(0, conversation_limit - summary.active_conversations)
        },
        "characters": {
            "limit": character_limit,
            "used": summary.active_characters,
            "remaining": max(0, character_limit - summary.active_characters)
        }
    }
    
    premium_features = {
        "can_make_public_characters": is_premium
    }
    
    return LimitsResponse(
        is_premium=is_premium,
        limits=limits,
        premium_features=premium_features
    )
