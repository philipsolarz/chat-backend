# app/api/v1/objects.py
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path, Body
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any

from app.database import get_db
from app.api import schemas
from app.api.auth import get_current_user
from app.api.dependencies import get_service
from app.services.object_service import ObjectService
from app.services.zone_service import ZoneService
from app.services.world_service import WorldService
from app.models.user import User
from app.models.object import Object

router = APIRouter()


@router.post("/", response_model=schemas.ObjectResponse, status_code=status.HTTP_201_CREATED)
async def create_object(
    object_data: schemas.ObjectCreate,
    current_user: User = Depends(get_current_user),
    object_service: ObjectService = Depends(get_service(ObjectService)),
    zone_service: ZoneService = Depends(get_service(ZoneService)),
    world_service: WorldService = Depends(get_service(WorldService))
):
    """
    Create a new object entity
    
    If zone_id is provided, checks:
    1. User has access to the zone's world
    2. The zone has not reached its entity limit
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
        
        # Check zone entity limit
        if not zone_service.can_add_entity_to_zone(object_data.zone_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Zone entity limit reached. Purchase an upgrade to add more entities."
            )
    
    # Create the object
    new_object = object_service.create_object(
        name=object_data.name,
        description=object_data.description,
        zone_id=object_data.zone_id,
        is_interactive=object_data.is_interactive,
        object_type=object_data.object_type,
        settings=object_data.settings
    )
    
    if not new_object:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to create object"
        )
    
    return new_object


@router.get("/", response_model=schemas.ObjectList)
async def list_objects(
    zone_id: Optional[str] = Query(None, description="Filter objects by zone"),
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
    Can be filtered by object type and interactivity.
    """
    # If zone_id is provided, check access
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
    
    # Get objects
    objects, total_count, total_pages = object_service.get_objects(
        zone_id=zone_id,
        object_type=object_type,
        is_interactive=is_interactive,
        page=page,
        page_size=page_size,
        sort_by=sort_by
    )
    
    return {
        "items": objects,
        "total": total_count,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages
    }


@router.get("/{object_id}", response_model=schemas.ObjectResponse)
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
    
    # If object is in a zone, check world access
    if obj.zone_id:
        zone = zone_service.get_zone(obj.zone_id)
        if zone and not world_service.check_user_access(current_user.id, zone.world_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this object's world"
            )
    
    return obj


@router.put("/{object_id}", response_model=schemas.ObjectResponse)
async def update_object(
    object_id: str,
    object_update: schemas.ObjectUpdate,
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
    
    # Check if object is in a zone and user has owner access to the world
    if obj.zone_id:
        zone = zone_service.get_zone(obj.zone_id)
        if zone:
            world = world_service.get_world(zone.world_id)
            if not world or world.owner_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only the world owner can update objects"
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
    
    # Check if object is in a zone and user has owner access to the world
    if obj.zone_id:
        zone = zone_service.get_zone(obj.zone_id)
        if zone:
            world = world_service.get_world(zone.world_id)
            if not world or world.owner_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only the world owner can delete objects"
                )
    
    success = object_service.delete_object(object_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete object"
        )
    
    return None


@router.post("/{object_id}/move", response_model=schemas.ObjectResponse)
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
    2. The destination zone exists and has capacity
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
    
    # Move the object
    success = object_service.move_object_to_zone(object_id, zone_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to move object. The zone may have reached its entity limit."
        )
    
    # Return the updated object
    updated_object = object_service.get_object(object_id)
    return updated_object