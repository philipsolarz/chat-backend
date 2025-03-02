# app/services/character_service.py
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, func
from typing import List, Optional, Dict, Any, Tuple
import math

from app.models.character import Character, CharacterType
from app.models.entity import Entity, EntityType
from app.models.player import Player


class CharacterService:
    """Service for handling character operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_character(self, 
                        user_id: str, 
                        name: str, 
                        description: Optional[str] = None,
                        world_id: Optional[str] = None,
                        zone_id: Optional[str] = None,
                        is_public: bool = False,
                        template: Optional[str] = None) -> Optional[Character]:
        """
        Create a new character
        
        Args:
            user_id: ID of the user creating the character (owner)
            name: Name of the character
            description: Description of the character (including personality)
            world_id: Optional world ID
            zone_id: Optional zone ID to place the character in
            is_public: Whether the character can be used by agents
            template: Optional character template
            
        Returns:
            Created character or None if zone has reached its entity limit
        """
        # First, create an entity
        from app.services.entity_service import EntityService
        entity_service = EntityService(self.db)
        
        entity = entity_service.create_entity(
            name=name,
            description=description,
            entity_type=EntityType.CHARACTER,
            zone_id=zone_id,
            world_id=world_id
        )
        
        if not entity:
            return None  # Failed to create entity (e.g., zone reached limit)
        
        # Create character linked to the entity
        character = Character(
            name=name,
            description=description,
            type=CharacterType.PLAYER,  # Default to player-controlled
            entity_id=entity.id,
            player_id=user_id,
            world_id=world_id,
            zone_id=zone_id,
            template=template,
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
            if 'player_id' in filters:
                query = query.filter(Character.player_id == filters['player_id'])
            
            if 'name' in filters:
                query = query.filter(Character.name.ilike(f"%{filters['name']}%"))
            
            if 'description' in filters:
                query = query.filter(Character.description.ilike(f"%{filters['description']}%"))
            
            if 'is_public' in filters:
                query = query.filter(Character.is_public == filters['is_public'])
            
            if 'world_id' in filters:
                query = query.filter(Character.world_id == filters['world_id'])
                
            if 'zone_id' in filters:
                query = query.filter(Character.zone_id == filters['zone_id'])
            
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
            filters={'player_id': user_id},
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
        
        # If we're updating basic properties, update the entity as well
        entity = None
        entity_updates = {}
        if character.entity_id:
            entity = self.db.query(Entity).filter(Entity.id == character.entity_id).first()
            
            if entity:
                # Collect entity updates
                if 'name' in update_data:
                    entity_updates['name'] = update_data['name']
                if 'description' in update_data:
                    entity_updates['description'] = update_data['description']
                
                # Apply entity updates
                for key, value in entity_updates.items():
                    setattr(entity, key, value)
        
        # Update character fields
        for key, value in update_data.items():
            if hasattr(character, key):
                setattr(character, key, value)
        
        self.db.commit()
        
        if character:
            self.db.refresh(character)
        if entity:
            self.db.refresh(entity)
        
        return character
    
    def delete_character(self, character_id: str) -> bool:
        """Delete a character and its associated entity"""
        character = self.get_character(character_id)
        if not character:
            return False
        
        # Get the associated entity
        entity_id = character.entity_id
        
        # Delete the character
        self.db.delete(character)
        self.db.commit()
        
        # Delete the associated entity if it exists
        if entity_id:
            entity = self.db.query(Entity).filter(Entity.id == entity_id).first()
            if entity:
                self.db.delete(entity)
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
                        Character.player_id == user_id,
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
                filters['player_id'] = user_id
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
                        Character.player_id == user_id,
                        Character.is_public == True
                    )
                )
            else:
                query = query.filter(Character.player_id == user_id)
        elif include_public:
            query = query.filter(Character.is_public == True)
        
        return query.scalar() or 0
    
    def make_character_public(self, character_id: str) -> Optional[Character]:
        """Make a character publicly available for agents"""
        return self.update_character(character_id, {"is_public": True})
    
    def make_character_private(self, character_id: str) -> Optional[Character]:
        """Make a character private (only for owner)"""
        return self.update_character(character_id, {"is_public": False})
        
    def move_character_to_zone(self, character_id: str, zone_id: str) -> bool:
        """
        Move a character to a different zone
        
        Args:
            character_id: ID of the character to move
            zone_id: ID of the destination zone
            
        Returns:
            True if successful, False otherwise
        """
        character = self.get_character(character_id)
        if not character or not character.entity_id:
            return False
            
        # Use EntityService to move the underlying entity
        from app.services.entity_service import EntityService
        entity_service = EntityService(self.db)
        
        if entity_service.move_entity_to_zone(character.entity_id, zone_id):
            # Update the character's zone_id to match
            character.zone_id = zone_id
            self.db.commit()
            return True
        
        return False