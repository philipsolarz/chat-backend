# app/api/v1/zones.py
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path, Body
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any

from app.database import get_db
from app.api import schemas
from app.api.auth import get_current_user
from app.api.dependencies import get_service
from app.services.zone_service import ZoneService
from app.services.world_service import WorldService
from app.services.payment_service import PaymentService
from app.models.player import Player as User
from app.models.world import World
from app.models.zone import Zone

router = APIRouter()


@router.post("/", response_model=schemas.ZoneResponse, status_code=status.HTTP_201_CREATED)
async def create_zone(
    zone: schemas.ZoneCreate,
    current_user: User = Depends(get_current_user),
    zone_service: ZoneService = Depends(get_service(ZoneService)),
    world_service: WorldService = Depends(get_service(WorldService))
):
    """
    Create a new zone
    
    This checks that:
    1. The user has access to the world
    2. The world has not reached its tier-based zone limit
    3. If parent_zone_id is provided, it's a valid zone in the same world
    """
    # Check if user has access to the world
    world = world_service.get_world(zone.world_id)
    if not world:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="World not found"
        )
    
    # Check if user has write access to the world (must be owner)
    if world.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the world owner can create zones"
        )
    
    # Check zone limit based on world's tier
    if not world_service.can_add_zone_to_world(zone.world_id):
        zone_limit = world_service.calculate_zone_limit(world.tier)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Zone limit reached (maximum: {zone_limit} for tier {world.tier}). Upgrade the world tier to create more zones."
        )
    
    # Create the zone
    new_zone = zone_service.create_zone(
        world_id=zone.world_id,
        name=zone.name,
        description=zone.description,
        settings=zone.settings,
        parent_zone_id=zone.parent_zone_id
    )
    
    if not new_zone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to create zone. Check that the parent zone is valid."
        )
    
    return new_zone


@router.get("/", response_model=schemas.ZoneList)
async def list_zones(
    world_id: str = Query(..., description="ID of the world to list zones for"),
    parent_zone_id: Optional[str] = Query(None, description="ID of the parent zone to list sub-zones for"),
    name: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = Query("name"),
    sort_desc: bool = Query(False),
    current_user: User = Depends(get_current_user),
    zone_service: ZoneService = Depends(get_service(ZoneService)),
    world_service: WorldService = Depends(get_service(WorldService))
):
    """
    Get zones for a specific world with pagination and filtering
    
    Can be filtered to show only sub-zones of a specific parent zone
    """
    # Check if user has access to the world
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
    
    # Set up filters
    filters = {'world_id': world_id}
    
    if parent_zone_id is not None:
        filters['parent_zone_id'] = parent_zone_id
    
    if name:
        filters['name'] = name
    
    # Get zones
    zones, total_count, total_pages = zone_service.get_zones(
        filters=filters,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_desc=sort_desc
    )
    
    return {
        "items": zones,
        "total": total_count,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages
    }


@router.get("/hierarchy", response_model=schemas.ZoneHierarchyResponse)
async def get_zone_hierarchy(
    world_id: str = Query(..., description="ID of the world to get zone hierarchy for"),
    current_user: User = Depends(get_current_user),
    zone_service: ZoneService = Depends(get_service(ZoneService)),
    world_service: WorldService = Depends(get_service(WorldService))
):
    """
    Get the full hierarchy of zones for a world
    
    Returns a nested structure with top-level zones and their sub-zones
    """
    # Check if user has access to the world
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
    
    # Get all zones for this world
    all_zones = zone_service.db.query(Zone).filter(Zone.world_id == world_id).all()
    
    # Build a dictionary mapping parent IDs to children
    parent_to_children = {}
    for zone in all_zones:
        parent_id = zone.parent_zone_id
        if parent_id not in parent_to_children:
            parent_to_children[parent_id] = []
        parent_to_children[parent_id].append(zone)
    
    # Build the hierarchy
    top_level_zones = parent_to_children.get(None, [])
    
    def build_tree(zone):
        node = schemas.ZoneTreeNode(
            id=zone.id,
            name=zone.name,
            description=zone.description,
            settings=zone.settings,
            world_id=zone.world_id,
            parent_zone_id=zone.parent_zone_id,
            tier=zone.tier,  # Include tier information
            created_at=zone.created_at,
            sub_zones=[]
        )
        
        # Add children recursively
        children = parent_to_children.get(zone.id, [])
        for child in children:
            node.sub_zones.append(build_tree(child))
        
        return node
    
    # Build the tree structure
    result = [build_tree(zone) for zone in top_level_zones]
    
    return {"zones": result}


