# app/services/zone_service.py
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, func, desc
from typing import List, Optional, Dict, Any, Tuple
import math

from app.models.zone import Zone
from app.models.world import World
from app.models.character import Character
from app.models.agent import Agent


class ZoneService:
    """Service for handling zone operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_zone(self, 
                   world_id: str,
                   name: str,
                   description: Optional[str] = None,
                   zone_type: Optional[str] = None,
                   coordinates: Optional[str] = None,
                   properties: Optional[str] = None,
                   parent_zone_id: Optional[str] = None) -> Optional[Zone]:
        """
        Create a new zone
        
        Args:
            world_id: ID of the world this zone belongs to
            name: Name of the zone
            description: Description of the zone
            zone_type: Type of zone (city, forest, dungeon, etc.)
            coordinates: Geographic coordinates (implementation-specific)
            properties: Additional zone properties (could be JSON)
            parent_zone_id: ID of the parent zone (for sub-zones)
            
        Returns:
            The created zone or None if zone limit is reached
        """
        # Get the world to check zone limits
        world = self.db.query(World).filter(World.id == world_id).first()
        if not world:
            return None
        
        # Check zone limit
        zone_count = self.db.query(Zone).filter(Zone.world_id == world_id).count()
        if zone_count >= world.total_zone_limit:
            return None
        
        # Validate parent zone if provided
        if parent_zone_id:
            parent_zone = self.db.query(Zone).filter(
                Zone.id == parent_zone_id,
                Zone.world_id == world_id  # Ensure parent zone is in the same world
            ).first()
            
            if not parent_zone:
                return None
        
        # Create zone
        zone = Zone(
            name=name,
            description=description,
            zone_type=zone_type,
            coordinates=coordinates,
            properties=properties,
            world_id=world_id,
            parent_zone_id=parent_zone_id
        )
        
        self.db.add(zone)
        self.db.commit()
        self.db.refresh(zone)
        
        return zone
    
    def get_zone(self, zone_id: str) -> Optional[Zone]:
        """Get a zone by ID"""
        return self.db.query(Zone).filter(Zone.id == zone_id).first()
    
    def get_zones(self, 
                 filters: Dict[str, Any] = None, 
                 page: int = 1, 
                 page_size: int = 20, 
                 sort_by: str = "name", 
                 sort_desc: bool = False) -> Tuple[List[Zone], int, int]:
        """
        Get zones with flexible filtering options
        
        Args:
            filters: Dictionary of filter conditions
            page: Page number (starting from 1)
            page_size: Number of records per page
            sort_by: Field to sort by
            sort_desc: Whether to sort in descending order
            
        Returns:
            Tuple of (zones, total_count, total_pages)
        """
        query = self.db.query(Zone)
        
        # Apply filters if provided
        if filters:
            if 'world_id' in filters:
                query = query.filter(Zone.world_id == filters['world_id'])
            
            if 'name' in filters:
                query = query.filter(Zone.name.ilike(f"%{filters['name']}%"))
            
            if 'description' in filters:
                query = query.filter(Zone.description.ilike(f"%{filters['description']}%"))
            
            if 'zone_type' in filters:
                query = query.filter(Zone.zone_type == filters['zone_type'])
            
            if 'parent_zone_id' in filters:
                if filters['parent_zone_id'] is None:
                    # Get top-level zones (no parent)
                    query = query.filter(Zone.parent_zone_id.is_(None))
                else:
                    # Get sub-zones of a specific parent
                    query = query.filter(Zone.parent_zone_id == filters['parent_zone_id'])
                
            if 'search' in filters and filters['search']:
                search_term = f"%{filters['search']}%"
                query = query.filter(
                    or_(
                        Zone.name.ilike(search_term),
                        Zone.description.ilike(search_term)
                    )
                )
        
        # Get total count before pagination
        total_count = query.count()
        total_pages = math.ceil(total_count / page_size) if total_count > 0 else 1
        
        # Apply sorting
        if hasattr(Zone, sort_by):
            sort_field = getattr(Zone, sort_by)
            query = query.order_by(sort_field.desc() if sort_desc else sort_field)
        else:
            # Default to name
            query = query.order_by(Zone.name.desc() if sort_desc else Zone.name)
        
        # Apply pagination - convert page to offset
        offset = (page - 1) * page_size if page > 0 else 0
        
        # Get paginated results
        zones = query.offset(offset).limit(page_size).all()
        
        return zones, total_count, total_pages
    
    def get_world_zones(self, world_id: str, parent_zone_id: Optional[str] = None, include_subzones: bool = False) -> List[Zone]:
        """
        Get zones for a specific world, optionally filtered by parent zone
        
        Args:
            world_id: ID of the world
            parent_zone_id: ID of the parent zone (for sub-zones), or None for top-level zones
            include_subzones: Whether to include all subzones recursively (ignores pagination)
            
        Returns:
            List of zones
        """
        if include_subzones and parent_zone_id:
            # Get the parent zone and all its descendants using recursive CTE
            # This is advanced SQL and might need to be adapted based on your DB
            # For now, we'll use a simpler approach
            
            # First get the parent zone
            parent_zone = self.get_zone(parent_zone_id)
            if not parent_zone:
                return []
                
            # Then get all zones in this world and filter client-side
            all_zones = self.db.query(Zone).filter(Zone.world_id == world_id).all()
            
            # Build a dictionary mapping parent IDs to children
            parent_to_children = {}
            for zone in all_zones:
                parent_id = zone.parent_zone_id
                if parent_id not in parent_to_children:
                    parent_to_children[parent_id] = []
                parent_to_children[parent_id].append(zone)
            
            # Now collect all zones recursively
            result = []
            
            def collect_zones(zone_id):
                children = parent_to_children.get(zone_id, [])
                for child in children:
                    result.append(child)
                    collect_zones(child.id)
            
            # Start collection from the parent zone
            result.append(parent_zone)
            collect_zones(parent_zone_id)
            
            return result
            
        else:
            # Simple filtering by world_id and parent_zone_id
            query = self.db.query(Zone).filter(Zone.world_id == world_id)
            
            if parent_zone_id is not None:
                query = query.filter(Zone.parent_zone_id == parent_zone_id)
            else:
                query = query.filter(Zone.parent_zone_id.is_(None))
                
            return query.order_by(Zone.name).all()
    
    def update_zone(self, zone_id: str, update_data: Dict[str, Any]) -> Optional[Zone]:
        """Update a zone"""
        zone = self.get_zone(zone_id)
        if not zone:
            return None
        
        # Validate parent zone if being changed
        if 'parent_zone_id' in update_data and update_data['parent_zone_id'] is not None:
            # Check for circular reference
            if update_data['parent_zone_id'] == zone_id:
                return None  # Cannot be its own parent
                
            parent_zone = self.db.query(Zone).filter(
                Zone.id == update_data['parent_zone_id'],
                Zone.world_id == zone.world_id  # Ensure parent zone is in the same world
            ).first()
            
            if not parent_zone:
                return None
                
            # Check if the new parent is not one of this zone's descendants
            if self.is_descendant(update_data['parent_zone_id'], zone_id):
                return None  # Would create a circular reference
        
        # Update only the fields provided
        for key, value in update_data.items():
            if hasattr(zone, key):
                setattr(zone, key, value)
        
        self.db.commit()
        self.db.refresh(zone)
        
        return zone
    
    def delete_zone(self, zone_id: str) -> bool:
        """
        Delete a zone
        
        If the zone has sub-zones:
        1. Those sub-zones will have their parent_zone_id set to the deleted zone's parent_zone_id
        2. If the deleted zone has no parent, its sub-zones will become top-level zones
        
        If the zone has characters or agents:
        1. They will be moved to the parent zone
        2. If there's no parent zone, they will need to be moved manually first (can't delete)
        """
        zone = self.get_zone(zone_id)
        if not zone:
            return False
        
        # Handle characters and agents in this zone
        characters = self.db.query(Character).filter(Character.zone_id == zone_id).all()
        agents = self.db.query(Agent).filter(Agent.zone_id == zone_id).all()
        
        if (characters or agents) and not zone.parent_zone_id:
            # Can't delete a zone with entities if it has no parent to move them to
            return False
        
        # Move entities to parent zone if needed
        if zone.parent_zone_id:
            for character in characters:
                character.zone_id = zone.parent_zone_id
                
            for agent in agents:
                agent.zone_id = zone.parent_zone_id
        
        # Handle sub-zones
        sub_zones = self.db.query(Zone).filter(Zone.parent_zone_id == zone_id).all()
        for sub_zone in sub_zones:
            sub_zone.parent_zone_id = zone.parent_zone_id
        
        # Delete the zone
        self.db.delete(zone)
        self.db.commit()
        
        return True
    
    def move_character_to_zone(self, character_id: str, zone_id: str) -> bool:
        """Move a character to a different zone"""
        character = self.db.query(Character).filter(Character.id == character_id).first()
        zone = self.get_zone(zone_id)
        
        if not character or not zone:
            return False
        
        # Ensure the zone is in the same world as the character
        if character.world_id != zone.world_id:
            return False
        
        character.zone_id = zone_id
        self.db.commit()
        
        return True
    
    def move_agent_to_zone(self, agent_id: str, zone_id: str) -> bool:
        """Move an agent (NPC) to a different zone"""
        agent = self.db.query(Agent).filter(Agent.id == agent_id).first()
        zone = self.get_zone(zone_id)
        
        if not agent or not zone:
            return False
        
        agent.zone_id = zone_id
        self.db.commit()
        
        return True
    
    def get_characters_in_zone(self, zone_id: str) -> List[Character]:
        """Get all characters in a specific zone"""
        return self.db.query(Character).filter(Character.zone_id == zone_id).all()
    
    def get_agents_in_zone(self, zone_id: str) -> List[Agent]:
        """Get all agents (NPCs) in a specific zone"""
        return self.db.query(Agent).filter(Agent.zone_id == zone_id).all()
    
    def is_descendant(self, potential_descendant_id: str, ancestor_id: str) -> bool:
        """
        Check if a zone is a descendant of another zone
        
        Args:
            potential_descendant_id: ID of the zone to check
            ancestor_id: ID of the potential ancestor
            
        Returns:
            True if potential_descendant_id is a descendant of ancestor_id
        """
        # Get the potential descendant
        zone = self.get_zone(potential_descendant_id)
        if not zone:
            return False
            
        # Check its parent chain
        while zone.parent_zone_id:
            if zone.parent_zone_id == ancestor_id:
                return True
                
            zone = self.get_zone(zone.parent_zone_id)
            if not zone:
                break
                
        return False
    
    def count_zones_in_world(self, world_id: str) -> int:
        """Count the number of zones in a world"""
        return self.db.query(func.count(Zone.id)).filter(Zone.world_id == world_id).scalar() or 0
    
    def upgrade_world_zone_limit(self, world_id: str) -> bool:
        """Increase a world's zone limit by purchasing an upgrade"""
        world = self.db.query(World).filter(World.id == world_id).first()
        if not world:
            return False
            
        world.zone_limit_upgrades += 1
        self.db.commit()
        
        return True
    
    def count_agents_in_zone(self, zone_id: str) -> int:
        """Count the number of agents in a zone"""
        from app.models.agent import Agent
        return self.db.query(func.count(Agent.id)).filter(Agent.zone_id == zone_id).scalar() or 0

    def can_add_agent_to_zone(self, zone_id: str) -> bool:
        """Check if a zone has reached its agent limit"""
        zone = self.get_zone(zone_id)
        if not zone:
            return False
            
        agent_count = self.count_agents_in_zone(zone_id)
        return agent_count < zone.total_agent_limit

    def get_zone_agent_limits(self, zone_id: str) -> Dict[str, Any]:
        """Get agent limit information for a zone"""
        zone = self.get_zone(zone_id)
        if not zone:
            return None
            
        agent_count = self.count_agents_in_zone(zone_id)
        
        return {
            "agent_count": agent_count,
            "base_limit": zone.agent_limit,
            "upgrades_purchased": zone.agent_limit_upgrades,
            "total_limit": zone.total_agent_limit,
            "remaining_capacity": zone.total_agent_limit - agent_count
        }

    def upgrade_zone_agent_limit(self, zone_id: str) -> bool:
        """Increase a zone's agent limit by purchasing an upgrade"""
        zone = self.get_zone(zone_id)
        if not zone:
            return False
            
        zone.agent_limit_upgrades += 1
        self.db.commit()
        
        return True