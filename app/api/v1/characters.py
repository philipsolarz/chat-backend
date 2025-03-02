# app/api/v1/characters.py
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database import get_db
from app.api import schemas
from app.api.auth import get_current_user
from app.api.dependencies import get_service
from app.api.premium import require_premium, check_character_limit, check_public_character_permission
from app.services.character_service import CharacterService
from app.services.usage_service import UsageService
from app.services.world_service import WorldService
from app.services.zone_service import ZoneService
from app.services.payment_service import PaymentService
from app.models.player import User
from app.models.character import Character, CharacterType

router = APIRouter()


@router.post("/", response_model=schemas.CharacterResponse, status_code=status.HTTP_201_CREATED)
async def create_character(
    character: schemas.CharacterCreate,
    user_with_capacity: User = Depends(check_character_limit),
    character_service: CharacterService = Depends(get_service(CharacterService)),
    usage_service: UsageService = Depends(get_service(UsageService)),
    world_service: WorldService = Depends(get_service(WorldService)),
    zone_service: ZoneService = Depends(get_service(ZoneService))
):
    """
    Create a new character for the current user
    
    This endpoint checks character limits before creating.
    If zone_id is provided, checks if the zone has capacity for another entity.
    Returns the created character.
    """
    # If trying to make public, check if user has premium
    if character.is_public and not usage_service.can_make_character_public(user_with_capacity.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Making characters public is a premium feature"
        )
    
    # If world_id is provided, check if user has access
    if character.world_id:
        world = world_service.get_world(character.world_id)
        if not world:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="World not found"
            )
        
        if not world_service.check_user_access(user_with_capacity.id, character.world_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this world"
            )
    
    # If zone_id is provided, check if zone has capacity for another entity
    if character.zone_id:
        zone = zone_service.get_zone(character.zone_id)
        if not zone:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Zone not found"
            )
        
        # Check if world IDs match
        if character.world_id and zone.world_id != character.world_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Zone does not belong to the specified world"
            )
        
        # Check zone capacity based on tier
        if not zone_service.can_add_entity_to_zone(character.zone_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Zone has reached its entity limit for tier {zone.tier}. Upgrade the zone tier to add more entities."
            )
    
    # Track character creation for usage metrics
    usage_service.track_character_created(user_with_capacity.id)
    
    # Create the character
    new_character = character_service.create_character(
        user_id=user_with_capacity.id,
        name=character.name,
        description=character.description,
        world_id=character.world_id,
        zone_id=character.zone_id,
        is_public=character.is_public,
        template=character.template
    )
    
    if not new_character:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to create character. The zone may have reached its entity limit."
        )
    
    return new_character


@router.get("/", response_model=schemas.CharacterList)
async def list_characters(
    name: Optional[str] = None,
    is_public: Optional[bool] = None,
    world_id: Optional[str] = Query(None, description="Filter characters by world"),
    zone_id: Optional[str] = Query(None, description="Filter characters by zone"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = Query("name"),
    sort_desc: bool = Query(False),
    current_user: User = Depends(get_current_user),
    character_service: CharacterService = Depends(get_service(CharacterService)),
    world_service: WorldService = Depends(get_service(WorldService))
):
    """
    Get all characters belonging to the current user with pagination and filtering
    
    Returns a paginated list of characters
    """
    filters = {'player_id': current_user.id}
    
    if name:
        filters['name'] = name
    
    if is_public is not None:
        filters['is_public'] = is_public
    
    if world_id:
        # Check if user has access to the world
        if not world_service.check_user_access(current_user.id, world_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this world"
            )
        filters['world_id'] = world_id
    
    if zone_id:
        filters['zone_id'] = zone_id
    
    characters, total_count, total_pages = character_service.get_characters(
        filters=filters,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_desc=sort_desc
    )
    
    return {
        "items": characters,
        "total": total_count,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages
    }


@router.get("/public", response_model=schemas.CharacterList)
async def list_public_characters(
    name: Optional[str] = None,
    world_id: Optional[str] = Query(None, description="Filter characters by world"),
    zone_id: Optional[str] = Query(None, description="Filter characters by zone"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = Query("name"),
    sort_desc: bool = Query(False),
    current_user: User = Depends(get_current_user),
    character_service: CharacterService = Depends(get_service(CharacterService))
):
    """
    Get all public characters available for agents
    
    Returns a paginated list of public characters
    """
    filters = {'is_public': True}
    
    if name:
        filters['name'] = name
    
    if world_id:
        filters['world_id'] = world_id
    
    if zone_id:
        filters['zone_id'] = zone_id
    
    characters, total_count, total_pages = character_service.get_characters(
        filters=filters,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_desc=sort_desc
    )
    
    return {
        "items": characters,
        "total": total_count,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages
    }


@router.get("/{character_id}", response_model=schemas.CharacterResponse)
async def get_character(
    character_id: str = Path(..., title="The ID of the character to get"),
    current_user: User = Depends(get_current_user),
    character_service: CharacterService = Depends(get_service(CharacterService))
):
    """
    Get a specific character by ID
    
    If the character is public, any user can access it.
    If it's private, only the owner can access it.
    """
    character = character_service.get_character(character_id)
    
    if not character:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Character not found"
        )
    
    # Check access permissions
    if not character.is_public and character.player_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to view this character"
        )
    
    return character


