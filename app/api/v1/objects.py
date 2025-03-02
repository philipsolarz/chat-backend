# app/api/v1/objects.py
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path, Body
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any

from app.database import get_db
from app.schemas import ObjectBase, ObjectCreate, ObjectList, ObjectResponse, ObjectType, ObjectUpdate
from app.api.auth import get_current_user
from app.api.dependencies import get_service
from app.services.object_service import ObjectService
from app.services.zone_service import ZoneService
from app.services.world_service import WorldService
from app.services.payment_service import PaymentService
from app.models.player import Player as User
from app.models.object import Object, ObjectType

router = APIRouter()


@router.post("/", response_model=ObjectResponse, status_code=status.HTTP_201_CREATED)
async def create_object(
    object_data: ObjectCreate,
    current_user: User = Depends(get_current_user),
    object_service: ObjectService = Depends(get_service(ObjectService)),
    zone_service: ZoneService = Depends(get_service(ZoneService)),
    world_service: WorldService = Depends(get_service(WorldService))
):
    """
    Create a new object entity
    
    If zone_id is provided, checks:
    1. User has access to the zone's world
    2. The zone has not reached its entity limit based on its tier
    """
    # If zone_id is provided, check access
    if object_data.zone_id:
        zone = zone_service.get_zone(object_data.zone_id)
        if not zone:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Zone not found"
            )
        
        # Check if user has write access to the world (must be owner)
        world = world_service.get_world(zone.world_id)
        if not world or world.owner_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the world owner can create objects in a zone"
            )
        
        # Check zone entity limit based on tier
        if not zone_service.can_add_entity_to_zone(object_data.zone_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Zone has reached its entity limit for tier {zone.tier}. Upgrade the zone tier to add more entities."
            )
            
        # If world_id is also provided, make sure it matches the zone's world
        if object_data.world_id and object_data.world_id != zone.world_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The provided world_id does not match the zone's world"
            )
        
        # Set world_id if only zone_id is provided
        if not object_data.world_id:
            object_data.world_id = zone.world_id
    
    # If only world_id is provided, check access
    elif object_data.world_id:
        world = world_service.get_world(object_data.world_id)
        if not world:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="World not found"
            )
        
        if world.owner_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the world owner can create objects in a world"
            )
    
    # Create the object
    new_object = object_service.create_object(
        name=object_data.name,
        description=object_data.description,
        zone_id=object_data.zone_id,
        world_id=object_data.world_id,
        is_interactive=object_data.is_interactive,
        object_type=object_data.type,
        settings=object_data.properties
    )
    
    if not new_object:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to create object. The zone may have reached its entity limit."
        )
    
    return new_object


@router.get("/", response_model=ObjectList)
async def list_objects(
    zone_id: Optional[str] = Query(None, description="Filter objects by zone"),
    world_id: Optional[str] = Query(None, description="Filter objects by world"),
    object_type: Optional[str] = Query(None, description="Filter by object type"),
    is_interactive: Optional[bool] = Query(None, description="Filter by interactivity"),
    name: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = Query("name"),
    sort_desc: bool = Query(False),
    current_user: User = Depends(get_current_user),
    object_service: ObjectService = Depends(get_service(ObjectService)),
    zone_service: ZoneService = Depends(get_service(ZoneService)),
    world_service: WorldService = Depends(get_service(WorldService))
):
    """
    Get objects with pagination and filtering
    
    If zone_id is provided, returns objects in that zone.
    If world_id is provided, returns objects in that world.
    Can be filtered by object type and interactivity.
    """
    # Build filters
    filters = {}
    
    if name:
        filters['name'] = name
    
    if is_interactive is not None:
        filters['is_interactive'] = is_interactive
        
    if object_type:
        filters['object_type'] = object_type
    
    # Validate zone access if provided
    if zone_id:
        zone = zone_service.get_zone(zone_id)
        if not zone:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Zone not found"
            )
        
        # Check world access
        if not world_service.check_user_access(current_user.id, zone.world_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this world"
            )
        
        filters['zone_id'] = zone_id
    
    # Validate world access if provided
    if world_id:
        world = world_service.get_world(world_id)
        if not world:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="World not found"
            )
        
        # Check world access
        if not world_service.check_user_access(current_user.id, world_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this world"
            )
        
        filters['world_id'] = world_id
    
    # Get objects
    objects, total_count, total_pages = object_service.get_objects(
        filters=filters,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_desc=sort_desc
    )
    
    return {
        "items": objects,
        "total": total_count,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages
    }


