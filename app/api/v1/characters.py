# app/api/v1/characters.py
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database import get_db
from app.schemas import (
    CharacterBase,
    CharacterCreate,
    CharacterResponse,
    CharacterType,
    CharacterUpdate,
    CharacterList
)
from app.api.auth import get_current_user
from app.api.dependencies import get_service
from app.api.premium import require_premium, check_character_limit, check_public_character_permission
from app.services.character_service import CharacterService
from app.services.usage_service import UsageService
from app.services.world_service import WorldService
from app.services.zone_service import ZoneService
from app.services.payment_service import PaymentService
from app.models.player import Player as User
from app.models.character import Character, CharacterType

router = APIRouter()


@router.post("/", response_model=CharacterResponse, status_code=status.HTTP_201_CREATED)
async def create_character(
    character: CharacterCreate,
    user_with_capacity: User = Depends(check_character_limit),
    character_service: CharacterService = Depends(get_service(CharacterService)),
    usage_service: UsageService = Depends(get_service(UsageService)),
    zone_service: ZoneService = Depends(get_service(ZoneService))
):
    """
    Create a new character for the current user.
    
    If a zone_id is provided, the endpoint checks that the zone exists and has capacity.
    Returns the created character.
    """
    if character.zone_id:
        zone = zone_service.get_zone(character.zone_id)
        if not zone:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Zone not found"
            )
        if not zone_service.can_add_entity_to_zone(character.zone_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Zone has reached its entity limit for tier {zone.tier}. Upgrade the zone tier to add more entities."
            )
    
    # Track character creation for usage metrics.
    usage_service.track_character_created(user_with_capacity.id)
    
    new_character = character_service.create_character(
        user_id=user_with_capacity.id,
        name=character.name,
        description=character.description,
        zone_id=character.zone_id
    )
    
    if not new_character:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to create character. The zone may have reached its entity limit."
        )
    
    return new_character


@router.get("/", response_model=CharacterList)
async def list_characters(
    name: Optional[str] = Query(None),
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
    Get all characters belonging to the current user with pagination and filtering.
    
    Returns a paginated list of characters.
    """
    filters = {'player_id': current_user.id}
    if name:
        filters['name'] = name
    if world_id:
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


@router.get("/public", response_model=CharacterList)
async def list_public_characters(
    name: Optional[str] = Query(None),
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
    Get all public characters available for agents.
    
    Returns a paginated list of public characters.
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


@router.get("/{character_id}", response_model=CharacterResponse)
async def get_character(
    character_id: str = Path(..., title="The ID of the character to get"),
    current_user: User = Depends(get_current_user),
    character_service: CharacterService = Depends(get_service(CharacterService))
):
    """
    Get a specific character by ID.
    
    If the character is public, any user can access it.
    If it's private, only the owner may access it.
    """
    character = character_service.get_character(character_id)
    if not character:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Character not found"
        )
    if hasattr(character, "is_public") and not character.is_public and character.player_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to view this character"
        )
    return character


@router.put("/{character_id}", response_model=CharacterResponse)
async def update_character(
    character_id: str,
    character_update: CharacterUpdate,
    current_user: User = Depends(get_current_user),
    character_service: CharacterService = Depends(get_service(CharacterService)),
    usage_service: UsageService = Depends(get_service(UsageService))
):
    """
    Update a character belonging to the current user.
    
    Returns the updated character.
    """
    character = character_service.get_character(character_id)
    if not character:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Character not found"
        )
    if character.player_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update your own characters"
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
    Delete a character belonging to the current user.
    
    Returns no content on success.
    """
    character = character_service.get_character(character_id)
    if not character:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Character not found"
        )
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


@router.get("/search/", response_model=CharacterList)
async def search_characters(
    query: str = Query(..., min_length=1),
    world_id: Optional[str] = Query(None, description="Filter search to a specific world"),
    zone_id: Optional[str] = Query(None, description="Filter search to a specific zone"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    character_service: CharacterService = Depends(get_service(CharacterService))
):
    """
    Search for characters by name or description.
    
    Returns a paginated list of matching characters.
    """
    filters = {'search': query}
    if world_id:
        filters['world_id'] = world_id
    if zone_id:
        filters['zone_id'] = zone_id
    
    characters, total_count, total_pages = character_service.search_characters(
        query_str=query,
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


@router.post("/{character_id}/move", response_model=CharacterResponse)
async def move_character_to_zone(
    character_id: str,
    zone_id: str = Query(..., description="ID of the destination zone"),
    current_user: User = Depends(get_current_user),
    character_service: CharacterService = Depends(get_service(CharacterService)),
    zone_service: ZoneService = Depends(get_service(ZoneService)),
    world_service: WorldService = Depends(get_service(WorldService))
):
    """
    Move a character to a different zone.
    
    Checks:
      1. The character exists and belongs to the user.
      2. The destination zone exists and has capacity.
      3. The user has access to the destination zone's world.
    """
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
    zone = zone_service.get_zone(zone_id)
    if not zone:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Destination zone not found"
        )
    if not world_service.check_user_access(current_user.id, zone.world_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this zone's world"
        )
    success = character_service.move_character_to_zone(character_id, zone_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to move character. The zone may have reached its entity limit for tier {zone.tier}."
        )
    updated_character = character_service.get_character(character_id)
    return updated_character


@router.post("/{character_id}/upgrade-tier", response_model=dict)
async def create_character_tier_upgrade_checkout(
    character_id: str,
    success_url: str = Query(..., description="URL to redirect after successful payment"),
    cancel_url: str = Query(..., description="URL to redirect if payment is canceled"),
    current_user: User = Depends(get_current_user),
    character_service: CharacterService = Depends(get_service(CharacterService)),
    payment_service: PaymentService = Depends(get_service(PaymentService))
):
    """
    Create a checkout session to upgrade a character's tier.
    
    Returns the checkout URL for payment processing.
    """
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
    if not character.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Character cannot be upgraded (missing associated entity)"
        )
    try:
        checkout_url = payment_service.create_entity_tier_upgrade_checkout(
            user_id=current_user.id,
            entity_id=character.id,
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
