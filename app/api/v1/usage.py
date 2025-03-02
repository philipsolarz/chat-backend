# app/api/v1/usage.py
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Dict, Any
from datetime import date, timedelta

from app.database import get_db
from app.api.auth import get_current_user
from app.api.dependencies import get_service
from app.models.player import Player as User
from app.services.usage_service import UsageService

router = APIRouter()


@router.get("/stats", response_model=Dict[str, Any])
async def get_usage_stats(
    current_user: User = Depends(get_current_user),
    usage_service: UsageService = Depends(get_service(UsageService))
):
    """
    Get comprehensive usage statistics for the current user
    
    Returns detailed stats including limits and usage
    """
    stats = usage_service.get_usage_stats(current_user.id)
    return stats


@router.get("/daily", response_model=Dict[str, Any])
async def get_daily_usage(
    date_str: str = Query(None, description="Date in YYYY-MM-DD format (defaults to today)"),
    current_user: User = Depends(get_current_user),
    usage_service: UsageService = Depends(get_service(UsageService))
):
    """
    Get daily usage for a specific date
    
    Returns message counts and limits for the specified date
    """
    # Parse date if provided, otherwise use today
    usage_date = None
    if date_str:
        try:
            usage_date = date.fromisoformat(date_str)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid date format. Use YYYY-MM-DD"
            )
    
    # Get usage for the date
    usage = usage_service.get_or_create_daily_usage(current_user.id, usage_date)
    
    # Get message limits
    is_premium = usage_service.payment_service.is_premium(current_user.id)
    from app.config import get_settings
    settings = get_settings()
    daily_limit = settings.PREMIUM_MESSAGES_PER_DAY if is_premium else settings.FREE_MESSAGES_PER_DAY
    
    return {
        "date": usage.date.isoformat(),
        "message_count": usage.message_count,
        "ai_response_count": usage.ai_response_count,
        "message_limit": daily_limit,
        "messages_remaining": max(0, daily_limit - usage.message_count),
        "is_premium": is_premium
    }


@router.get("/weekly", response_model=Dict[str, Any])
async def get_weekly_usage(
    current_user: User = Depends(get_current_user),
    usage_service: UsageService = Depends(get_service(UsageService))
):
    """
    Get usage statistics for the last 7 days
    
    Returns daily message counts for the last week
    """
    # Get complete stats which includes the weekly data
    stats = usage_service.get_usage_stats(current_user.id)
    
    # Extract just the daily data for the last 7 days
    return {
        "recent_daily": stats["recent_daily"],
        "is_premium": stats["is_premium"]
    }


@router.get("/limits", response_model=Dict[str, Any])
async def get_usage_limits(
    current_user: User = Depends(get_current_user),
    usage_service: UsageService = Depends(get_service(UsageService))
):
    """
    Get current usage limits and remaining capacity
    
    Returns detailed information about different limits
    """
    # Get premium status
    is_premium = usage_service.payment_service.is_premium(current_user.id)
    
    # Get usage summary
    summary = usage_service.get_or_create_usage_summary(current_user.id)
    
    # Get today's usage
    daily_usage = usage_service.get_or_create_daily_usage(current_user.id)
    
    # Get limits from settings
    from app.config import get_settings
    settings = get_settings()
    
    # Calculate limits
    daily_limit = settings.PREMIUM_MESSAGES_PER_DAY if is_premium else settings.FREE_MESSAGES_PER_DAY
    conversation_limit = (
        settings.PREMIUM_CONVERSATIONS_LIMIT if is_premium 
        else settings.FREE_CONVERSATIONS_LIMIT
    )
    character_limit = (
        settings.PREMIUM_CHARACTERS_LIMIT if is_premium 
        else settings.FREE_CHARACTERS_LIMIT
    )
    
    return {
        "is_premium": is_premium,
        "limits": {
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
        },
        "premium_features": {
            "can_make_public_characters": is_premium
        }
    }