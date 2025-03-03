from fastapi import APIRouter, Depends, HTTPException, status, Query, Path, Body
from sqlalchemy.orm import Session
from typing import Any, Dict, List, Optional

from app.database import get_db
from app.schemas import WorldList, WorldBase, WorldCreate, WorldResponse, WorldUpdate
from app.api.auth import get_current_user
from app.api.dependencies import get_service
from app.services.world_service import WorldService
from app.services.payment_service import PaymentService
from app.models.player import Player as User
from app.models.world import World

router = APIRouter()


@router.post("/", response_model=WorldResponse, status_code=status.HTTP_201_CREATED)
async def create_world(
    world: WorldCreate,
    current_user: User = Depends(get_current_user),
    world_service: WorldService = Depends(get_service(WorldService))
):
    """
    Create a new world
    
    Returns the created world.
    """
    # Only admins can mark worlds as official.
    if world.is_official and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can create official worlds"
        )
        
    # Create the world using the provided settings (which maps to properties)
    return world_service.create_world(
        owner_id=current_user.id,
        name=world.name,
        description=world.description,
        settings=world.settings,
        is_official=world.is_official,
        is_private=world.is_private
    )


@router.get("/", response_model=WorldList)
async def list_worlds(
    name: Optional[str] = None,
    is_official: Optional[bool] = None,
    include_private: bool = Query(False, description="Whether to include private worlds"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = Query("name"),
    sort_desc: bool = Query(False),
    current_user: User = Depends(get_current_user),
    world_service: WorldService = Depends(get_service(WorldService))
):
    """
    Get worlds with pagination and filtering.
    
    Returns a paginated list of worlds.
    """
    filters = {}
    if name:
        filters['name'] = name
    if is_official is not None:
        filters['is_official'] = is_official
    if not include_private:
        filters['is_private'] = False

    worlds, total_count, total_pages = world_service.get_worlds(
        filters=filters,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_desc=sort_desc
    )
    
    return {
        "items": worlds,
        "total": total_count,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages
    }


@router.get("/{world_id}", response_model=WorldResponse)
async def get_world(
    world_id: str = Path(..., title="The ID of the world to get"),
    current_user: User = Depends(get_current_user),
    world_service: WorldService = Depends(get_service(WorldService))
):
    """
    Get a specific world by ID.
    
    Accessible for world owners, admins, or for public (non-private) worlds.
    """
    world = world_service.get_world(world_id)
    if not world:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="World not found"
        )
    if not world_service.check_user_access(current_user.id, world_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to view this world"
        )
    return world


@router.put("/{world_id}", response_model=WorldResponse)
async def update_world(
    world_id: str,
    world_update: WorldUpdate,
    current_user: User = Depends(get_current_user),
    world_service: WorldService = Depends(get_service(WorldService))
):
    """
    Update a world.
    
    Only the owner may update their world.
    """
    world = world_service.get_world(world_id)
    if not world:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="World not found"
        )
    if world.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to update this world"
        )
    # Only allow official status changes by admins.
    if world_update.is_official is not None and world_update.is_official != world.is_official and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can change the official status of worlds"
        )
    
    # Use by_alias=True so that "settings" maps to "properties"
    update_data = world_update.dict(by_alias=True, exclude_unset=True)
    
    updated_world = world_service.update_world(world_id, update_data)
    if not updated_world:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update world"
        )
    
    return updated_world


@router.delete("/{world_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_world(
    world_id: str,
    current_user: User = Depends(get_current_user),
    world_service: WorldService = Depends(get_service(WorldService))
):
    """
    Delete a world.
    
    Only the world owner may delete their world.
    """
    world = world_service.get_world(world_id)
    if not world:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="World not found"
        )
    if world.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to delete this world"
        )
    if world.is_official and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can delete official worlds"
        )
    success = world_service.delete_world(world_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete world"
        )
    return None


@router.get("/search/", response_model=WorldList)
async def search_worlds(
    query: str = Query(..., min_length=1),
    include_private: bool = Query(False, description="Whether to include private worlds"),
    is_official: Optional[bool] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    world_service: WorldService = Depends(get_service(WorldService))
):
    """
    Search for worlds by name or description.
    
    Returns a paginated list of matching worlds.
    """
    filters = {'search': query}
    if is_official is not None:
        filters['is_official'] = is_official
    if not include_private:
        filters['is_private'] = False
    
    worlds, total_count, total_pages = world_service.get_worlds(
        filters=filters,
        page=page,
        page_size=page_size
    )
    
    return {
        "items": worlds,
        "total": total_count,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages
    }


@router.get("/search/limits", response_model=Dict[str, Any])
async def get_world_limits(
    world_id: str,
    current_user: User = Depends(get_current_user),
    world_service: WorldService = Depends(get_service(WorldService))
):
    """
    Get zone limit information for a world based on its tier.
    
    Returns zone usage statistics.
    """
    world = world_service.get_world(world_id)
    if not world:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="World not found"
        )
    if not world_service.check_user_access(current_user.id, world_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to view this world"
        )
    from app.services.zone_service import ZoneService
    zone_service = ZoneService(next(get_db()))
    zone_count = zone_service.count_zones_in_world(world_id)
    zone_limit = world_service.calculate_zone_limit(world.tier)
    
    return {
        "tier": world.tier,
        "zone_count": zone_count,
        "zone_limit": zone_limit,
        "remaining_capacity": zone_limit - zone_count,
        "can_upgrade": True,
        "is_owner": world.owner_id == current_user.id
    }


@router.post("/tier-upgrade-checkout", response_model=Dict[str, str])
async def create_world_tier_upgrade_checkout(
    world_id: str = Body(..., embed=True),
    success_url: str = Body(..., embed=True),
    cancel_url: str = Body(..., embed=True),
    current_user: User = Depends(get_current_user),
    payment_service: PaymentService = Depends(get_service(PaymentService)),
    world_service: WorldService = Depends(get_service(WorldService))
):
    """
    Create a checkout session for purchasing a world tier upgrade.
    
    Returns a URL for redirecting the user to complete payment.
    """
    try:
        world = world_service.get_world(world_id)
        if not world:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="World not found"
            )
        if world.owner_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the world owner can purchase tier upgrades"
            )
        checkout_url = payment_service.create_world_tier_upgrade_checkout(
            user_id=current_user.id,
            world_id=world_id,
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
