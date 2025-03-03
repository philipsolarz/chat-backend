from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any

from app.database import get_db
from app.schemas import AgentBase, AgentCreate, AgentResponse, AgentUpdate, AgentList
from app.api.auth import get_current_user
from app.api.dependencies import get_service
from app.services.agent_service import AgentService
from app.services.zone_service import ZoneService
from app.services.world_service import WorldService
from app.services.payment_service import PaymentService
from app.models.player import Player as User
from app.models.agent import Agent

router = APIRouter()

@router.post("/", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(
    agent: AgentCreate,
    current_user: User = Depends(get_current_user),
    agent_service: AgentService = Depends(get_service(AgentService)),
    zone_service: ZoneService = Depends(get_service(ZoneService)),
    world_service: WorldService = Depends(get_service(WorldService))
):
    """
    Create a new AI agent (admin only).

    If a zone_id is provided, checks:
      1. The zone exists.
      2. The current user is the owner of the world that contains the zone.
      3. The zone has capacity for a new entity.
    """
    if agent.zone_id:
        zone = zone_service.get_zone(agent.zone_id)
        if not zone:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Zone not found"
            )
        world = world_service.get_world(zone.world_id)
        if not world or world.owner_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the world owner can create agents in this zone"
            )
        if not zone_service.can_add_entity_to_zone(agent.zone_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Zone has reached its entity limit for tier {zone.tier}. Upgrade the zone tier to add more entities."
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Zone ID is required to create an agent."
        )
    
    new_agent = agent_service.create_agent(
        name=agent.name,
        description=agent.description,
        zone_id=agent.zone_id,
        settings=agent.settings
    )
    
    if not new_agent:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to create agent. The zone may have reached its entity limit."
        )
    
    return new_agent

@router.get("/", response_model=AgentList)
async def list_agents(
    zone_id: Optional[str] = Query(None, description="Filter agents by zone"),
    name: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = Query("name"),
    sort_desc: bool = Query(False),
    current_user: User = Depends(get_current_user),
    agent_service: AgentService = Depends(get_service(AgentService)),
    zone_service: ZoneService = Depends(get_service(ZoneService)),
    world_service: WorldService = Depends(get_service(WorldService))
):
    """
    Get available AI agents with pagination and filtering.

    Returns a paginated list of agents.
    """
    filters = {}
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
    
    agents, total_count, total_pages = agent_service.get_agents(
        filters=filters,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_desc=sort_desc
    )
    
    return {
        "items": agents,
        "total": total_count,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages
    }

@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: str = Path(..., title="The ID of the agent to get"),
    current_user: User = Depends(get_current_user),
    agent_service: AgentService = Depends(get_service(AgentService)),
    zone_service: ZoneService = Depends(get_service(ZoneService)),
    world_service: WorldService = Depends(get_service(WorldService))
):
    """
    Get a specific AI agent by ID.

    Returns details about the agent.
    """
    agent = agent_service.get_agent(agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found"
        )
    if agent.character and agent.character.zone_id:
        zone = zone_service.get_zone(agent.character.zone_id)
        if zone and not world_service.check_user_access(current_user.id, zone.world_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this agent's world"
            )
    
    return agent

