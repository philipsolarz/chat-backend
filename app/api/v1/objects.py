from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any

from app.database import get_db
from app.schemas import ObjectBase, ObjectCreate, ObjectList, ObjectResponse, ObjectUpdate
from app.api.auth import get_current_user
from app.api.dependencies import get_service
from app.services.object_service import ObjectService
from app.services.zone_service import ZoneService
from app.services.world_service import WorldService
from app.services.payment_service import PaymentService
from app.models.player import Player as User

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
    Create a new object entity.
    
    If zone_id is provided, the endpoint checks:
      1. That the zone exists.
      2. The current user has write access to the zone's world (must be the world owner).
      3. The zone has not reached its entity limit based on its tier.
    """
    # If zone_id is provided, verify zone exists and check world access
    if object_data.zone_id:
        zone = zone_service.get_zone(object_data.zone_id)
        if not zone:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Zone not found"
            )
        world = world_service.get_world(zone.world_id)
        if not world or world.owner_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the world owner can create objects in a zone"
            )
        if not zone_service.can_add_entity_to_zone(object_data.zone_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Zone has reached its entity limit for tier {zone.tier}. Upgrade the zone tier to add more entities."
            )
    
    # If no zone_id is provided, you could choose to enforce admin-only creation, etc.
    new_object = object_service.create_object(
        name=object_data.name,
        description=object_data.description,
        zone_id=object_data.zone_id,
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
    name: Optional[str] = Query(None, description="Filter by name"),
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
    Retrieve objects with pagination and filtering.
    
    Filters:
      - zone_id: Return objects in the given zone.
      - world_id: Return objects in the given world (validated via the associated zone).
      - name: Filter by object name.
    """
    filters: Dict[str, Any] = {}
    if name:
        filters['name'] = name

    if zone_id:
        zone = zone_service.get_zone(zone_id)
        if not zone:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Zone not found"
            )
        if not world_service.check_user_access(current_user.id, zone.world_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this world"
            )
        filters['zone_id'] = zone_id

    if world_id:
        world = world_service.get_world(world_id)
        if not world:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="World not found"
            )
        if not world_service.check_user_access(current_user.id, world_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this world"
            )
        filters['world_id'] = world_id

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
    Retrieve details of a specific object.
    """
    obj = object_service.get_object(object_id)
    if not obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Object not found"
        )
    # Validate access based on the object's zone (and its world)
    if obj.zone_id:
        zone = zone_service.get_zone(obj.zone_id)
        if zone and not world_service.check_user_access(current_user.id, zone.world_id):
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
    Update an object.
    
    Only the world owner can update objects.
    """
    obj = object_service.get_object(object_id)
    if not obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Object not found"
        )
    # Check update permission
    if obj.zone_id:
        zone = zone_service.get_zone(obj.zone_id)
        if zone:
            world = world_service.get_world(zone.world_id)
            if not world or world.owner_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only the world owner can update objects"
                )
    elif not current_user.is_admin:
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
    Delete an object.
    
    Only the world owner (or an administrator for unassigned objects) can delete objects.
    """
    obj = object_service.get_object(object_id)
    if not obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Object not found"
        )
    # Check delete permission
    if obj.zone_id:
        zone = zone_service.get_zone(obj.zone_id)
        if zone:
            world = world_service.get_world(zone.world_id)
            if not world or world.owner_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only the world owner can delete objects"
                )
    elif not current_user.is_admin:
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
    Move an object to a different zone.
    
    Checks that:
      1. The object exists.
      2. The destination zone exists and has capacity.
      3. The user has permission to move the object.
    """
    obj = object_service.get_object(object_id)
    if not obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Object not found"
        )
    zone = zone_service.get_zone(zone_id)
    if not zone:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Destination zone not found"
        )
    world = world_service.get_world(zone.world_id)
    if not world or world.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the world owner can move objects"
        )
    if obj.zone_id and obj.zone_id != zone_id:
        # You might enforce that objects can’t move between different worlds
        current_zone = zone_service.get_zone(obj.zone_id)
        if current_zone and current_zone.world_id != zone.world_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot move object between different worlds"
            )
    success = object_service.move_object_to_zone(object_id, zone_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to move object. The zone may have reached its tier-based entity limit (tier {zone.tier})."
        )
    updated_object = object_service.get_object(object_id)
    return updated_object


@router.get("/search/", response_model=ObjectList)
async def search_objects(
    query: str = Query(..., min_length=1, description="Search term"),
    zone_id: Optional[str] = Query(None, description="Filter search to a specific zone"),
    world_id: Optional[str] = Query(None, description="Filter search to a specific world"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    object_service: ObjectService = Depends(get_service(ObjectService)),
    zone_service: ZoneService = Depends(get_service(ZoneService)),
    world_service: WorldService = Depends(get_service(WorldService))
):
    """
    Search for objects by name or description.
    """
    if zone_id:
        zone = zone_service.get_zone(zone_id)
        if not zone:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Zone not found"
            )
        if not world_service.check_user_access(current_user.id, zone.world_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this world"
            )
    if world_id:
        if not world_service.check_user_access(current_user.id, world_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this world"
            )
    
    objects, total_count, total_pages = object_service.search_objects(
        query=query,
        zone_id=zone_id,
        world_id=world_id,
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
    Create a checkout session to upgrade an object's tier.
    
    Returns the checkout URL for processing payment.
    """
    obj = object_service.get_object(object_id)
    if not obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Object not found"
        )
    if obj.zone_id:
        zone = zone_service.get_zone(obj.zone_id)
        if zone:
            world = world_service.get_world(zone.world_id)
            if not world or world.owner_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only the world owner can upgrade objects"
                )
    elif not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can upgrade unassigned objects"
        )
    if not obj.entity_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Object cannot be upgraded (no associated entity)"
        )
    try:
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
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create checkout session"
        )
