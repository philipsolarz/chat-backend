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
        from app.services.entity_service import EntityService
        self.entity_service = EntityService(db)
    
    def create_character(self, 
                        user_id: str, 
                        name: str, 
                        description: Optional[str] = None,
                        world_id: Optional[str] = None,
                        zone_id: Optional[str] = None,
                        ) -> Optional[Character]:
        """
        Create a new character
        
        Args:
            user_id: ID of the user creating the character (owner)
            name: Name of the character
            description: Description of the character (including personality)
            world_id: Optional world ID
            zone_id: Optional zone ID to place the character in
            
        Returns:
            Created character or None if zone has reached its entity limit
        """
        # First, create an entity
        entity = self.entity_service.create_entity(
            name=name,
            description=description,
            entity_type=EntityType.CHARACTER,
            zone_id=zone_id,
            # world_id=world_id
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
            # world_id=world_id,
            # zone_id=zone_id
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

            if 'world_id' in filters:
                query = query.filter(Character.world.id == filters['world_id'])
                
            if 'zone_id' in filters:
                query = query.filter(Character.zone.id == filters['zone_id'])
            
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
        """
        Update a character and its underlying entity if needed
        
        Args:
            character_id: ID of the character to update
            update_data: Dictionary of fields to update
            
        Returns:
            Updated character or None if not found
        """
        character = self.get_character(character_id)
        if not character:
            return None
        
        # If we're updating basic properties, update the entity as well
        if character.entity_id and ('name' in update_data or 'description' in update_data):
            self.entity_service.update_entity_fields(character.entity_id, update_data)
        
        # Update character fields
        for key, value in update_data.items():
            if hasattr(character, key):
                setattr(character, key, value)
        
        self.db.commit()
        self.db.refresh(character)
        
        return character
    
    def delete_character(self, character_id: str) -> bool:
        """
        Delete a character and its associated entity
        
        Args:
            character_id: ID of the character to delete
            
        Returns:
            True if successful, False if not found
        """
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
            self.entity_service.delete_entity(entity_id)
        
        return True
    
    def search_characters(self, 
                         query: str,
                         user_id: Optional[str] = None, 
                         page: int = 1, 
                         page_size: int = 20,
                         filters: Dict[str, Any] = None) -> Tuple[List[Character], int, int]:
        """
        Search for characters by name or description
        
        Args:
            query: Search term
            user_id: Filter by user ID (or None to search all)
            page: Page number
            page_size: Results per page
            filters: Additional filters to apply
            
        Returns:
            Tuple of (characters, total_count, total_pages)
        """
        if filters is None:
            filters = {}
            
        filters['search'] = query

        return self.get_characters(
            filters=filters,
            page=page,
            page_size=page_size
        )
    
    def count_characters(self, user_id: Optional[str] = None) -> int:
        """
        Count the number of characters
        
        Args:
            user_id: Filter by user ID (or None to count all)
            
        Returns:
            Count of characters matching criteria
        """
        query = self.db.query(func.count(Character.id))

        return query.scalar() or 0

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
            
        # Use EntityService to handle the move
        return self.entity_service.move_entity_with_related(
            entity_id=character.entity_id,
            related_obj=character,
            zone_id=zone_id
        )
        
    def upgrade_character_tier(self, character_id: str) -> bool:
        """
        Upgrade a character's tier
        
        Args:
            character_id: ID of the character to upgrade
            
        Returns:
            True if successful, False otherwise
        """
        character = self.get_character(character_id)
        if not character:
            return False
            
        # Increment character tier
        character.tier += 1
        
        # Also upgrade the entity if present
        if character.entity_id:
            self.entity_service.upgrade_entity_tier(character.entity_id)
            
        self.db.commit()
        return True
        
    def check_character_owner(self, character_id: str, user_id: str) -> bool:
        """
        Check if a user owns a character
        
        Args:
            character_id: ID of the character to check
            user_id: ID of the user to check
            
        Returns:
            True if user owns the character, False otherwise
        """
        character = self.get_character(character_id)
        if not character:
            return False
            
        return character.player_id == user_id