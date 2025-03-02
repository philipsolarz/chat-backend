# app/api/premium.py
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session
from functools import wraps
from typing import Callable, Type

from app.database import get_db
from app.models.player import User
from app.api.auth import get_current_user
from app.services.payment_service import PaymentService
from app.services.usage_service import UsageService


def premium_required(func: Callable) -> Callable:
    """
    Decorator to require premium status for a route
    
    Example:
        @router.post("/premium-feature")
        @premium_required
        async def premium_feature(current_user: User = Depends(get_current_user)):
            # This will only execute if user has premium
            ...
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        # Get current user from kwargs
        current_user = kwargs.get('current_user')
        if not current_user:
            # If no current_user in kwargs, it means the function hasn't been called with FastAPI's dependency injection yet
            return func(*args, **kwargs)
        
        # Check if user has premium
        if not current_user.is_premium:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This feature requires a premium subscription"
            )
        
        return await func(*args, **kwargs)
    
    return wrapper


def require_premium(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
    """
    Dependency to require premium status
    
    Example:
        @router.post("/premium-feature")
        async def premium_feature(premium_user: User = Depends(require_premium)):
            # This will only execute if user has premium
            ...
    """
    payment_service = PaymentService(db)
    if not payment_service.is_premium(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This feature requires a premium subscription"
        )
    
    return current_user


def check_character_limit(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
    """
    Dependency to check if user can create more characters
    
    Example:
        @router.post("/characters")
        async def create_character(
            user_with_capacity: User = Depends(check_character_limit),
            ...
        ):
            # This will only execute if user can create more characters
            ...
    """
    usage_service = UsageService(db)
    if not usage_service.can_create_character(current_user.id):
        # Determine if it's due to free plan or just hitting the premium limit
        is_premium = usage_service.payment_service.is_premium(current_user.id)
        if is_premium:
            detail = "You have reached your character limit. Please delete some characters to create more."
        else:
            detail = "You have reached the character limit for free users. Please upgrade to premium for more characters."
        
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail
        )
    
    return current_user


def check_conversation_limit(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
    """
    Dependency to check if user can create more conversations
    
    Example:
        @router.post("/conversations")
        async def create_conversation(
            user_with_capacity: User = Depends(check_conversation_limit),
            ...
        ):
            # This will only execute if user can create more conversations
            ...
    """
    usage_service = UsageService(db)
    if not usage_service.can_create_conversation(current_user.id):
        # Determine if it's due to free plan or just hitting the premium limit
        is_premium = usage_service.payment_service.is_premium(current_user.id)
        if is_premium:
            detail = "You have reached your conversation limit. Please delete some conversations to create more."
        else:
            detail = "You have reached the conversation limit for free users. Please upgrade to premium for more conversations."
        
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail
        )
    
    return current_user


def check_message_limit(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
    """
    Dependency to check if user can send more messages today
    
    Example:
        @router.post("/messages")
        async def send_message(
            user_with_capacity: User = Depends(check_message_limit),
            ...
        ):
            # This will only execute if user can send more messages
            ...
    """
    usage_service = UsageService(db)
    if not usage_service.can_send_message(current_user.id):
        # Determine if it's due to free plan or just hitting the premium limit
        is_premium = usage_service.payment_service.is_premium(current_user.id)
        if is_premium:
            detail = "You have reached your daily message limit. Please try again tomorrow."
        else:
            detail = "You have reached the daily message limit for free users. Please upgrade to premium for more messages."
        
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail
        )
    
    return current_user


def check_public_character_permission(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
    """
    Dependency to check if user can make characters public
    
    Example:
        @router.post("/characters/{character_id}/public")
        async def make_character_public(
            user_with_permission: User = Depends(check_public_character_permission),
            ...
        ):
            # This will only execute if user can make characters public
            ...
    """
    usage_service = UsageService(db)
    if not usage_service.can_make_character_public(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Making characters public is a premium feature. Please upgrade to premium to use this feature."
        )
    
    return current_user