@router.get("/{object_id}", response_model=ObjectResponse)
async def get_object(
    object_id: str = Path(..., title="The ID of the object to retrieve"),
    current_user: User = Depends(get_current_user),
    object_service: ObjectService = Depends(get_service(ObjectService)),
    zone_service: ZoneService = Depends(get_service(ZoneService)),
    world_service: WorldService = Depends(get_service(WorldService))
):
    """
    Get details of a specific object
    """
    obj = object_service.get_object(object_id)
    if not obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Object not found"
        )
    
    # Check access based on zone or world
    if obj.zone_id:
        zone = zone_service.get_zone(obj.zone_id)
        if zone and not world_service.check_user_access(current_user.id, zone.world_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this object's world"
            )
    elif obj.world_id:
        if not world_service.check_user_access(current_user.id, obj.world_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this object's world"
            )
    
    return obj


@router.put("/{object_id}", response_model=ObjectResponse)
async def update_object(
    object_id: str,
    object_update: ObjectUpdate,
    current_user: User = Depends(get_current_user),
    object_service: ObjectService = Depends(get_service(ObjectService)),
    zone_service: ZoneService = Depends(get_service(ZoneService)),
    world_service: WorldService = Depends(get_service(WorldService))
):
    """
    Update an object
    
    Only the world owner can update objects
    """
    obj = object_service.get_object(object_id)
    if not obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Object not found"
        )
    
    # Check if the user has permission to update the object
    if obj.zone_id:
        zone = zone_service.get_zone(obj.zone_id)
        if zone:
            world = world_service.get_world(zone.world_id)
            if not world or world.owner_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only the world owner can update objects"
                )
    elif obj.world_id:
        world = world_service.get_world(obj.world_id)
        if not world or world.owner_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the world owner can update objects"
            )
    else:
        # If object is not in any world or zone, default to admin-only
        if not current_user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only administrators can update unassigned objects"
            )
    
    update_data = object_update.dict(exclude_unset=True)
    
    updated_object = object_service.update_object(object_id, update_data)
    if not updated_object:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update object"
        )
    
    return updated_object


@router.delete("/{object_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_object(
    object_id: str = Path(..., title="The ID of the object to delete"),
    current_user: User = Depends(get_current_user),
    object_service: ObjectService = Depends(get_service(ObjectService)),
    zone_service: ZoneService = Depends(get_service(ZoneService)),
    world_service: WorldService = Depends(get_service(WorldService))
):
    """
    Delete an object
    
    Only the world owner can delete objects
    """
    obj = object_service.get_object(object_id)
    if not obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Object not found"
        )
    
    # Check if the user has permission to delete the object
    if obj.zone_id:
        zone = zone_service.get_zone(obj.zone_id)
        if zone:
            world = world_service.get_world(zone.world_id)
            if not world or world.owner_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only the world owner can delete objects"
                )
    elif obj.world_id:
        world = world_service.get_world(obj.world_id)
        if not world or world.owner_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the world owner can delete objects"
            )
    else:
        # If object is not in any world or zone, default to admin-only
        if not current_user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only administrators can delete unassigned objects"
            )
    
    success = object_service.delete_object(object_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete object"
        )
    
    return None