@router.get("/{zone_id}", response_model=schemas.ZoneDetailResponse)
async def get_zone(
    zone_id: str = Path(..., title="The ID of the zone to get"),
    current_user: User = Depends(get_current_user),
    zone_service: ZoneService = Depends(get_service(ZoneService)),
    world_service: WorldService = Depends(get_service(WorldService))
):
    """
    Get details of a specific zone
    
    Includes counts of sub-zones and entities
    """
    zone = zone_service.get_zone(zone_id)
    if not zone:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Zone not found"
        )
    
    # Check if user has access to the world
    if not world_service.check_user_access(current_user.id, zone.world_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this world"
        )
    
    # Count sub-zones
    sub_zone_count = zone_service.db.query(Zone).filter(Zone.parent_zone_id == zone_id).count()
    
    # Count entities
    entity_count = zone_service.count_entities_in_zone(zone_id)
    
    # Get entity limits based on tier
    entity_limit = zone_service.get_zone_entity_limit(zone.tier)
    
    # Create response
    response = {
        **zone.__dict__,
        "sub_zone_count": sub_zone_count,
        "entity_count": entity_count,
        "entity_limit": entity_limit,
        "remaining_capacity": entity_limit - entity_count
    }
    
    return response


@router.put("/{zone_id}", response_model=schemas.ZoneResponse)
async def update_zone(
    zone_id: str,
    zone_update: schemas.ZoneUpdate,
    current_user: User = Depends(get_current_user),
    zone_service: ZoneService = Depends(get_service(ZoneService)),
    world_service: WorldService = Depends(get_service(WorldService))
):
    """
    Update a zone
    
    Can update properties and change parent (move the zone in the hierarchy)
    """
    zone = zone_service.get_zone(zone_id)
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
            detail="Only the world owner can update zones"
        )
    
    update_data = zone_update.dict(exclude_unset=True)
    
    updated_zone = zone_service.update_zone(zone_id, update_data)
    if not updated_zone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to update zone. Check that the parent zone is valid and doesn't create a circular reference."
        )
    
    return updated_zone


@router.delete("/{zone_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_zone(
    zone_id: str,
    current_user: User = Depends(get_current_user),
    zone_service: ZoneService = Depends(get_service(ZoneService)),
    world_service: WorldService = Depends(get_service(WorldService))
):
    """
    Delete a zone
    
    If the zone has sub-zones, they will be reparented to the zone's parent.
    If the zone has entities and no parent, it cannot be deleted.
    """
    zone = zone_service.get_zone(zone_id)
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
            detail="Only the world owner can delete zones"
        )
    
    success = zone_service.delete_zone(zone_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to delete zone. The zone may contain entities and have no parent zone."
        )
    
    return None


@router.get(
    "/{zone_id}/entity-limits",
    response_model=Dict[str, Any]
)
async def get_zone_entity_limits(
    zone_id: str,
    current_user: User = Depends(get_current_user),
    zone_service: ZoneService = Depends(get_service(ZoneService)),
    world_service: WorldService = Depends(get_service(WorldService))
):
    """
    Get entity limit information for a zone based on tier
    
    Returns current entity count, tier-based limit, and upgrade information
    """
    zone = zone_service.get_zone(zone_id)
    if not zone:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Zone not found"
        )
    
    # Check if user has access to the world
    if not world_service.check_user_access(current_user.id, zone.world_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this world"
        )
    
    # Get zone entity limits based on tier
    limits = zone_service.get_zone_entity_limits(zone_id)
    
    # Check if user is the world owner (for purchase options)
    world = world_service.get_world(zone.world_id)
    is_owner = world and world.owner_id == current_user.id
    
    return {
        **limits,
        "is_owner": is_owner,
        "can_purchase_upgrade": is_owner
    }


@router.post("/tier-upgrade-checkout", response_model=Dict[str, str])
async def create_zone_tier_upgrade_checkout(
    zone_id: str = Body(..., embed=True),
    success_url: str = Body(..., embed=True),
    cancel_url: str = Body(..., embed=True),
    current_user: User = Depends(get_current_user),
    payment_service: PaymentService = Depends(get_service(PaymentService)),
    zone_service: ZoneService = Depends(get_service(ZoneService)),
    world_service: WorldService = Depends(get_service(WorldService))
):
    """
    Create a checkout session for purchasing a zone tier upgrade
    
    Returns a URL to redirect the user to for payment
    """
    try:
        # Get the zone
        zone = zone_service.get_zone(zone_id)
        if not zone:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Zone not found"
            )
        
        # Get the world to verify ownership
        world = world_service.get_world(zone.world_id)
        if not world:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="World not found"
            )
        
        # Check if user is the world owner
        if world.owner_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the world owner can purchase zone tier upgrades"
            )
        
        # Create checkout for zone tier upgrade
        checkout_url = payment_service.create_zone_tier_upgrade_checkout(
            user_id=current_user.id,
            zone_id=zone_id,
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