@router.get("/search/", response_model=AgentList)
async def search_agents(
    query: str = Query(..., min_length=1),
    zone_id: Optional[str] = Query(None, description="Filter search to a specific zone"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    agent_service: AgentService = Depends(get_service(AgentService)),
    zone_service: ZoneService = Depends(get_service(ZoneService)),
    world_service: WorldService = Depends(get_service(WorldService))
):
    """
    Search for AI agents by name or description.

    Returns a paginated list of matching agents.
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
    
    agents, total_count, total_pages = agent_service.search_agents(
        query_str=query,
        zone_id=zone_id,
        page=page,
        page_size=page_size
    )
    
    return {
        "items": agents,
        "total": total_count,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages
    }

@router.put("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: str,
    agent_update: AgentUpdate,
    current_user: User = Depends(get_current_user),
    agent_service: AgentService = Depends(get_service(AgentService)),
    zone_service: ZoneService = Depends(get_service(ZoneService)),
    world_service: WorldService = Depends(get_service(WorldService))
):
    """
    Update an AI agent (admin only).

    Returns the updated agent.
    """
    agent = agent_service.get_agent(agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found"
        )
    if agent.character and agent.character.zone_id:
        zone = zone_service.get_zone(agent.character.zone_id)
        if zone:
            world = world_service.get_world(zone.world_id)
            if not world or world.owner_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only the world owner can update agents"
                )
    else:
        if not current_user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only administrators can update unassigned agents"
            )
    
    update_data = agent_update.dict(exclude_unset=True)
    updated_agent = agent_service.update_agent(agent_id, update_data)
    if not updated_agent:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update agent"
        )
    
    return updated_agent

@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    agent_id: str,
    current_user: User = Depends(get_current_user),
    agent_service: AgentService = Depends(get_service(AgentService)),
    zone_service: ZoneService = Depends(get_service(ZoneService)),
    world_service: WorldService = Depends(get_service(WorldService))
):
    """
    Delete an AI agent (admin only).

    Returns no content on success.
    """
    agent = agent_service.get_agent(agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found"
        )
    if agent.character and agent.character.zone_id:
        zone = zone_service.get_zone(agent.character.zone_id)
        if zone:
            world = world_service.get_world(zone.world_id)
            if not world or world.owner_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only the world owner can delete agents"
                )
    else:
        if not current_user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only administrators can delete unassigned agents"
            )
    
    success = agent_service.delete_agent(agent_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete agent"
        )
    
    return None

@router.post("/{agent_id}/move", response_model=AgentResponse)
async def move_agent_to_zone(
    agent_id: str,
    zone_id: str = Query(..., description="ID of the destination zone"),
    current_user: User = Depends(get_current_user),
    agent_service: AgentService = Depends(get_service(AgentService)),
    zone_service: ZoneService = Depends(get_service(ZoneService)),
    world_service: WorldService = Depends(get_service(WorldService))
):
    """
    Move an agent to a different zone.

    Checks that:
      1. The agent exists.
      2. The destination zone exists and has capacity based on its tier.
      3. The user has permission to move the agent.
    """
    agent = agent_service.get_agent(agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found"
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
            detail="Only the world owner can move agents"
        )
    
    success = agent_service.move_agent_to_zone(agent_id, zone_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to move agent. The zone may have reached its tier-based entity limit (tier {zone.tier})."
        )
    
    updated_agent = agent_service.get_agent(agent_id)
    return updated_agent

@router.post("/{agent_id}/upgrade-tier", response_model=Dict[str, str])
async def create_agent_tier_upgrade_checkout(
    agent_id: str,
    success_url: str = Query(..., description="URL to redirect after successful payment"),
    cancel_url: str = Query(..., description="URL to redirect if payment is canceled"),
    current_user: User = Depends(get_current_user),
    agent_service: AgentService = Depends(get_service(AgentService)),
    zone_service: ZoneService = Depends(get_service(ZoneService)),
    world_service: WorldService = Depends(get_service(WorldService)),
    payment_service: PaymentService = Depends(get_service(PaymentService))
):
    """
    Create a checkout session to upgrade an agent's tier.

    Returns the checkout URL for processing payment.
    """
    agent = agent_service.get_agent(agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found"
        )
    
    if agent.character and agent.character.zone_id:
        zone = zone_service.get_zone(agent.character.zone_id)
        if zone:
            world = world_service.get_world(zone.world_id)
            if not world or world.owner_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only the world owner can upgrade agents"
                )
    elif not agent.character:
        if not current_user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only administrators can upgrade unassigned agents"
            )
    
    if not agent.character:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Agent cannot be upgraded (no associated character)"
        )
    
    try:
        checkout_url = payment_service.create_entity_tier_upgrade_checkout(
            user_id=current_user.id,
            entity_id=agent.character.id,
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
