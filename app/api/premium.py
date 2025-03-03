# app/api/premium.py
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session
from functools import wraps
from typing import Callable, Any

from app.database import get_db
from app.models.player import Player as User  # Using 'User' for compatibility
from app.api.auth import get_current_user
from app.services.payment_service import PaymentService
from app.services.usage_service import UsageService


def premium_required(func: Callable) -> Callable:
    """
    Decorator to require premium status for a route.
    
    Example:
        @router.post("/premium-feature")
        @premium_required
        async def premium_feature(current_user: User = Depends(get_current_user)):
            # This will only execute if the user has premium
            ...
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        current_user = kwargs.get('current_user')
        if not current_user:
            # If no current_user in kwargs, proceed normally (this may be before dependency injection)
            return await func(*args, **kwargs)
        
        if not current_user.is_premium:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This feature requires a premium subscription"
            )
        
        return await func(*args, **kwargs)
    
    return wrapper


def require_premium(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> User:
    """
    Dependency to require premium status.
    
    Example:
        @router.post("/premium-feature")
        async def premium_feature(premium_user: User = Depends(require_premium)):
            # This will only execute if the user has premium
            ...
    """
    payment_service = PaymentService(db)
    if not payment_service.is_premium(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This feature requires a premium subscription"
        )
    
    return current_user


def check_character_limit(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> User:
    """
    Dependency to check if the user can create more characters.
    Limits are determined by tier-based calculations.
    
    Example:
        @router.post("/characters")
        async def create_character(
            user_with_capacity: User = Depends(check_character_limit),
            ...
        ):
            # Only executes if the user has capacity to create more characters
            ...
    """
    usage_service = UsageService(db)
    if not usage_service.can_create_character(current_user.id):
        is_premium = usage_service.payment_service.is_premium(current_user.id)
        detail = (
            "You have reached your character limit. Please delete some characters to create more."
            if is_premium
            else "You have reached the character limit for free users. Please upgrade to premium for more characters."
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail
        )
    
    return current_user


def check_world_limit(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> User:
    """
    Dependency to check if the user can create more worlds.
    Limits are determined by tier-based calculations.
    
    Example:
        @router.post("/worlds")
        async def create_world(
            user_with_capacity: User = Depends(check_world_limit),
            ...
        ):
            # Only executes if the user can create more worlds
            ...
    """
    usage_service = UsageService(db)
    if not usage_service.can_create_world(current_user.id):
        is_premium = usage_service.payment_service.is_premium(current_user.id)
        detail = (
            "You have reached your world limit. Please delete some worlds to create more."
            if is_premium
            else "You have reached the world limit for free users. Please upgrade to premium for more worlds."
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail
        )
    
    return current_user


def check_conversation_limit(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> User:
    """
    Dependency to check if the user can create more conversations.
    Limits are determined by tier-based calculations.
    
    Example:
        @router.post("/conversations")
        async def create_conversation(
            user_with_capacity: User = Depends(check_conversation_limit),
            ...
        ):
            # Only executes if the user can create more conversations
            ...
    """
    usage_service = UsageService(db)
    if not usage_service.can_create_conversation(current_user.id):
        is_premium = usage_service.payment_service.is_premium(current_user.id)
        detail = (
            "You have reached your conversation limit. Please delete some conversations to create more."
            if is_premium
            else "You have reached the conversation limit for free users. Please upgrade to premium for more conversations."
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail
        )
    
    return current_user


def check_message_limit(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> User:
    """
    Dependency to check if the user can send more messages today.
    Limits are determined by tier-based calculations.
    
    Example:
        @router.post("/messages")
        async def send_message(
            user_with_capacity: User = Depends(check_message_limit),
            ...
        ):
            # Only executes if the user can send more messages
            ...
    """
    usage_service = UsageService(db)
    if not usage_service.can_send_message(current_user.id):
        is_premium = usage_service.payment_service.is_premium(current_user.id)
        detail = (
            "You have reached your daily message limit. Please try again tomorrow."
            if is_premium
            else "You have reached the daily message limit for free users. Please upgrade to premium for more messages."
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail
        )
    
    return current_user


def check_public_character_permission(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> User:
    """
    Dependency to check if the user is allowed to make characters public.
    Only premium users can make characters public.
    
    Example:
        @router.post("/characters/{character_id}/public")
        async def make_character_public(
            user_with_permission: User = Depends(check_public_character_permission),
            ...
        ):
            # Only executes if the user can make characters public
            ...
    """
    usage_service = UsageService(db)
    if not usage_service.can_make_character_public(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Making characters public is a premium feature. Please upgrade to premium to use this feature."
        )
    
    return current_user


def check_world_tier_upgrade_permission(
    current_user: User = Depends(get_current_user), 
    world_id: str = None,
    db: Session = Depends(get_db)
) -> User:
    """
    Dependency to check if the current user is the owner of a world and can upgrade its tier.
    
    Example:
        @router.post("/worlds/{world_id}/upgrade-tier")
        async def upgrade_world_tier(
            world_id: str,
            user_with_permission: User = Depends(
                lambda: check_world_tier_upgrade_permission(world_id=world_id)
            ),
            ...
        ):
            # Only executes if the user owns the world
    """
    if not world_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="World ID is required"
        )
    
    from app.services.world_service import WorldService
    world_service = WorldService(db)
    
    world = world_service.get_world(world_id)
    if not world:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="World not found"
        )
    
    if world.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the world owner can upgrade its tier"
        )
    
    return current_user
