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
from app.models.user import User
from app.models.world import World

router = APIRouter()


@router.post("/", response_model=schemas.WorldResponse, status_code=status.HTTP_201_CREATED)
async def create_world(
    world: schemas.WorldCreate,
    current_user: User = Depends(get_current_user),
    world_service: WorldService = Depends(get_service(WorldService))
):
    """
    Create a new world (standard, not premium)
    
    Regular users can create standard worlds. Premium worlds require a subscription.
    """
    # Check if trying to create a premium world
    if world.is_premium:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Premium worlds require a subscription. Please use the premium world creation endpoint."
        )
    
    # Create the world
    return world_service.create_world(
        owner_id=current_user.id,
        name=world.name,
        description=world.description,
        genre=world.genre,
        settings=world.settings,
        default_prompt=world.default_prompt,
        is_public=world.is_public,
        is_premium=False,  # Force to false for regular creation
        price=None
    )


@router.post("/premium", response_model=Dict[str, str])
async def create_premium_world_checkout(
    world_data: schemas.PremiumWorldCreate,
    success_url: str = Body(..., embed=True),
    cancel_url: str = Body(..., embed=True),
    current_user: User = Depends(get_current_user),
    payment_service: PaymentService = Depends(get_service(PaymentService))
):
    """
    Create a premium world by initiating a checkout session
    
    Returns a URL to redirect the user to for payment
    """
    try:
        # Store world data for later use after payment
        # In a real system, you might store this in a pending worlds table
        # Here we'll use session metadata
        metadata = {
            "user_id": current_user.id,
            "world_name": world_data.name,
            "world_description": world_data.description,
            "world_genre": world_data.genre,
            "is_premium": True,
            "price": 249.99
        }
        
        # Create checkout for premium world
        checkout_url = payment_service.create_premium_world_checkout(
            user_id=current_user.id,
            world_data=metadata,
            success_url=success_url,
            cancel_url=cancel_url,
            price=249.99  # Hardcoded price as per requirements
        )
        
        return {"checkout_url": checkout_url}
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        # logger.error(f"Error creating premium world checkout: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create checkout session"
        )


@router.get("/", response_model=schemas.WorldList)
async def list_worlds(
    name: Optional[str] = None,
    genre: Optional[str] = None,
    include_starters: bool = Query(True, description="Include starter worlds in results"),
    include_public: bool = Query(True, description="Include public worlds in results"),
    owned_only: bool = Query(False, description="Only include worlds owned by the current user"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = Query("name"),
    sort_desc: bool = Query(False),
    current_user: User = Depends(get_current_user),
    world_service: WorldService = Depends(get_service(WorldService))
):
    """
    Get all worlds accessible to the current user with pagination and filtering
    
    Returns a paginated list of worlds
    """
    filters = {}
    
    if name:
        filters['name'] = name
    
    if genre:
        filters['genre'] = genre
    
    if owned_only:
        filters['owner_id'] = current_user.id
    else:
        # Get all worlds accessible to user
        filters['members'] = current_user.id
        
        # If including starters, we'll handle it in the service
        # (the filters approach isn't sophisticated enough for complex OR conditions)
    
    worlds, total_count, total_pages = world_service.get_user_worlds(
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


@router.get("/starter", response_model=schemas.WorldList)
async def list_starter_worlds(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = Query("name"),
    sort_desc: bool = Query(False),
    current_user: User = Depends(get_current_user),
    world_service: WorldService = Depends(get_service(WorldService))
):
    """
    Get all starter worlds available to all users
    
    Returns a paginated list of starter worlds
    """
    worlds, total_count, total_pages = world_service.get_starter_worlds(
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


@router.get("/{world_id}", response_model=schemas.WorldResponse)
async def get_world(
    world_id: str = Path(..., title="The ID of the world to get"),
    current_user: User = Depends(get_current_user),
    world_service: WorldService = Depends(get_service(WorldService))
):
    """
    Get a specific world by ID
    
    If the world is a starter world, any user can access it.
    Otherwise, the user must have access to the world.
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
    
    # Prevent changing premium status
    if (world_update.is_premium is not None and 
        world_update.is_premium != world.is_premium):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot change premium status of an existing world"
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
    
    # Prevent deleting starter worlds
    if world.is_starter:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete starter worlds"
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
    include_public: bool = Query(True, description="Include public worlds in results"),
    include_starters: bool = Query(True, description="Include starter worlds in results"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    world_service: WorldService = Depends(get_service(WorldService))
):
    """
    Search for worlds by name or description
    
    Returns a paginated list of matching worlds
    """
    worlds, total_count, total_pages = world_service.search_worlds(
        query=query,
        include_public=include_public,
        include_starters=include_starters,
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


@router.post("/{world_id}/members/{user_id}", status_code=status.HTTP_200_OK)
async def add_world_member(
    world_id: str,
    user_id: str,
    current_user: User = Depends(get_current_user),
    world_service: WorldService = Depends(get_service(WorldService))
):
    """
    Add a user as a member of a world
    
    Only the owner can add members
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
            detail="Only the world owner can add members"
        )
    
    success = world_service.add_member(world_id, user_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to add member"
        )
    
    return {"status": "success", "message": "Member added successfully"}


@router.delete("/{world_id}/members/{user_id}", status_code=status.HTTP_200_OK)
async def remove_world_member(
    world_id: str,
    user_id: str,
    current_user: User = Depends(get_current_user),
    world_service: WorldService = Depends(get_service(WorldService))
):
    """
    Remove a user as a member of a world
    
    Only the owner can remove members
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
            detail="Only the world owner can remove members"
        )
    
    # Cannot remove the owner
    if user_id == world.owner_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove the world owner"
        )
    
    success = world_service.remove_member(world_id, user_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to remove member"
        )
    
    return {"status": "success", "message": "Member removed successfully"}


@router.get("/{world_id}/members", response_model=List[schemas.UserResponse])
async def get_world_members(
    world_id: str,
    current_user: User = Depends(get_current_user),
    world_service: WorldService = Depends(get_service(WorldService))
):
    """
    Get all members of a world
    
    Only members and the owner can view the member list
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
            detail="You don't have permission to view this world's members"
        )
    
    # Return all members
    return world.members