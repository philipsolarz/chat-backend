from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any

from app.database import get_db
from app.schemas import EntityBase, EntityList, EntityResponse, EntityType
from app.api.auth import get_current_user
from app.api.dependencies import check_entity_ownership, get_service
from app.services.entity_service import EntityService
from app.services.zone_service import ZoneService
from app.services.world_service import WorldService
from app.models.player import Player as User
from app.models.entity import Entity

router = APIRouter()


@router.get("/", response_model=EntityList)
async def list_entities(
    zone_id: Optional[str] = Query(None, description="Filter entities by zone"),
    world_id: Optional[str] = Query(None, description="Filter entities by world"),
    entity_type: Optional[str] = Query(None, description="Filter by entity type (character, object)"),
    name: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = Query("name"),
    sort_desc: bool = Query(False),
    current_user: User = Depends(get_current_user),
    entity_service: EntityService = Depends(get_service(EntityService)),
    zone_service: ZoneService = Depends(get_service(ZoneService)),
    world_service: WorldService = Depends(get_service(WorldService))
):
    """
    Get entities with pagination and filtering.
    
    If zone_id is provided, returns entities in that zone.
    If world_id is provided, returns entities in that world.
    Can be filtered by entity type.
    """
    filters: Dict[str, Any] = {}
    
    # Validate zone access if provided
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
    
    # Validate world access if provided
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
        filters['world_id'] = world_id  # This filter will join through Zone in the service
    
    if entity_type:
        try:
            filters['type'] = EntityType(entity_type)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid entity type: {entity_type}. Must be one of: {', '.join([e.value for e in EntityType])}"
            )
    
    if name:
        filters['name'] = name
    
    entities, total_count, total_pages = entity_service.get_entities(
        filters=filters,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_desc=sort_desc
    )
    
    return {
        "items": entities,
        "total": total_count,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages
    }


@router.get("/{entity_id}", response_model=EntityResponse)
async def get_entity(
    entity_id: str = Path(..., title="The ID of the entity to retrieve"),
    current_user: User = Depends(get_current_user),
    entity_service: EntityService = Depends(get_service(EntityService)),
    zone_service: ZoneService = Depends(get_service(ZoneService)),
    world_service: WorldService = Depends(get_service(WorldService))
):
    """
    Get details of a specific entity.
    """
    entity = entity_service.get_entity(entity_id)
    if not entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entity not found"
        )
    
    # Every entity is associated with a zone. Check access via the zone.
    zone = zone_service.get_zone(entity.zone_id)
    if zone and not world_service.check_user_access(current_user.id, zone.world_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this entity's world"
        )
    
    return entity


@router.post("/{entity_id}/move", response_model=EntityResponse)
async def move_entity_to_zone(
    entity_id: str,
    zone_id: str = Query(..., description="ID of the destination zone"),
    entity: Entity = Depends(check_entity_ownership),  # Dependency that checks ownership
    entity_service: EntityService = Depends(get_service(EntityService)),
    zone_service: ZoneService = Depends(get_service(ZoneService))
):
    """
    Move an entity to a different zone.
    
    Checks that:
      1. The entity exists.
      2. The destination zone exists and has capacity.
      3. The user has permission to move the entity.
    """
    zone = zone_service.get_zone(zone_id)
    if not zone:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Destination zone not found"
        )
    
    success = entity_service.move_entity_to_zone(entity_id, zone_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to move entity. The zone may have reached its tier-based entity limit (tier {zone.tier})."
        )
    
    updated_entity = entity_service.get_entity(entity_id)
    return updated_entity


@router.post("/{entity_id}/upgrade-tier", response_model=EntityResponse)
async def upgrade_entity_tier(
    entity_id: str,
    entity: Entity = Depends(check_entity_ownership),  # Dependency that checks ownership
    entity_service: EntityService = Depends(get_service(EntityService))
):
    """
    Upgrade an entity's tier.
    
    Only the world owner can upgrade entity tiers.
    """
    success = entity_service.upgrade_entity_tier(entity_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upgrade entity tier"
        )
    
    updated_entity = entity_service.get_entity(entity_id)
    return updated_entity


@router.delete("/{entity_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_entity(
    entity_id: str = Path(..., title="The ID of the entity to delete"),
    current_user: User = Depends(get_current_user),
    entity_service: EntityService = Depends(get_service(EntityService)),
    zone_service: ZoneService = Depends(get_service(ZoneService)),
    world_service: WorldService = Depends(get_service(WorldService))
):
    """
    Delete an entity.
    
    Only the world owner can delete entities.
    """
    entity = entity_service.get_entity(entity_id)
    if not entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entity not found"
        )
    
    zone = zone_service.get_zone(entity.zone_id)
    if zone:
        world = world_service.get_world(zone.world_id)
        if not world or world.owner_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the world owner can delete entities"
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete this entity as it's not part of any world or zone"
        )
    
    # If the entity is a character, ensure the user owns it.
    if entity.type == EntityType.CHARACTER:
        from app.models.character import Character
        character = entity_service.db.query(Character).filter(Character.id == entity_id).first()
        if character and character.player_id and character.player_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only delete your own characters"
            )
    
    success = entity_service.delete_entity(entity_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete entity"
        )
    
    return None


@router.get("/search/", response_model=EntityList)
async def search_entities(
    query: str = Query(..., min_length=1, description="Search term"),
    zone_id: Optional[str] = Query(None, description="Filter search to specific zone"),
    world_id: Optional[str] = Query(None, description="Filter search to specific world"),
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    entity_service: EntityService = Depends(get_service(EntityService)),
    zone_service: ZoneService = Depends(get_service(ZoneService)),
    world_service: WorldService = Depends(get_service(WorldService))
):
    """
    Search for entities by name or description.
    
    Can be filtered by zone, world, and entity type.
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
    
    entity_type_enum = None
    if entity_type:
        try:
            entity_type_enum = EntityType(entity_type)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid entity type: {entity_type}. Must be one of: {', '.join([e.value for e in EntityType])}"
            )
    
    entities, total_count, total_pages = entity_service.search_entities(
        query=query,
        zone_id=zone_id,
        world_id=world_id,
        entity_type=entity_type_enum,
        page=page,
        page_size=page_size
    )
    
    return {
        "items": entities,
        "total": total_count,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages
    }
