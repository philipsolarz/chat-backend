# app/services/agent_service.py
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from typing import List, Optional, Dict, Any, Tuple
import math

from app.models.agent import Agent
from app.models.entity import EntityType
from app.models.zone import Zone
from app.services.entity_service import EntityService


class AgentService:
    """Service for handling AI agent operations"""
    
    def __init__(self, db: Session):
        self.db = db
        self.entity_service = EntityService(db)
    
    def create_agent(self, 
                    name: str, 
                    description: str = None, 
                    system_prompt: str = None, 
                    zone_id: Optional[str] = None,
                    settings: Optional[Dict[str, Any]] = None) -> Optional[Agent]:
        """
        Create a new AI agent entity
        
        Args:
            name: Name of the agent
            description: Optional description
            system_prompt: Optional system prompt for AI behavior
            zone_id: Optional zone ID to place the agent in
            settings: JSON settings for agent configuration
            
        Returns:
            The created agent or None if the zone has reached its entity limit
        """
        # If zone_id is provided, check the zone's entity limit
        if zone_id:
            zone = self.db.query(Zone).filter(Zone.id == zone_id).first()
            if not zone:
                return None
                
            # Check entity limit
            from app.services.zone_service import ZoneService
            zone_service = ZoneService(self.db)
            if not zone_service.can_add_entity_to_zone(zone_id):
                return None
        
        agent = Agent(
            name=name,
            description=description,
            type=EntityType.AGENT,
            system_prompt=system_prompt,
            is_active=True,
            zone_id=zone_id,
            settings=settings
        )
        
        self.db.add(agent)
        self.db.commit()
        self.db.refresh(agent)
        
        return agent
    
    def get_agent(self, agent_id: str) -> Optional[Agent]:
        """Get an agent by ID"""
        return self.db.query(Agent).filter(Agent.id == agent_id).first()
    
    def get_agents(self, 
                   filters: Dict[str, Any] = None, 
                   page: int = 1, 
                   page_size: int = 20, 
                   sort_by: str = "name", 
                   sort_desc: bool = False) -> Tuple[List[Agent], int, int]:
        """
        Get agents with flexible filtering options
        
        Args:
            filters: Dictionary of filter conditions
            page: Page number (starting from 1)
            page_size: Number of records per page
            sort_by: Field to sort by
            sort_desc: Whether to sort in descending order
            
        Returns:
            Tuple of (agents, total_count, total_pages)
        """
        # Start with entity type filter
        if filters is None:
            filters = {}
        filters['type'] = EntityType.AGENT
        
        # Get entities with basic filters
        entities, total_count, total_pages = self.entity_service.get_entities(
            filters=filters,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_desc=sort_desc
        )
        
        # Convert entities to agents
        agents = [entity for entity in entities if isinstance(entity, Agent)]
        
        # Apply agent-specific filters client-side
        if 'is_active' in filters:
            agents = [agent for agent in agents if agent.is_active == filters['is_active']]
        
        # Recalculate counts if we filtered further
        if 'is_active' in filters:
            total_count = len(agents)
            total_pages = (total_count + page_size - 1) // page_size
        
        return agents, total_count, total_pages
    
    def get_active_agents(self, page: int = 1, page_size: int = 20) -> Tuple[List[Agent], int, int]:
        """Get all active agents"""
        return self.get_agents(
            filters={'is_active': True},
            page=page,
            page_size=page_size
        )
    
    def update_agent(self, agent_id: str, update_data: Dict[str, Any]) -> Optional[Agent]:
        """Update an agent"""
        agent = self.get_agent(agent_id)
        if not agent:
            return None
        
        # Update only the fields provided
        for key, value in update_data.items():
            if hasattr(agent, key):
                setattr(agent, key, value)
        
        self.db.commit()
        self.db.refresh(agent)
        
        return agent
    
    def delete_agent(self, agent_id: str) -> bool:
        """Delete an agent"""
        return self.entity_service.delete_entity(agent_id)
    
    def search_agents(self, 
                     query: str, 
                     include_inactive: bool = False,
                     zone_id: Optional[str] = None,
                     page: int = 1, 
                     page_size: int = 20) -> Tuple[List[Agent], int, int]:
        """
        Search for agents by name or description
        
        Args:
            query: Search term
            include_inactive: Whether to include inactive agents
            zone_id: Optional zone ID to search within
            page: Page number
            page_size: Results per page
        """
        # Start with entity search
        entities, total_count, total_pages = self.entity_service.search_entities(
            query=query,
            zone_id=zone_id,
            entity_type=EntityType.AGENT,
            page=page,
            page_size=page_size
        )
        
        # Convert entities to agents
        agents = [entity for entity in entities if isinstance(entity, Agent)]
        
        # Filter by active status if needed
        if not include_inactive:
            agents = [agent for agent in agents if agent.is_active]
            
            # Recalculate counts if we filtered further
            total_count = len(agents)
            total_pages = (total_count + page_size - 1) // page_size
        
        return agents, total_count, total_pages
    
    def count_agents(self, include_inactive: bool = False) -> int:
        """
        Count the number of agents
        
        Args:
            include_inactive: Whether to include inactive agents
        """
        query = self.db.query(func.count(Agent.id))
        
        if not include_inactive:
            query = query.filter(Agent.is_active == True)
        
        return query.scalar() or 0
    
    def activate_agent(self, agent_id: str) -> Optional[Agent]:
        """Activate an agent"""
        return self.update_agent(agent_id, {"is_active": True})
    
    def deactivate_agent(self, agent_id: str) -> Optional[Agent]:
        """Deactivate an agent"""
        return self.update_agent(agent_id, {"is_active": False})
    
    def move_agent_to_zone(self, agent_id: str, zone_id: str) -> bool:
        """
        Move an agent to a different zone
        
        Args:
            agent_id: ID of the agent to move
            zone_id: ID of the destination zone
            
        Returns:
            True if successful, False if the zone has reached its entity limit
        """
        return self.entity_service.move_entity_to_zone(agent_id, zone_id)