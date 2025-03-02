# app/services/agent_service.py
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from typing import List, Optional, Dict, Any, Tuple
import math

from app.models.agent import Agent
from app.models.entity import EntityType
from app.models.zone import Zone


class AgentService:
    """Service for handling AI agent operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_agent(self, 
                    name: str, 
                    description: str = None,
                    zone_id: Optional[str] = None,
                    world_id: Optional[str] = None,
                    settings: Optional[Dict[str, Any]] = None) -> Optional[Agent]:
        """
        Create a new AI agent entity
        
        Args:
            name: Name of the agent
            description: Optional description
            zone_id: Optional zone ID to place the agent in
            world_id: Optional world ID for the agent
            settings: JSON settings for agent configuration
            
        Returns:
            The created agent or None if the zone has reached its entity limit
        """
        # First, create an entity
        from app.services.entity_service import EntityService
        entity_service = EntityService(self.db)
        
        entity = entity_service.create_entity(
            name=name,
            description=description,
            entity_type=EntityType.AGENT,
            zone_id=zone_id,
            world_id=world_id
        )
        
        if not entity:
            return None  # Failed to create entity (e.g., zone reached limit)
        
        # Create agent with default tier 1
        agent = Agent(
            name=name,
            description=description,
            zone_id=zone_id,
            world_id=world_id,
            entity_id=entity.id,
            settings=settings,
            tier=1  # Default tier for new agents
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
        query = self.db.query(Agent)
        
        # Apply filters if provided
        if filters:
            if 'zone_id' in filters:
                query = query.filter(Agent.zone_id == filters['zone_id'])
                
            if 'world_id' in filters:
                query = query.filter(Agent.world_id == filters['world_id'])
            
            if 'name' in filters:
                query = query.filter(Agent.name.ilike(f"%{filters['name']}%"))
            
            if 'description' in filters:
                query = query.filter(Agent.description.ilike(f"%{filters['description']}%"))
            
            if 'is_active' in filters:
                query = query.filter(Agent.is_active == filters['is_active'])
                
            if 'search' in filters and filters['search']:
                search_term = f"%{filters['search']}%"
                query = query.filter(
                    or_(
                        Agent.name.ilike(search_term),
                        Agent.description.ilike(search_term)
                    )
                )
        
        # Get total count before pagination
        total_count = query.count()
        total_pages = math.ceil(total_count / page_size) if total_count > 0 else 1
        
        # Apply sorting
        if hasattr(Agent, sort_by):
            sort_field = getattr(Agent, sort_by)
            query = query.order_by(sort_field.desc() if sort_desc else sort_field)
        else:
            # Default to name
            query = query.order_by(Agent.name.desc() if sort_desc else Agent.name)
        
        # Apply pagination - convert page to offset
        offset = (page - 1) * page_size if page > 0 else 0
        
        # Get paginated results
        agents = query.offset(offset).limit(page_size).all()
        
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
        
        # If we're updating basic properties, update the entity as well
        entity = None
        entity_updates = {}
        if agent.entity_id:
            from app.models.entity import Entity
            entity = self.db.query(Entity).filter(Entity.id == agent.entity_id).first()
            
            if entity:
                # Collect entity updates
                if 'name' in update_data:
                    entity_updates['name'] = update_data['name']
                if 'description' in update_data:
                    entity_updates['description'] = update_data['description']
                
                # Apply entity updates
                for key, value in entity_updates.items():
                    setattr(entity, key, value)
        
        # Update agent fields
        for key, value in update_data.items():
            if hasattr(agent, key):
                setattr(agent, key, value)
        
        self.db.commit()
        
        if agent:
            self.db.refresh(agent)
        if entity:
            self.db.refresh(entity)
        
        return agent
    
    def delete_agent(self, agent_id: str) -> bool:
        """Delete an agent and its associated entity"""
        agent = self.get_agent(agent_id)
        if not agent:
            return False
        
        # Get the associated entity
        entity_id = agent.entity_id
        
        # Delete the agent
        self.db.delete(agent)
        self.db.commit()
        
        # Delete the associated entity if it exists
        if entity_id:
            from app.models.entity import Entity
            entity = self.db.query(Entity).filter(Entity.id == entity_id).first()
            if entity:
                self.db.delete(entity)
                self.db.commit()
        
        return True
    
    def search_agents(self, 
                     query: str,
                     zone_id: Optional[str] = None,
                     world_id: Optional[str] = None,
                     page: int = 1, 
                     page_size: int = 20) -> Tuple[List[Agent], int, int]:
        """
        Search for agents by name or description
        
        Args:
            query: Search term
            include_inactive: Whether to include inactive agents
            zone_id: Optional zone ID to search within
            world_id: Optional world ID to search within
            page: Page number
            page_size: Results per page
        """
        # Start with basic search filter
        filters = {'search': query}
        
        # Add optional filters
        if zone_id:
            filters['zone_id'] = zone_id
            
        if world_id:
            filters['world_id'] = world_id

        return self.get_agents(
            filters=filters,
            page=page,
            page_size=page_size
        )
    
    def count_agents(self) -> int:
        """
        Count the number of agents
        
        Args:
            include_inactive: Whether to include inactive agents
        """
        query = self.db.query(func.count(Agent.id))

        return query.scalar() or 0

    def move_agent_to_zone(self, agent_id: str, zone_id: str) -> bool:
        """
        Move an agent to a different zone
        
        Args:
            agent_id: ID of the agent to move
            zone_id: ID of the destination zone
            
        Returns:
            True if successful, False if the zone has reached its entity limit
        """
        agent = self.get_agent(agent_id)
        if not agent or not agent.entity_id:
            return False
            
        # Use EntityService to move the underlying entity
        from app.services.entity_service import EntityService
        entity_service = EntityService(self.db)
        
        if entity_service.move_entity_to_zone(agent.entity_id, zone_id):
            # Update the agent's zone_id to match
            agent.zone_id = zone_id
            self.db.commit()
            return True
        
        return False
        
    def upgrade_agent_tier(self, agent_id: str) -> bool:
        """
        Upgrade an agent's tier
        
        Args:
            agent_id: ID of the agent to upgrade
            
        Returns:
            True if successful, False otherwise
        """
        agent = self.get_agent(agent_id)
        if not agent:
            return False
            
        # Increment tier
        agent.tier += 1
        self.db.commit()
        
        # Also upgrade the entity if present
        if agent.entity_id:
            from app.services.entity_service import EntityService
            entity_service = EntityService(self.db)
            entity_service.upgrade_entity_tier(agent.entity_id)
        
        return True