@router.put("/{character_id}", response_model=schemas.CharacterResponse)
async def update_character(
    character_id: str,
    character_update: schemas.CharacterUpdate,
    current_user: User = Depends(get_current_user),
    character_service: CharacterService = Depends(get_service(CharacterService)),
    usage_service: UsageService = Depends(get_service(UsageService))
):
    """
    Update a character belonging to the current user
    
    Returns the updated character
    """
    character = character_service.get_character(character_id)
    if not character:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Character not found"
        )
    
    # Check ownership
    if character.player_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update your own characters"
        )
    
    # Check if trying to make public and has permission
    if character_update.is_public is not None and character_update.is_public and not character.is_public:
        if not usage_service.can_make_character_public(character.player_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Making characters public is a premium feature"
            )
    
    update_data = character_update.dict(exclude_unset=True)
    
    updated_character = character_service.update_character(character.id, update_data)
    if not updated_character:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update character"
        )
    
    return updated_character


@router.delete("/{character_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_character(
    character_id: str,
    current_user: User = Depends(get_current_user),
    character_service: CharacterService = Depends(get_service(CharacterService))
):
    """
    Delete a character belonging to the current user
    
    Returns no content on success
    """
    character = character_service.get_character(character_id)
    if not character:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Character not found"
        )
    
    # Check ownership
    if character.player_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own characters"
        )
    
    success = character_service.delete_character(character.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete character"
        )
    
    return None


@router.get("/search/", response_model=schemas.CharacterList)
async def search_characters(
    query: str = Query(..., min_length=1),
    include_public: bool = Query(False, title="Include public characters in results"),
    world_id: Optional[str] = Query(None, description="Filter search to specific world"),
    zone_id: Optional[str] = Query(None, description="Filter search to specific zone"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    character_service: CharacterService = Depends(get_service(CharacterService))
):
    """
    Search for characters by name or description
    
    Returns a paginated list of matching characters
    """
    # Create filters dictionary for search
    filters = {'search': query}
    
    # If world_id is provided, add it to filters
    if world_id:
        filters['world_id'] = world_id
    
    # If zone_id is provided, add it to filters
    if zone_id:
        filters['zone_id'] = zone_id
    
    characters, total_count, total_pages = character_service.search_characters(
        query=query,
        include_public=include_public,
        user_id=current_user.id,
        page=page,
        page_size=page_size,
        filters=filters
    )
    
    return {
        "items": characters,
        "total": total_count,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages
    }


@router.post("/{character_id}/public", response_model=schemas.CharacterResponse)
async def make_character_public(
    character_id: str,
    premium_user: User = Depends(check_public_character_permission), # This checks premium status
    character_service: CharacterService = Depends(get_service(CharacterService))
):
    """
    Make a character publicly available for agents (Premium Feature)
    
    Returns the updated character
    """
    character = character_service.get_character(character_id)
    if not character:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Character not found"
        )
    
    # Check ownership
    if character.player_id != premium_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only make your own characters public"
        )
    
    updated_character = character_service.make_character_public(character.id)
    if not updated_character:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update character"
        )
    
    return updated_character


@router.post("/{character_id}/private", response_model=schemas.CharacterResponse)
async def make_character_private(
    character_id: str,
    current_user: User = Depends(get_current_user),
    character_service: CharacterService = Depends(get_service(CharacterService))
):
    """
    Make a character private (only for owner)
    
    Returns the updated character
    """
    character = character_service.get_character(character_id)
    if not character:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Character not found"
        )
    
    # Check ownership
    if character.player_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only make your own characters private"
        )
    
    updated_character = character_service.make_character_private(character.id)
    if not updated_character:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update character"
        )
    
    return updated_character


@router.post("/{character_id}/move", response_model=schemas.CharacterResponse)
async def move_character_to_zone(
    character_id: str,
    zone_id: str = Query(..., description="ID of the destination zone"),
    current_user: User = Depends(get_current_user),
    character_service: CharacterService = Depends(get_service(CharacterService)),
    zone_service: ZoneService = Depends(get_service(ZoneService)),
    world_service: WorldService = Depends(get_service(WorldService))
):
    """
    Move a character to a different zone
    
    Checks that:
    1. The character exists and belongs to the user
    2. The destination zone exists and has capacity based on its tier
    3. The user has permission to access the destination zone
    """
    # Check if character exists and belongs to user
    character = character_service.get_character(character_id)
    if not character:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Character not found"
        )
    
    if character.player_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only move your own characters"
        )
    
    # Check if destination zone exists
    zone = zone_service.get_zone(zone_id)
    if not zone:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Destination zone not found"
        )
    
    # Check if user has access to the zone's world
    if not world_service.check_user_access(current_user.id, zone.world_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this zone's world"
        )
    
    # Move the character
    success = character_service.move_character_to_zone(character_id, zone_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to move character. The zone may have reached its tier-based entity limit (tier {zone.tier})."
        )
    
    # Return the updated character
    updated_character = character_service.get_character(character_id)
    return updated_character


@router.post("/{character_id}/upgrade-tier", response_model=schemas.CharacterResponse)
async def create_character_tier_upgrade_checkout(
    character_id: str,
    success_url: str = Query(..., description="URL to redirect after successful payment"),
    cancel_url: str = Query(..., description="URL to redirect if payment is canceled"),
    current_user: User = Depends(get_current_user),
    character_service: CharacterService = Depends(get_service(CharacterService)),
    payment_service: PaymentService = Depends(get_service(PaymentService))
):
    """
    Create a checkout session to upgrade a character's tier
    
    Returns the checkout URL for processing payment
    """
    # Check if character exists and belongs to user
    character = character_service.get_character(character_id)
    if not character:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Character not found"
        )
    
    if character.player_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only upgrade your own characters"
        )
    
    if not character.entity_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Character cannot be upgraded (no associated entity)"
        )
    
    try:
        # Create checkout for entity tier upgrade
        checkout_url = payment_service.create_entity_tier_upgrade_checkout(
            user_id=current_user.id,
            entity_id=character.entity_id,
            success_url=success_url,
            cancel_url=cancel_url
        )
        
        return {"checkout_url": checkout_url}
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create checkout session"
        )