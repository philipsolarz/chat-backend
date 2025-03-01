# app/services/world_service.py
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, func
from typing import List, Optional, Dict, Any, Tuple
import math

from app.models.world import World
from app.models.player import User

# Import the updated name (Player instead of User)
# Note: The model name in the database may still be User until migrated
from app.models.player import Player


class WorldService:
    """Service for handling world operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_world(self, 
                    owner_id: str, 
                    name: str, 
                    description: Optional[str] = None,
                    settings: Optional[Dict[str, Any]] = None,
                    genre: Optional[str] = None,
                    is_premium: bool = False,
                    price: Optional[float] = None) -> World:
        """
        Create a new world
        
        Args:
            owner_id: ID of the user creating the world (owner)
            name: Name of the world
            description: Description of the world
            settings: JSON settings for world configuration
            genre: Optional genre for the world
            is_premium: Whether this is a premium world
            price: Optional price if purchased as a premium world
        """
        # Create world with tier 1 by default
        world = World(
            name=name,
            description=description,
            settings=settings,
            owner_id=owner_id,
            genre=genre if genre else None,
            tier=1  # Default tier for new worlds
        )
        
        self.db.add(world)
        self.db.commit()
        self.db.refresh(world)
        
        return world
    
    def get_world(self, world_id: str) -> Optional[World]:
        """Get a world by ID"""
        return self.db.query(World).filter(World.id == world_id).first()
    
    def get_worlds(self, 
                  filters: Dict[str, Any] = None, 
                  page: int = 1, 
                  page_size: int = 20, 
                  sort_by: str = "name", 
                  sort_desc: bool = False) -> Tuple[List[World], int, int]:
        """
        Get worlds with flexible filtering options
        
        Args:
            filters: Dictionary of filter conditions
            page: Page number (starting from 1)
            page_size: Number of records per page
            sort_by: Field to sort by
            sort_desc: Whether to sort in descending order
            
        Returns:
            Tuple of (worlds, total_count, total_pages)
        """
        query = self.db.query(World)
        
        # Apply filters if provided
        if filters:
            if 'owner_id' in filters:
                query = query.filter(World.owner_id == filters['owner_id'])
            
            if 'name' in filters:
                query = query.filter(World.name.ilike(f"%{filters['name']}%"))
            
            if 'description' in filters:
                query = query.filter(World.description.ilike(f"%{filters['description']}%"))
                
            if 'genre' in filters:
                query = query.filter(World.genre == filters['genre'])
                
            if 'search' in filters and filters['search']:
                search_term = f"%{filters['search']}%"
                query = query.filter(
                    or_(
                        World.name.ilike(search_term),
                        World.description.ilike(search_term)
                    )
                )
        
        # Get total count before pagination
        total_count = query.count()
        total_pages = math.ceil(total_count / page_size) if total_count > 0 else 1
        
        # Apply sorting
        if hasattr(World, sort_by):
            sort_field = getattr(World, sort_by)
            query = query.order_by(sort_field.desc() if sort_desc else sort_field)
        else:
            # Default to name
            query = query.order_by(World.name.desc() if sort_desc else World.name)
        
        # Apply pagination - convert page to offset
        offset = (page - 1) * page_size if page > 0 else 0
        
        # Get paginated results
        worlds = query.offset(offset).limit(page_size).all()
        
        return worlds, total_count, total_pages
    
    def get_user_worlds(self, user_id: str, page: int = 1, page_size: int = 20) -> Tuple[List[World], int, int]:
        """Get all worlds owned by a user"""
        return self.get_worlds(
            filters={'owner_id': user_id},
            page=page,
            page_size=page_size
        )
    
    def update_world(self, world_id: str, update_data: Dict[str, Any]) -> Optional[World]:
        """Update a world"""
        world = self.get_world(world_id)
        if not world:
            return None
        
        # Update only the fields provided
        for key, value in update_data.items():
            if hasattr(world, key):
                setattr(world, key, value)
        
        self.db.commit()
        self.db.refresh(world)
        
        return world
    
    def delete_world(self, world_id: str) -> bool:
        """Delete a world"""
        world = self.get_world(world_id)
        if not world:
            return False
        
        self.db.delete(world)
        self.db.commit()
        
        return True
    
    def check_user_access(self, user_id: str, world_id: str) -> bool:
        """Check if a user has access to a world (owner or admin)"""
        world = self.get_world(world_id)
        
        if not world:
            return False
        
        # Owner always has access
        if world.owner_id == user_id:
            return True
        
        # Check if user is admin
        user = self.db.query(Player).filter(Player.id == user_id).first()
        if user and user.is_admin:
            return True
            
        return False
    
    def search_worlds(self, 
                     query: str, 
                     user_id: Optional[str] = None, 
                     page: int = 1, 
                     page_size: int = 20) -> Tuple[List[World], int, int]:
        """
        Search for worlds by name or description
        
        Args:
            query: Search term
            user_id: Filter by user ID (for owned worlds)
            page: Page number
            page_size: Results per page
        """
        filters = {'search': query}
        
        if user_id:
            filters['owner_id'] = user_id
        
        return self.get_worlds(
            filters=filters,
            page=page,
            page_size=page_size
        )
        
    def get_world_zone_limit(self, world_id: str) -> int:
        """
        Get the zone limit for a world based on its tier
        
        Args:
            world_id: ID of the world
            
        Returns:
            The maximum number of zones the world can contain
        """
        world = self.get_world(world_id)
        if not world:
            return 0
            
        return self.calculate_zone_limit(world.tier)
        
    def calculate_zone_limit(self, tier: int) -> int:
        """
        Calculate zone limit based on tier
        
        Args:
            tier: The world's tier
            
        Returns:
            The maximum number of zones the world can contain
        """
        # Base zone limit for tier 1
        BASE_ZONE_LIMIT = 10
        
        # Formula: base * tier (can be adjusted with more complex formulas as needed)
        return BASE_ZONE_LIMIT * tier
        
    def upgrade_world_tier(self, world_id: str) -> bool:
        """
        Upgrade a world's tier
        
        Args:
            world_id: ID of the world to upgrade
            
        Returns:
            True if successful, False otherwise
        """
        world = self.get_world(world_id)
        if not world:
            return False
            
        # Increment tier
        world.tier += 1
        self.db.commit()
        
        return True
        
    def can_add_zone_to_world(self, world_id: str) -> bool:
        """
        Check if a world has reached its zone limit based on tier
        
        Args:
            world_id: ID of the world
            
        Returns:
            True if more zones can be added, False otherwise
        """
        world = self.get_world(world_id)
        if not world:
            return False
            
        # Get current zone count
        from app.services.zone_service import ZoneService
        zone_service = ZoneService(self.db)
        zone_count = zone_service.count_zones_in_world(world_id)
        
        # Get the zone limit based on tier
        zone_limit = self.calculate_zone_limit(world.tier)
        
        return zone_count < zone_limit