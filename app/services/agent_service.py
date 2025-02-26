# app/services/agent_service.py
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from typing import List, Optional, Dict, Any, Tuple
import math

from app.models.agent import Agent


class AgentService:
    """Service for handling AI agent operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_agent(self, name: str, description: str = None, system_prompt: str = None) -> Agent:
        """Create a new AI agent"""
        agent = Agent(
            name=name,
            description=description,
            system_prompt=system_prompt,
            is_active=True
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
            if 'is_active' in filters:
                query = query.filter(Agent.is_active == filters['is_active'])
            
            if 'name' in filters:
                query = query.filter(Agent.name.ilike(f"%{filters['name']}%"))
            
            if 'description' in filters:
                query = query.filter(Agent.description.ilike(f"%{filters['description']}%"))
            
            if 'ids' in filters and isinstance(filters['ids'], list):
                query = query.filter(Agent.id.in_(filters['ids']))
                
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
        
        # Update only the fields provided
        for key, value in update_data.items():
            if hasattr(agent, key):
                setattr(agent, key, value)
        
        self.db.commit()
        self.db.refresh(agent)
        
        return agent
    
    def delete_agent(self, agent_id: str) -> bool:
        """Delete an agent"""
        agent = self.get_agent(agent_id)
        if not agent:
            return False
        
        self.db.delete(agent)
        self.db.commit()
        
        return True
    
    def search_agents(self, 
                     query: str, 
                     include_inactive: bool = False,
                     page: int = 1, 
                     page_size: int = 20) -> Tuple[List[Agent], int, int]:
        """
        Search for agents by name or description
        
        Args:
            query: Search term
            include_inactive: Whether to include inactive agents
            page: Page number
            page_size: Results per page
        """
        filters = {'search': query}
        
        if not include_inactive:
            filters['is_active'] = True
        
        return self.get_agents(
            filters=filters,
            page=page,
            page_size=page_size
        )
    
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