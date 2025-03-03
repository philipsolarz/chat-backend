# app/services/agent_service.py
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from typing import List, Optional, Dict, Any, Tuple
import math

from app.models.agent import Agent
from app.models.enums import CharacterType
from app.models.character import Character

class AgentService:
    """Service for handling AI agent operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_agent(self, 
                     name: str, 
                     description: Optional[str] = None,
                     zone_id: Optional[str] = None,
                     settings: Optional[Dict[str, Any]] = None) -> Optional[Agent]:
        """
        Create a new AI agent and its associated agent-controlled character.
        
        Args:
            name: Name of the agent.
            description: Optional description.
            zone_id: Zone ID where the agent's character will be placed.
            settings: JSON settings for agent configuration.
        
        Returns:
            The created Agent instance.
        """
        # Create the Agent record
        agent = Agent(
            name=name,
            description=description,
            properties=settings,  # agent-specific properties
            tier=1
        )
        self.db.add(agent)
        self.db.commit()
        self.db.refresh(agent)
        
        # Create the associated Character record for the agent
        character = Character(
            name=name,
            description=description,
            zone_id=zone_id,  # zone is required on the character
            character_type=CharacterType.AGENT,
            settings=settings,
            agent_id=agent.id
        )
        self.db.add(character)
        self.db.commit()
        self.db.refresh(character)
        
        # Link the agent to its character (bidirectional relationship)
        agent.character = character
        self.db.commit()
        
        return agent
    
    def get_agent(self, agent_id: str) -> Optional[Agent]:
        """Get an agent by ID"""
        return self.db.query(Agent).filter(Agent.id == agent_id).first()
    
    def get_agents(self, 
                   filters: Optional[Dict[str, Any]] = None, 
                   page: int = 1, 
                   page_size: int = 20, 
                   sort_by: str = "name", 
                   sort_desc: bool = False) -> Tuple[List[Agent], int, int]:
        """
        Get agents with flexible filtering options.
        
        Args:
            filters: Dictionary of filter conditions.
            page: Page number (starting from 1).
            page_size: Number of records per page.
            sort_by: Field to sort by.
            sort_desc: Whether to sort in descending order.
            
        Returns:
            Tuple of (agents, total_count, total_pages)
        """
        query = self.db.query(Agent)
        
        if filters:
            if 'zone_id' in filters:
                # Join with the associated Character to filter by zone_id.
                query = query.join(Agent.character).filter(Character.zone_id == filters['zone_id'])
            
            if 'name' in filters:
                query = query.filter(Agent.name.ilike(f"%{filters['name']}%"))
            
            if 'description' in filters:
                query = query.filter(Agent.description.ilike(f"%{filters['description']}%"))
            
            if 'search' in filters and filters['search']:
                search_term = f"%{filters['search']}%"
                query = query.filter(
                    or_(
                        Agent.name.ilike(search_term),
                        Agent.description.ilike(search_term)
                    )
                )
        
        total_count = query.count()
        total_pages = math.ceil(total_count / page_size) if total_count > 0 else 1
        
        if hasattr(Agent, sort_by):
            sort_field = getattr(Agent, sort_by)
            query = query.order_by(sort_field.desc() if sort_desc else sort_field)
        else:
            query = query.order_by(Agent.name.desc() if sort_desc else Agent.name)
        
        offset = (page - 1) * page_size if page > 0 else 0
        agents = query.offset(offset).limit(page_size).all()
        
        return agents, total_count, total_pages
    
    def update_agent(self, agent_id: str, update_data: Dict[str, Any]) -> Optional[Agent]:
        """
        Update an agent and its associated character record if applicable.
        
        Args:
            agent_id: ID of the agent to update.
            update_data: Dictionary of fields to update.
        
        Returns:
            The updated Agent instance or None if not found.
        """
        agent = self.get_agent(agent_id)
        if not agent:
            return None
        
        # Update associated character (if it exists)
        character = agent.character
        if character:
            if 'name' in update_data:
                character.name = update_data['name']
            if 'description' in update_data:
                character.description = update_data['description']
            if 'zone_id' in update_data:
                character.zone_id = update_data['zone_id']
            if 'settings' in update_data:
                character.settings = update_data['settings']
        
        # Update agent-specific fields (skip overlapping keys handled above)
        for key, value in update_data.items():
            if hasattr(agent, key) and key not in ['name', 'description']:
                setattr(agent, key, value)
        
        self.db.commit()
        self.db.refresh(agent)
        if character:
            self.db.refresh(character)
        
        return agent
    
    def delete_agent(self, agent_id: str) -> bool:
        """
        Delete an agent and its associated character.
        
        Args:
            agent_id: ID of the agent to delete.
        
        Returns:
            True if deletion was successful, False otherwise.
        """
        agent = self.get_agent(agent_id)
        if not agent:
            return False
        
        # Delete the associated character first (if exists)
        character = agent.character
        if character:
            self.db.delete(character)
            self.db.commit()
        
        self.db.delete(agent)
        self.db.commit()
        return True
    
    def search_agents(self, 
                      query_str: str,
                      zone_id: Optional[str] = None,
                      page: int = 1, 
                      page_size: int = 20) -> Tuple[List[Agent], int, int]:
        """
        Search for agents by name or description.
        
        Args:
            query_str: Search term.
            zone_id: Optional zone ID filter.
            page: Page number.
            page_size: Number of results per page.
        
        Returns:
            Tuple of (agents, total_count, total_pages)
        """
        filters = {'search': query_str}
        if zone_id:
            filters['zone_id'] = zone_id
        
        return self.get_agents(filters=filters, page=page, page_size=page_size)
    
    def count_agents(self) -> int:
        """Count the number of agents."""
        return self.db.query(func.count(Agent.id)).scalar() or 0
    
    def move_agent_to_zone(self, agent_id: str, zone_id: str) -> bool:
        """
        Move an agent to a different zone by updating its associated character.
        
        Args:
            agent_id: ID of the agent.
            zone_id: Destination zone ID.
        
        Returns:
            True if successful, False otherwise.
        """
        agent = self.get_agent(agent_id)
        if not agent or not agent.character:
            return False
        
        # Here, you might add validations (e.g., checking zone capacity)
        agent.character.zone_id = zone_id
        self.db.commit()
        return True
        
    def upgrade_agent_tier(self, agent_id: str) -> bool:
        """
        Upgrade an agent's tier.
        
        Args:
            agent_id: ID of the agent to upgrade.
        
        Returns:
            True if successful, False otherwise.
        """
        agent = self.get_agent(agent_id)
        if not agent:
            return False
        
        agent.tier += 1
        self.db.commit()
        return True
