# app/services/character_service.py
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from typing import List, Optional, Dict, Any, Tuple
import math

from app.models.character import Character, CharacterType
from app.models.entity import Entity
from app.models.enums import EntityType
from app.models.player import Player
from app.models.zone import Zone  # needed for filtering by world

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
                        zone_id: Optional[str] = None,
                        world_id: Optional[str] = None
                        ) -> Optional[Character]:
        """
        Create a new character.
        
        Args:
            user_id: ID of the user creating the character (owner)
            name: Name of the character
            description: Description of the character (including personality)
            zone_id: Zone ID to place the character in
            world_id: ID of the world (for reference, not directly used here)
            
        Returns:
            Created character or None if entity creation fails (e.g., zone reached its entity limit)
        """
        # First, create an entity (which is the base for our character)
        entity = self.entity_service.create_entity(
            name=name,
            description=description,
            entity_type=EntityType.CHARACTER,
            zone_id=zone_id,
        )
        
        if not entity:
            return None  # Failed to create entity
        
        # Create a character using the same id as the created entity.
        character = Character(
            id=entity.id,
            character_type=CharacterType.PLAYER,  # default to player-controlled
            player_id=user_id
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
        Get characters with flexible filtering options.
        
        Args:
            filters: Dictionary of filter conditions
            page: Page number (starting from 1)
            page_size: Number of records per page
            sort_by: Field to sort by
            sort_desc: Whether to sort in descending order
            
        Returns:
            Tuple of (list of characters, total count, total pages)
        """
        query = self.db.query(Character)
        
        if filters:
            if 'player_id' in filters:
                query = query.filter(Character.player_id == filters['player_id'])
            
            if 'name' in filters:
                query = query.filter(Character.name.ilike(f"%{filters['name']}%"))
            
            if 'description' in filters:
                query = query.filter(Character.description.ilike(f"%{filters['description']}%"))
                
            if 'world_id' in filters:
                # Join to Zone to filter by world.
                query = query.join(Character.zone).filter(Zone.world_id == filters['world_id'])
                
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
            # If filtering for public characters, ensure you have an "is_public" flag defined on Character or use another mechanism.
            if 'is_public' in filters:
                query = query.filter(Character.is_public == filters['is_public'])
        
        total_count = query.count()
        total_pages = math.ceil(total_count / page_size) if total_count > 0 else 1
        
        # Apply sorting based on a valid field of Character.
        if hasattr(Character, sort_by):
            sort_field = getattr(Character, sort_by)
            query = query.order_by(sort_field.desc() if sort_desc else sort_field)
        else:
            query = query.order_by(Character.name.desc() if sort_desc else Character.name)
        
        offset = (page - 1) * page_size if page > 0 else 0
        
        characters = query.offset(offset).limit(page_size).all()
        
        return characters, total_count, total_pages
    
    def get_user_characters(self, user_id: str, page: int = 1, page_size: int = 20) -> Tuple[List[Character], int, int]:
        """Get all characters owned by a specific user"""
        return self.get_characters(
            filters={'player_id': user_id},
            page=page,
            page_size=page_size
        )
    
    def get_public_characters(self, page: int = 1, page_size: int = 20) -> Tuple[List[Character], int, int]:
        """Get all public characters available for agents"""
        # Ensure that your Character model or entity service provides an 'is_public' flag if needed.
        return self.get_characters(
            filters={'is_public': True},
            page=page,
            page_size=page_size
        )
    
    def update_character(self, character_id: str, update_data: Dict[str, Any]) -> Optional[Character]:
        """
        Update a character and its underlying entity if needed.
        
        Args:
            character_id: ID of the character to update.
            update_data: Dictionary of fields to update.
            
        Returns:
            Updated character or None if not found.
        """
        character = self.get_character(character_id)
        if not character:
            return None
        
        # Update underlying entity fields (name, description, etc.)
        if character.id and ('name' in update_data or 'description' in update_data):
            self.entity_service.update_entity_fields(character.id, update_data)
        
        # Update character-specific fields.
        for key, value in update_data.items():
            if hasattr(character, key):
                setattr(character, key, value)
        
        self.db.commit()
        self.db.refresh(character)
        
        return character
    
    def delete_character(self, character_id: str) -> bool:
        """
        Delete a character and its associated entity.
        
        Args:
            character_id: ID of the character to delete.
            
        Returns:
            True if deletion was successful, False otherwise.
        """
        character = self.get_character(character_id)
        if not character:
            return False
        
        # Since Character.id is the same as the underlying entity id, use it.
        entity_id = character.id
        
        self.db.delete(character)
        self.db.commit()
        
        if entity_id:
            self.entity_service.delete_entity(entity_id)
        
        return True
    
    def search_characters(self, 
                          query_str: str,
                          user_id: Optional[str] = None, 
                          page: int = 1, 
                          page_size: int = 20,
                          filters: Dict[str, Any] = None) -> Tuple[List[Character], int, int]:
        """
        Search for characters by name or description.
        
        Args:
            query_str: Search term.
            user_id: Optionally filter by user ID.
            page: Page number.
            page_size: Results per page.
            filters: Additional filters.
            
        Returns:
            Tuple of (list of characters, total count, total pages).
        """
        if filters is None:
            filters = {}
            
        filters['search'] = query_str

        return self.get_characters(
            filters=filters,
            page=page,
            page_size=page_size
        )
    
    def count_characters(self, user_id: Optional[str] = None) -> int:
        """
        Count the number of characters.
        
        Args:
            user_id: Optionally filter by user ID.
            
        Returns:
            Count of characters matching criteria.
        """
        query = self.db.query(func.count(Character.id))
        if user_id:
            query = query.filter(Character.player_id == user_id)
        return query.scalar() or 0

    def move_character_to_zone(self, character_id: str, zone_id: str) -> bool:
        """
        Move a character to a different zone.
        
        Args:
            character_id: ID of the character to move.
            zone_id: ID of the destination zone.
            
        Returns:
            True if successful, False otherwise.
        """
        character = self.get_character(character_id)
        if not character:
            return False
            
        # Use EntityService to handle the move using the underlying entity id.
        return self.entity_service.move_entity_with_related(
            entity_id=character.id,
            related_obj=character,
            zone_id=zone_id
        )
        
    def upgrade_character_tier(self, character_id: str) -> bool:
        """
        Upgrade a character's tier.
        
        Args:
            character_id: ID of the character to upgrade.
            
        Returns:
            True if successful, False otherwise.
        """
        character = self.get_character(character_id)
        if not character:
            return False
            
        # Assuming tier is defined on the inherited entity columns.
        character.tier += 1
        
        if character.id:
            self.entity_service.upgrade_entity_tier(character.id)
            
        self.db.commit()
        return True
        
    def check_character_owner(self, character_id: str, user_id: str) -> bool:
        """
        Check if a user owns a character.
        
        Args:
            character_id: ID of the character.
            user_id: ID of the user.
            
        Returns:
            True if the user is the owner, False otherwise.
        """
        character = self.get_character(character_id)
        if not character:
            return False
            
        return character.player_id == user_id
