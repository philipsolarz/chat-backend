# app/api/v1/agents.py
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database import get_db
from app.api import schemas
from app.api.auth import get_current_user
from app.api.dependencies import get_service
from app.services.agent_service import AgentService
from app.services.zone_service import ZoneService
from app.services.world_service import WorldService
from app.models.user import User
from app.models.agent import Agent

router = APIRouter()


@router.post("/", response_model=schemas.AgentResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(
    agent: schemas.AgentCreate,
    current_user: User = Depends(get_current_user),
    agent_service: AgentService = Depends(get_service(AgentService)),
    zone_service: ZoneService = Depends(get_service(ZoneService)),
    world_service: WorldService = Depends(get_service(WorldService))
):
    """
    Create a new AI agent (admin only)
    
    If zone_id is provided, checks:
    1. User has access to the zone's world
    2. The zone has not reached its entity limit
    """
    # If zone_id is provided, check access
    if agent.zone_id:
        zone = zone_service.get_zone(agent.zone_id)
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
                detail="Only the world owner can create agents in a zone"
            )
        
        # Check zone entity limit
        if not zone_service.can_add_entity_to_zone(agent.zone_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Zone entity limit reached. Purchase an upgrade to add more entities."
            )
    
    # Create the agent
    new_agent = agent_service.create_agent(
        name=agent.name,
        description=agent.description,
        system_prompt=agent.system_prompt,
        zone_id=agent.zone_id,
        settings=agent.settings
    )
    
    if not new_agent:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to create agent"
        )
    
    return new_agent


@router.get("/", response_model=schemas.AgentList)
async def list_agents(
    is_active: Optional[bool] = None,
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
    Get available AI agents with pagination and filtering
    
    Returns a paginated list of agents
    """
    filters = {}
    
    if is_active is not None:
        filters['is_active'] = is_active
    
    if name:
        filters['name'] = name
    
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


@router.get("/{agent_id}", response_model=schemas.AgentResponse)
async def get_agent(
    agent_id: str = Path(..., title="The ID of the agent to get"),
    current_user: User = Depends(get_current_user),
    agent_service: AgentService = Depends(get_service(AgentService)),
    zone_service: ZoneService = Depends(get_service(ZoneService)),
    world_service: WorldService = Depends(get_service(WorldService))
):
    """
    Get a specific AI agent by ID
    
    Returns details about the agent
    """
    agent = agent_service.get_agent(agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found"
        )
    
    # If agent is in a zone, check world access
    if agent.zone_id:
        zone = zone_service.get_zone(agent.zone_id)
        if zone and not world_service.check_user_access(current_user.id, zone.world_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this agent's world"
            )
    
    return agent


@router.get("/search/", response_model=schemas.AgentList)
async def search_agents(
    query: str = Query(..., min_length=1),
    include_inactive: bool = Query(False, title="Include inactive agents in results"),
    zone_id: Optional[str] = Query(None, description="Filter search to specific zone"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    agent_service: AgentService = Depends(get_service(AgentService)),
    zone_service: ZoneService = Depends(get_service(ZoneService)),
    world_service: WorldService = Depends(get_service(WorldService))
):
    """
    Search for AI agents by name or description
    
    Returns a paginated list of matching agents
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
    
    agents, total_count, total_pages = agent_service.search_agents(
        query=query,
        include_inactive=include_inactive,
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


@router.put("/{agent_id}", response_model=schemas.AgentResponse)
async def update_agent(
    agent_id: str,
    agent_update: schemas.AgentUpdate,
    current_user: User = Depends(get_current_user),
    agent_service: AgentService = Depends(get_service(AgentService)),
    zone_service: ZoneService = Depends(get_service(ZoneService)),
    world_service: WorldService = Depends(get_service(WorldService))
):
    """
    Update an AI agent (admin only)
    
    Returns the updated agent
    """
    agent = agent_service.get_agent(agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found"
        )
    
    # Check if agent is in a zone and user has owner access to the world
    if agent.zone_id:
        zone = zone_service.get_zone(agent.zone_id)
        if zone:
            world = world_service.get_world(zone.world_id)
            if not world or world.owner_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only the world owner can update agents"
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
    Delete an AI agent (admin only)
    
    Returns no content on success
    """
    agent = agent_service.get_agent(agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found"
        )
    
    # Check if agent is in a zone and user has owner access to the world
    if agent.zone_id:
        zone = zone_service.get_zone(agent.zone_id)
        if zone:
            world = world_service.get_world(zone.world_id)
            if not world or world.owner_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only the world owner can delete agents"
                )
    
    success = agent_service.delete_agent(agent_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete agent"
        )
    
    return None


@router.post("/{agent_id}/activate", response_model=schemas.AgentResponse)
async def activate_agent(
    agent_id: str,
    current_user: User = Depends(get_current_user),
    agent_service: AgentService = Depends(get_service(AgentService)),
    zone_service: ZoneService = Depends(get_service(ZoneService)),
    world_service: WorldService = Depends(get_service(WorldService))
):
    """
    Activate an AI agent
    
    Returns the updated agent
    """
    agent = agent_service.get_agent(agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found"
        )
    
    # Check if agent is in a zone and user has owner access to the world
    if agent.zone_id:
        zone = zone_service.get_zone(agent.zone_id)
        if zone:
            world = world_service.get_world(zone.world_id)
            if not world or world.owner_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only the world owner can activate agents"
                )
    
    agent = agent_service.activate_agent(agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found"
        )
    
    return agent


@router.post("/{agent_id}/deactivate", response_model=schemas.AgentResponse)
async def deactivate_agent(
    agent_id: str,
    current_user: User = Depends(get_current_user),
    agent_service: AgentService = Depends(get_service(AgentService)),
    zone_service: ZoneService = Depends(get_service(ZoneService)),
    world_service: WorldService = Depends(get_service(WorldService))
):
    """
    Deactivate an AI agent
    
    Returns the updated agent
    """
    agent = agent_service.get_agent(agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found"
        )
    
    # Check if agent is in a zone and user has owner access to the world
    if agent.zone_id:
        zone = zone_service.get_zone(agent.zone_id)
        if zone:
            world = world_service.get_world(zone.world_id)
            if not world or world.owner_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only the world owner can deactivate agents"
                )
    
    agent = agent_service.deactivate_agent(agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found"
        )
    
    return agent


@router.post("/{agent_id}/move", response_model=schemas.AgentResponse)
async def move_agent_to_zone(
    agent_id: str,
    zone_id: str = Query(..., description="ID of the destination zone"),
    current_user: User = Depends(get_current_user),
    agent_service: AgentService = Depends(get_service(AgentService)),
    zone_service: ZoneService = Depends(get_service(ZoneService)),
    world_service: WorldService = Depends(get_service(WorldService))
):
    """
    Move an agent to a different zone
    
    Checks that:
    1. The agent exists
    2. The destination zone exists and has capacity
    3. The user has permission to move the agent
    """
    # Check if agent exists
    agent = agent_service.get_agent(agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found"
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
            detail="Only the world owner can move agents"
        )
    
    # Move the agent
    success = agent_service.move_agent_to_zone(agent_id, zone_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to move agent. The zone may have reached its entity limit."
        )
    
    # Return the updated agent
    updated_agent = agent_service.get_agent(agent_id)
    return updated_agent