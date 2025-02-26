# app/api/v1/agents.py
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database import get_db
from app.api import schemas
from app.api.auth import get_current_user
from app.api.dependencies import get_service
from app.services.agent_service import AgentService
from app.models.user import User
from app.models.agent import Agent

router = APIRouter()


@router.get("/", response_model=schemas.AgentList)
async def list_agents(
    is_active: Optional[bool] = None,
    name: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = Query("name"),
    sort_desc: bool = Query(False),
    current_user: User = Depends(get_current_user),
    agent_service: AgentService = Depends(get_service(AgentService))
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
    agent_service: AgentService = Depends(get_service(AgentService))
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
    
    return agent


@router.get("/search/", response_model=schemas.AgentList)
async def search_agents(
    query: str = Query(..., min_length=1),
    include_inactive: bool = Query(False, title="Include inactive agents in results"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    agent_service: AgentService = Depends(get_service(AgentService))
):
    """
    Search for AI agents by name or description
    
    Returns a paginated list of matching agents
    """
    agents, total_count, total_pages = agent_service.search_agents(
        query=query,
        include_inactive=include_inactive,
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


# Admin-only routes (these would require special permissions in a production app)
# For simplicity, we're allowing any authenticated user to access these in this demo

@router.post("/", response_model=schemas.AgentResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(
    agent: schemas.AgentCreate,
    current_user: User = Depends(get_current_user),
    agent_service: AgentService = Depends(get_service(AgentService))
):
    """
    Create a new AI agent (admin only)
    
    Returns the created agent
    """
    return agent_service.create_agent(
        name=agent.name,
        description=agent.description,
        system_prompt=agent.system_prompt
    )


@router.put("/{agent_id}", response_model=schemas.AgentResponse)
async def update_agent(
    agent_id: str,
    agent_update: schemas.AgentUpdate,
    current_user: User = Depends(get_current_user),
    agent_service: AgentService = Depends(get_service(AgentService))
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
    agent_service: AgentService = Depends(get_service(AgentService))
):
    """
    Delete an AI agent (admin only)
    
    Returns no content on success
    """
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
    agent_service: AgentService = Depends(get_service(AgentService))
):
    """
    Activate an AI agent (admin only)
    
    Returns the updated agent
    """
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
    agent_service: AgentService = Depends(get_service(AgentService))
):
    """
    Deactivate an AI agent (admin only)
    
    Returns the updated agent
    """
    agent = agent_service.deactivate_agent(agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found"
        )
    
    return agent