@router.post("/{object_id}/move", response_model=ObjectResponse)
async def move_object_to_zone(
    object_id: str,
    zone_id: str = Query(..., description="ID of the destination zone"),
    current_user: User = Depends(get_current_user),
    object_service: ObjectService = Depends(get_service(ObjectService)),
    zone_service: ZoneService = Depends(get_service(ZoneService)),
    world_service: WorldService = Depends(get_service(WorldService))
):
    """
    Move an object to a different zone
    
    Checks that:
    1. The object exists
    2. The destination zone exists and has capacity based on its tier
    3. The user has permission to move the object
    """
    # Check if object exists
    obj = object_service.get_object(object_id)
    if not obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Object not found"
        )
    
    # Check if destination zone exists
    zone = zone_service.get_zone(zone_id)
    if not zone:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Destination zone not found"
        )
    
    # Check if user is the world owner
    world = world_service.get_world(zone.world_id)
    if not world or world.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the world owner can move objects"
        )
    
    # If object already has a world_id, check that it's the same as the destination zone's world
    if obj.world_id and obj.world_id != zone.world_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot move object between different worlds"
        )
    
    # Move the object
    success = object_service.move_object_to_zone(object_id, zone_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to move object. The zone may have reached its tier-based entity limit (tier {zone.tier})."
        )
    
    # Return the updated object
    updated_object = object_service.get_object(object_id)
    return updated_object


@router.get("/search/", response_model=ObjectList)
async def search_objects(
    query: str = Query(..., min_length=1, description="Search term"),
    zone_id: Optional[str] = Query(None, description="Filter search to specific zone"),
    world_id: Optional[str] = Query(None, description="Filter search to specific world"),
    is_interactive: Optional[bool] = Query(None, description="Filter by interactivity"),
    object_type: Optional[str] = Query(None, description="Filter by object type"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    object_service: ObjectService = Depends(get_service(ObjectService)),
    zone_service: ZoneService = Depends(get_service(ZoneService)),
    world_service: WorldService = Depends(get_service(WorldService))
):
    """
    Search for objects by name or description
    
    Can be filtered by zone, world, interactivity, and object type
    """
    # Validate zone access if provided
    if zone_id:
        zone = zone_service.get_zone(zone_id)
        if not zone:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Zone not found"
            )
        
        # Check world access
        if not world_service.check_user_access(current_user.id, zone.world_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this world"
            )
    
    # Validate world access if provided
    if world_id:
        if not world_service.check_user_access(current_user.id, world_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this world"
            )
    
    # Search objects with the specified filters
    objects, total_count, total_pages = object_service.search_objects(
        query=query,
        zone_id=zone_id,
        world_id=world_id,
        is_interactive=is_interactive,
        object_type=object_type,
        page=page,
        page_size=page_size
    )
    
    return {
        "items": objects,
        "total": total_count,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages
    }


@router.post("/{object_id}/upgrade-tier", response_model=Dict[str, str])
async def create_object_tier_upgrade_checkout(
    object_id: str,
    success_url: str = Query(..., description="URL to redirect after successful payment"),
    cancel_url: str = Query(..., description="URL to redirect if payment is canceled"),
    current_user: User = Depends(get_current_user),
    object_service: ObjectService = Depends(get_service(ObjectService)),
    zone_service: ZoneService = Depends(get_service(ZoneService)),
    world_service: WorldService = Depends(get_service(WorldService)),
    payment_service: PaymentService = Depends(get_service(PaymentService))
):
    """
    Create a checkout session to upgrade an object's tier
    
    Returns the checkout URL for processing payment
    """
    # Check if object exists
    obj = object_service.get_object(object_id)
    if not obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Object not found"
        )
    
    # Check if the user has permission to upgrade the object
    if obj.zone_id:
        zone = zone_service.get_zone(obj.zone_id)
        if zone:
            world = world_service.get_world(zone.world_id)
            if not world or world.owner_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only the world owner can upgrade objects"
                )
    elif obj.world_id:
        world = world_service.get_world(obj.world_id)
        if not world or world.owner_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the world owner can upgrade objects"
            )
    else:
        # If object is not in any world or zone, default to admin-only
        if not current_user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only administrators can upgrade unassigned objects"
            )
    
    # Check if object has an entity
    if not obj.entity_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Object cannot be upgraded (no associated entity)"
        )
    
    try:
        # Create checkout for entity tier upgrade
        checkout_url = payment_service.create_entity_tier_upgrade_checkout(
            user_id=current_user.id,
            entity_id=obj.entity_id,
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