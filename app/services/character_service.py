# app/services/character_service.py
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, func
from typing import List, Optional, Dict, Any, Tuple
import math

from app.models.character import Character
from app.models.user import User


class CharacterService:
    """Service for handling character operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_character(self, 
                        user_id: str, 
                        name: str, 
                        description: Optional[str] = None,
                        is_public: bool = False) -> Character:
        """
        Create a new character
        
        Args:
            user_id: ID of the user creating the character (owner)
            name: Name of the character
            description: Description of the character (including personality)
            is_public: Whether the character can be used by agents
        """
        character = Character(
            name=name,
            description=description,
            user_id=user_id,
            is_public=is_public
        )
        
        self.db.add(character)
        self.db.commit()
        self.db.refresh(character)
        
        return character
    
    def get_character(self, character_id: str) -> Optional[Character]:
        """Get a character by ID"""
        return self.db.query(Character).filter(Character.id == character_id).first()
    
    def get_characters(self, 
                       filters: Dict[str, Any] = None, 
                       page: int = 1, 
                       page_size: int = 20, 
                       sort_by: str = "name", 
                       sort_desc: bool = False) -> Tuple[List[Character], int, int]:
        """
        Get characters with flexible filtering options
        
        Args:
            filters: Dictionary of filter conditions
            page: Page number (starting from 1)
            page_size: Number of records per page
            sort_by: Field to sort by
            sort_desc: Whether to sort in descending order
            
        Returns:
            Tuple of (characters, total_count, total_pages)
        """
        query = self.db.query(Character)
        
        # Apply filters if provided
        if filters:
            if 'user_id' in filters:
                query = query.filter(Character.user_id == filters['user_id'])
            
            if 'name' in filters:
                query = query.filter(Character.name.ilike(f"%{filters['name']}%"))
            
            if 'description' in filters:
                query = query.filter(Character.description.ilike(f"%{filters['description']}%"))
            
            if 'is_public' in filters:
                query = query.filter(Character.is_public == filters['is_public'])
            
            if 'ids' in filters and isinstance(filters['ids'], list):
                query = query.filter(Character.id.in_(filters['ids']))
                
            if 'search' in filters and filters['search']:
                search_term = f"%{filters['search']}%"
                query = query.filter(
                    or_(
                        Character.name.ilike(search_term),
                        Character.description.ilike(search_term)
                    )
                )
        
        # Get total count before pagination
        total_count = query.count()
        total_pages = math.ceil(total_count / page_size) if total_count > 0 else 1
        
        # Apply sorting
        if hasattr(Character, sort_by):
            sort_field = getattr(Character, sort_by)
            query = query.order_by(sort_field.desc() if sort_desc else sort_field)
        else:
            # Default to name
            query = query.order_by(Character.name.desc() if sort_desc else Character.name)
        
        # Apply pagination - convert page to offset
        offset = (page - 1) * page_size if page > 0 else 0
        
        # Get paginated results
        characters = query.offset(offset).limit(page_size).all()
        
        return characters, total_count, total_pages
    
    def get_user_characters(self, user_id: str, page: int = 1, page_size: int = 20) -> Tuple[List[Character], int, int]:
        """Get all characters owned by a user"""
        return self.get_characters(
            filters={'user_id': user_id},
            page=page,
            page_size=page_size
        )
    
    def get_public_characters(self, page: int = 1, page_size: int = 20) -> Tuple[List[Character], int, int]:
        """Get all public characters available for agents"""
        return self.get_characters(
            filters={'is_public': True},
            page=page,
            page_size=page_size
        )
    
    def update_character(self, character_id: str, update_data: Dict[str, Any]) -> Optional[Character]:
        """Update a character"""
        character = self.get_character(character_id)
        if not character:
            return None
        
        # Update only the fields provided
        for key, value in update_data.items():
            if hasattr(character, key):
                setattr(character, key, value)
        
        self.db.commit()
        self.db.refresh(character)
        
        return character
    
    def delete_character(self, character_id: str) -> bool:
        """Delete a character"""
        character = self.get_character(character_id)
        if not character:
            return False
        
        self.db.delete(character)
        self.db.commit()
        
        return True
    
    def search_characters(self, 
                         query: str, 
                         include_public: bool = False, 
                         user_id: Optional[str] = None, 
                         page: int = 1, 
                         page_size: int = 20) -> Tuple[List[Character], int, int]:
        """
        Search for characters by name or description
        
        Args:
            query: Search term
            include_public: Whether to include public characters
            user_id: Filter by user ID (or None to search all)
            page: Page number
            page_size: Results per page
        """
        filters = {'search': query}
        
        if user_id:
            # Filter by user, possibly including public characters
            if include_public:
                # This requires a custom query as we need an OR condition
                search_term = f"%{query}%"
                q = self.db.query(Character).filter(
                    or_(
                        Character.name.ilike(search_term),
                        Character.description.ilike(search_term)
                    ),
                    or_(
                        Character.user_id == user_id,
                        Character.is_public == True
                    )
                )
                
                # Count before pagination
                total_count = q.count()
                total_pages = math.ceil(total_count / page_size) if total_count > 0 else 1
                
                # Apply ordering and pagination
                offset = (page - 1) * page_size if page > 0 else 0
                characters = q.order_by(Character.name).offset(offset).limit(page_size).all()
                
                return characters, total_count, total_pages
            else:
                # Just filter by user
                filters['user_id'] = user_id
        elif not include_public:
            # Neither user nor public - return empty result
            return [], 0, 1
        else:
            # Only public characters
            filters['is_public'] = True
        
        return self.get_characters(
            filters=filters,
            page=page,
            page_size=page_size
        )
    
    def count_characters(self, user_id: Optional[str] = None, include_public: bool = False) -> int:
        """
        Count the number of characters
        
        Args:
            user_id: Filter by user ID (or None to count all)
            include_public: Whether to include public characters in the count
        """
        query = self.db.query(func.count(Character.id))
        
        if user_id:
            if include_public:
                query = query.filter(
                    or_(
                        Character.user_id == user_id,
                        Character.is_public == True
                    )
                )
            else:
                query = query.filter(Character.user_id == user_id)
        elif include_public:
            query = query.filter(Character.is_public == True)
        
        return query.scalar() or 0
    
    def make_character_public(self, character_id: str) -> Optional[Character]:
        """Make a character publicly available for agents"""
        return self.update_character(character_id, {"is_public": True})
    
    def make_character_private(self, character_id: str) -> Optional[Character]:
        """Make a character private (only for owner)"""
        return self.update_character(character_id, {"is_public": False})