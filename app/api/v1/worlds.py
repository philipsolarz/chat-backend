# app/api/v1/worlds.py
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path, Body
from sqlalchemy.orm import Session
from typing import Dict, List, Optional

from app.database import get_db
from app.api import schemas
from app.api.auth import get_current_user
from app.api.dependencies import get_service
from app.services.world_service import WorldService
from app.services.payment_service import PaymentService
from app.models.player import User
from app.models.world import World

router = APIRouter()


@router.post("/", response_model=schemas.WorldResponse, status_code=status.HTTP_201_CREATED)
async def create_world(
    world: schemas.WorldCreate,
    current_user: User = Depends(get_current_user),
    world_service: WorldService = Depends(get_service(WorldService))
):
    """
    Create a new world
    
    Returns the created world
    """
    # Create the world
    return world_service.create_world(
        owner_id=current_user.id,
        name=world.name,
        description=world.description,
        settings=world.settings
    )


@router.get("/", response_model=schemas.WorldList)
async def list_worlds(
    name: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = Query("name"),
    sort_desc: bool = Query(False),
    current_user: User = Depends(get_current_user),
    world_service: WorldService = Depends(get_service(WorldService))
):
    """
    Get all worlds owned by the current user with pagination and filtering
    
    Returns a paginated list of worlds
    """
    filters = {'owner_id': current_user.id}
    
    if name:
        filters['name'] = name
    
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


@router.get("/{world_id}", response_model=schemas.WorldResponse)
async def get_world(
    world_id: str = Path(..., title="The ID of the world to get"),
    current_user: User = Depends(get_current_user),
    world_service: WorldService = Depends(get_service(WorldService))
):
    """
    Get a specific world by ID
    
    Only the owner can access a world
    """
    world = world_service.get_world(world_id)
    
    if not world:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="World not found"
        )
    
    # Check access permissions
    if not world_service.check_user_access(current_user.id, world_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to view this world"
        )
    
    return world


@router.put("/{world_id}", response_model=schemas.WorldResponse)
async def update_world(
    world_id: str,
    world_update: schemas.WorldUpdate,
    current_user: User = Depends(get_current_user),
    world_service: WorldService = Depends(get_service(WorldService))
):
    """
    Update a world
    
    Only the owner can update a world
    """
    world = world_service.get_world(world_id)
    
    if not world:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="World not found"
        )
    
    # Check ownership
    if world.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to update this world"
        )
    
    update_data = world_update.dict(exclude_unset=True)
    
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
    Delete a world
    
    Only the owner can delete a world
    """
    world = world_service.get_world(world_id)
    
    if not world:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="World not found"
        )
    
    # Check ownership
    if world.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to delete this world"
        )
    
    success = world_service.delete_world(world_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete world"
        )
    
    return None


@router.get("/search/", response_model=schemas.WorldList)
async def search_worlds(
    query: str = Query(..., min_length=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    world_service: WorldService = Depends(get_service(WorldService))
):
    """
    Search for worlds by name or description
    
    Returns a paginated list of matching worlds owned by the current user
    """
    worlds, total_count, total_pages = world_service.search_worlds(
        query=query,
        user_id=current_user.id,
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


@router.post("/zone-upgrade-checkout", response_model=Dict[str, str])
async def create_zone_upgrade_checkout(
    world_id: str = Body(..., embed=True),
    success_url: str = Body(..., embed=True),
    cancel_url: str = Body(..., embed=True),
    current_user: User = Depends(get_current_user),
    payment_service: PaymentService = Depends(get_service(PaymentService)),
    world_service: WorldService = Depends(get_service(WorldService))
):
    """
    Create a checkout session for purchasing a zone limit upgrade
    
    Returns a URL to redirect the user to for payment
    """
    try:
        # Check if user is the world owner
        world = world_service.get_world(world_id)
        if not world:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="World not found"
            )
        
        if world.owner_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the world owner can purchase zone upgrades"
            )
        
        # Create checkout for zone upgrade
        checkout_url = payment_service.create_zone_upgrade_checkout(
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