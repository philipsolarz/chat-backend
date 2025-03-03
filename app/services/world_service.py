# app/services/world_service.py
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import List, Optional, Dict, Any, Tuple
import math

from app.models.world import World
from app.models.player import Player

class WorldService:
    """Service for handling world operations."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_world(
        self, 
        owner_id: str, 
        name: str, 
        description: Optional[str] = None,
        settings: Optional[Dict[str, Any]] = None,
        tier: int = 1,
        is_official: bool = False,
        is_private: bool = False
    ) -> World:
        """
        Create a new world.
        
        Args:
            owner_id: ID of the user creating the world (owner).
            name: Name of the world.
            description: Description of the world.
            settings: JSON settings for world configuration.
            tier: Initial tier level (defaults to 1).
            is_official: Whether this is an official world (defaults to False).
            is_private: Whether this world is private (defaults to False).
        """
        world = World(
            name=name,
            description=description,
            properties=settings,
            owner_id=owner_id,
            tier=tier,
            is_official=is_official,
            is_private=is_private
        )
        self.db.add(world)
        self.db.commit()
        self.db.refresh(world)
        return world
    
    def get_world(self, world_id: str) -> Optional[World]:
        """Get a world by its ID."""
        return self.db.query(World).filter(World.id == world_id).first()
    
    def get_worlds(
        self, 
        filters: Dict[str, Any] = None, 
        page: int = 1, 
        page_size: int = 20, 
        sort_by: str = "name", 
        sort_desc: bool = False
    ) -> Tuple[List[World], int, int]:
        """
        Get worlds with flexible filtering options.
        
        Args:
            filters: Dictionary of filter conditions.
            page: Page number (starting from 1).
            page_size: Number of records per page.
            sort_by: Field to sort by.
            sort_desc: Whether to sort in descending order.
            
        Returns:
            Tuple of (worlds, total_count, total_pages).
        """
        query = self.db.query(World)
        
        if filters:
            if 'owner_id' in filters:
                query = query.filter(World.owner_id == filters['owner_id'])
            if 'name' in filters:
                query = query.filter(World.name.ilike(f"%{filters['name']}%"))
            if 'description' in filters:
                query = query.filter(World.description.ilike(f"%{filters['description']}%"))
            if 'tier' in filters:
                query = query.filter(World.tier == filters['tier'])
            if 'is_official' in filters:
                query = query.filter(World.is_official == filters['is_official'])
            if 'is_private' in filters:
                query = query.filter(World.is_private == filters['is_private'])
            if 'search' in filters and filters['search']:
                search_term = f"%{filters['search']}%"
                query = query.filter(
                    or_(
                        World.name.ilike(search_term),
                        World.description.ilike(search_term)
                    )
                )
        
        total_count = query.count()
        total_pages = math.ceil(total_count / page_size) if total_count > 0 else 1
        
        if hasattr(World, sort_by):
            sort_field = getattr(World, sort_by)
            query = query.order_by(sort_field.desc() if sort_desc else sort_field)
        else:
            query = query.order_by(World.name.desc() if sort_desc else World.name)
        
        offset = (page - 1) * page_size if page > 0 else 0
        worlds = query.offset(offset).limit(page_size).all()
        
        return worlds, total_count, total_pages
    
    def get_user_worlds(self, user_id: str, page: int = 1, page_size: int = 20) -> Tuple[List[World], int, int]:
        """Get all worlds owned by a specific user."""
        return self.get_worlds(
            filters={'owner_id': user_id},
            page=page,
            page_size=page_size
        )
    
    def update_world(self, world_id: str, update_data: Dict[str, Any]) -> Optional[World]:
        """Update properties of a world."""
        world = self.get_world(world_id)
        if not world:
            return None
        
        # Only update provided fields
        for key, value in update_data.items():
            if hasattr(world, key):
                setattr(world, key, value)
        
        self.db.commit()
        self.db.refresh(world)
        return world
    
    def delete_world(self, world_id: str) -> bool:
        """
        Delete a world and all its associated content.
        Cascade deletion on relationships (like zones) will be handled by the ORM.
        """
        world = self.get_world(world_id)
        if not world:
            return False
        
        self.db.delete(world)
        self.db.commit()
        return True
    
    def check_user_access(self, user_id: str, world_id: str) -> bool:
        """
        Check if a user has access to a world (as owner, admin, or for public worlds).
        """
        world = self.get_world(world_id)
        if not world:
            return False
        
        # Owner always has access.
        if world.owner_id == user_id:
            return True
        
        # Check if user is admin.
        user = self.db.query(Player).filter(Player.id == user_id).first()
        if user and user.is_admin:
            return True
            
        # For private worlds, only owner or admin may access.
        if world.is_private:
            return False
            
        # Public worlds are accessible.
        return True
    
    def search_worlds(
        self, 
        query_str: str, 
        user_id: Optional[str] = None, 
        page: int = 1, 
        page_size: int = 20,
        include_private: bool = False
    ) -> Tuple[List[World], int, int]:
        """
        Search worlds by name or description.
        
        Args:
            query_str: Search term.
            user_id: If provided, restrict to worlds owned by this user.
            page: Page number.
            page_size: Number of results per page.
            include_private: Whether to include private worlds.
        """
        filters = {'search': query_str}
        if user_id:
            filters['owner_id'] = user_id
        if not include_private:
            filters['is_private'] = False
        
        return self.get_worlds(
            filters=filters,
            page=page,
            page_size=page_size
        )
    
    def calculate_zone_limit(self, tier: int) -> int:
        """
        Calculate the maximum number of zones allowed in a world based on its tier.
        """
        BASE_ZONE_LIMIT = 10
        return BASE_ZONE_LIMIT * tier
    
    def get_world_zone_limit(self, world_id: str) -> int:
        """
        Get the zone limit for a specific world.
        """
        world = self.get_world(world_id)
        if not world:
            return 0
        return self.calculate_zone_limit(world.tier)
    
    def upgrade_world_tier(self, world_id: str) -> bool:
        """
        Upgrade a world's tier.
        """
        world = self.get_world(world_id)
        if not world:
            return False
        
        world.tier += 1
        self.db.commit()
        return True
    
    def can_add_zone_to_world(self, world_id: str) -> bool:
        """
        Check if a world has not yet reached its zone limit.
        """
        world = self.get_world(world_id)
        if not world:
            return False
        
        # Assume ZoneService is updated to match our new Zone model.
        from app.services.zone_service import ZoneService
        zone_service = ZoneService(self.db)
        zone_count = zone_service.count_zones_in_world(world_id)
        
        zone_limit = self.calculate_zone_limit(world.tier)
        return zone_count < zone_limit
        
    def get_world_zone_usage(self, world_id: str) -> Dict[str, Any]:
        """
        Retrieve zone usage statistics for a world.
        """
        world = self.get_world(world_id)
        if not world:
            return {
                "zone_count": 0,
                "zone_limit": 0,
                "remaining_capacity": 0,
                "usage_percentage": 0,
                "tier": 0
            }
        
        from app.services.zone_service import ZoneService
        zone_service = ZoneService(self.db)
        zone_count = zone_service.count_zones_in_world(world_id)
        zone_limit = self.calculate_zone_limit(world.tier)
        remaining_capacity = max(0, zone_limit - zone_count)
        usage_percentage = (zone_count / zone_limit * 100) if zone_limit > 0 else 100
        
        return {
            "zone_count": zone_count,
            "zone_limit": zone_limit,
            "remaining_capacity": remaining_capacity,
            "usage_percentage": round(usage_percentage, 2),
            "tier": world.tier
        }
