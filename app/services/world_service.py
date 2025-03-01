# app/services/world_service.py
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, func
from typing import List, Optional, Dict, Any, Tuple
import math

from app.models.world import World, world_members
from app.models.user import User


class WorldService:
    """Service for handling world operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_world(self, 
                    owner_id: str, 
                    name: str, 
                    description: Optional[str] = None,
                    genre: Optional[str] = None,
                    settings: Optional[str] = None,
                    default_prompt: Optional[str] = None,
                    is_starter: bool = False,
                    is_public: bool = False,
                    is_premium: bool = False,
                    price: Optional[float] = None) -> World:
        """
        Create a new world
        
        Args:
            owner_id: ID of the user creating the world (owner)
            name: Name of the world
            description: Description of the world
            genre: Type of world (fantasy, sci-fi, etc)
            settings: World settings and configuration
            default_prompt: Default prompt for AI agents in this world
            is_starter: Whether this is a featured/starter world
            is_public: Whether this world is public
            is_premium: Whether this is a premium world
            price: Price in USD (for premium worlds)
        """
        world = World(
            name=name,
            description=description,
            genre=genre,
            settings=settings,
            default_prompt=default_prompt,
            is_starter=is_starter,
            is_public=is_public,
            is_premium=is_premium,
            price=price,
            owner_id=owner_id
        )
        
        # Add the owner as a member automatically
        if owner_id:
            owner = self.db.query(User).filter(User.id == owner_id).first()
            if owner:
                world.members.append(owner)
        
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
            
            if 'is_starter' in filters:
                query = query.filter(World.is_starter == filters['is_starter'])
            
            if 'is_public' in filters:
                query = query.filter(World.is_public == filters['is_public'])
            
            if 'is_premium' in filters:
                query = query.filter(World.is_premium == filters['is_premium'])
            
            if 'members' in filters and filters['members']:
                user_id = filters['members']
                query = query.join(world_members).filter(world_members.c.user_id == user_id)
                
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
        """Get all worlds a user can access (owned + joined + starter worlds)"""
        # Custom query to get all worlds a user can access
        query = self.db.query(World).filter(
            or_(
                World.owner_id == user_id,  # Worlds owned by the user
                World.is_starter == True,    # Starter worlds
                World.id.in_(                # Worlds the user is a member of
                    self.db.query(world_members.c.world_id).filter(
                        world_members.c.user_id == user_id
                    )
                )
            )
        )
        
        # Get total count before pagination
        total_count = query.count()
        total_pages = math.ceil(total_count / page_size) if total_count > 0 else 1
        
        # Apply pagination
        offset = (page - 1) * page_size if page > 0 else 0
        worlds = query.order_by(World.name).offset(offset).limit(page_size).all()
        
        return worlds, total_count, total_pages
    
    def get_starter_worlds(self, page: int = 1, page_size: int = 20) -> Tuple[List[World], int, int]:
        """Get all starter worlds available to all users"""
        return self.get_worlds(
            filters={'is_starter': True},
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
    
    def add_member(self, world_id: str, user_id: str) -> bool:
        """Add a user as a member of a world"""
        world = self.get_world(world_id)
        user = self.db.query(User).filter(User.id == user_id).first()
        
        if not world or not user:
            return False
        
        # Check if already a member
        is_member = self.db.query(world_members).filter(
            world_members.c.world_id == world_id,
            world_members.c.user_id == user_id
        ).first() is not None
        
        if is_member:
            return True  # Already a member
        
        # Add as member
        world.members.append(user)
        self.db.commit()
        
        return True
    
    def remove_member(self, world_id: str, user_id: str) -> bool:
        """Remove a user as a member of a world"""
        world = self.get_world(world_id)
        user = self.db.query(User).filter(User.id == user_id).first()
        
        if not world or not user:
            return False
        
        # Check if user is the owner
        if world.owner_id == user_id:
            return False  # Can't remove the owner
        
        # Remove from members
        world.members.remove(user)
        self.db.commit()
        
        return True
    
    def check_user_access(self, user_id: str, world_id: str) -> bool:
        """Check if a user has access to a world"""
        world = self.get_world(world_id)
        
        if not world:
            return False
        
        # Starter worlds are accessible to everyone
        if world.is_starter:
            return True
        
        # Owner always has access
        if world.owner_id == user_id:
            return True
        
        # Check if user is a member
        is_member = self.db.query(world_members).filter(
            world_members.c.world_id == world_id,
            world_members.c.user_id == user_id
        ).first() is not None
        
        return is_member
    
    def search_worlds(self, 
                     query: str, 
                     include_public: bool = True,
                     include_starters: bool = True,
                     user_id: Optional[str] = None, 
                     page: int = 1, 
                     page_size: int = 20) -> Tuple[List[World], int, int]:
        """
        Search for worlds by name or description
        
        Args:
            query: Search term
            include_public: Whether to include public worlds
            include_starters: Whether to include starter worlds
            user_id: Filter by user ID (for owned/joined worlds)
            page: Page number
            page_size: Results per page
        """
        filters = {'search': query}
        
        # Build a custom query with OR conditions
        search_term = f"%{query}%"
        base_query = self.db.query(World).filter(
            or_(
                World.name.ilike(search_term),
                World.description.ilike(search_term)
            )
        )
        
        # Add additional filters
        if user_id:
            if include_public and include_starters:
                # User-owned/joined + public + starters
                base_query = base_query.filter(
                    or_(
                        World.owner_id == user_id,
                        World.is_public == True,
                        World.is_starter == True,
                        World.id.in_(
                            self.db.query(world_members.c.world_id).filter(
                                world_members.c.user_id == user_id
                            )
                        )
                    )
                )
            elif include_public:
                # User-owned/joined + public
                base_query = base_query.filter(
                    or_(
                        World.owner_id == user_id,
                        World.is_public == True,
                        World.id.in_(
                            self.db.query(world_members.c.world_id).filter(
                                world_members.c.user_id == user_id
                            )
                        )
                    )
                )
            elif include_starters:
                # User-owned/joined + starters
                base_query = base_query.filter(
                    or_(
                        World.owner_id == user_id,
                        World.is_starter == True,
                        World.id.in_(
                            self.db.query(world_members.c.world_id).filter(
                                world_members.c.user_id == user_id
                            )
                        )
                    )
                )
            else:
                # Only user-owned/joined
                base_query = base_query.filter(
                    or_(
                        World.owner_id == user_id,
                        World.id.in_(
                            self.db.query(world_members.c.world_id).filter(
                                world_members.c.user_id == user_id
                            )
                        )
                    )
                )
        else:
            # No user specified, filter by public/starter status
            if include_public and include_starters:
                base_query = base_query.filter(
                    or_(
                        World.is_public == True,
                        World.is_starter == True
                    )
                )
            elif include_public:
                base_query = base_query.filter(World.is_public == True)
            elif include_starters:
                base_query = base_query.filter(World.is_starter == True)
            else:
                # No filters, should return empty result
                return [], 0, 1
        
        # Get count for pagination
        total_count = base_query.count()
        total_pages = math.ceil(total_count / page_size) if total_count > 0 else 1
        
        # Apply pagination
        offset = (page - 1) * page_size if page > 0 else 0
        worlds = base_query.order_by(World.name).offset(offset).limit(page_size).all()
        
        return worlds, total_count, total_pages