# app/services/entity_service.py
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from typing import List, Optional, Dict, Any, Tuple
import math

from app.models.entity import Entity, EntityType
from app.models.zone import Zone


class EntityService:
    """Service for handling entity operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_entity(self, entity_id: str) -> Optional[Entity]:
        """Get any entity by ID"""
        return self.db.query(Entity).filter(Entity.id == entity_id).first()
    
    def get_entities(self, 
                    filters: Dict[str, Any] = None, 
                    page: int = 1, 
                    page_size: int = 20, 
                    sort_by: str = "name", 
                    sort_desc: bool = False) -> Tuple[List[Entity], int, int]:
        """
        Get entities with flexible filtering options
        
        Args:
            filters: Dictionary of filter conditions
            page: Page number (starting from 1)
            page_size: Number of records per page
            sort_by: Field to sort by
            sort_desc: Whether to sort in descending order
            
        Returns:
            Tuple of (entities, total_count, total_pages)
        """
        query = self.db.query(Entity)
        
        # Apply filters if provided
        if filters:
            if 'zone_id' in filters:
                query = query.filter(Entity.zone_id == filters['zone_id'])
            
            if 'name' in filters:
                query = query.filter(Entity.name.ilike(f"%{filters['name']}%"))
            
            if 'description' in filters:
                query = query.filter(Entity.description.ilike(f"%{filters['description']}%"))
            
            if 'type' in filters:
                query = query.filter(Entity.type == filters['type'])
                
            if 'search' in filters and filters['search']:
                search_term = f"%{filters['search']}%"
                query = query.filter(
                    or_(
                        Entity.name.ilike(search_term),
                        Entity.description.ilike(search_term)
                    )
                )
        
        # Get total count before pagination
        total_count = query.count()
        total_pages = math.ceil(total_count / page_size) if total_count > 0 else 1
        
        # Apply sorting
        if hasattr(Entity, sort_by):
            sort_field = getattr(Entity, sort_by)
            query = query.order_by(sort_field.desc() if sort_desc else sort_field)
        else:
            # Default to name
            query = query.order_by(Entity.name.desc() if sort_desc else Entity.name)
        
        # Apply pagination - convert page to offset
        offset = (page - 1) * page_size if page > 0 else 0
        
        # Get paginated results
        entities = query.offset(offset).limit(page_size).all()
        
        return entities, total_count, total_pages
    
    def get_entities_in_zone(self, 
                           zone_id: str, 
                           entity_type: Optional[EntityType] = None,
                           page: int = 1, 
                           page_size: int = 20) -> Tuple[List[Entity], int, int]:
        """
        Get entities in a specific zone with optional type filtering
        
        Args:
            zone_id: ID of the zone to get entities from
            entity_type: Optional filter for entity type
            page: Page number
            page_size: Results per page
            
        Returns:
            Tuple of (entities, total_count, total_pages)
        """
        filters = {'zone_id': zone_id}
        
        if entity_type is not None:
            filters['type'] = entity_type
            
        return self.get_entities(
            filters=filters,
            page=page,
            page_size=page_size
        )
    
    def search_entities(self, 
                       query: str,
                       zone_id: Optional[str] = None,
                       entity_type: Optional[EntityType] = None,
                       page: int = 1, 
                       page_size: int = 20) -> Tuple[List[Entity], int, int]:
        """
        Search for entities by name or description
        
        Args:
            query: Search term
            zone_id: Optional zone ID to search within
            entity_type: Optional filter for entity type
            page: Page number
            page_size: Results per page
            
        Returns:
            Tuple of (entities, total_count, total_pages)
        """
        filters = {'search': query}
        
        if zone_id is not None:
            filters['zone_id'] = zone_id
            
        if entity_type is not None:
            filters['type'] = entity_type
            
        return self.get_entities(
            filters=filters,
            page=page,
            page_size=page_size
        )
    
    def create_entity(self, 
                     name: str,
                     description: Optional[str] = None,
                     entity_type: EntityType = None,
                     zone_id: Optional[str] = None,
                     world_id: Optional[str] = None,
                     properties: Optional[Dict[str, Any]] = None) -> Optional[Entity]:
        """
        Create a new entity
        
        Args:
            name: The name of the entity
            description: Optional description
            entity_type: The type of entity (character, object, etc.)
            zone_id: Optional zone ID to place the entity in
            world_id: Optional world ID (should be set if zone_id is set)
            properties: Optional JSON properties
            
        Returns:
            The created entity or None if the zone has reached its limit
        """
        # If zone_id is provided, check if the zone has reached its entity limit
        if zone_id:
            # Use ZoneService to check capacity based on zone tier
            from app.services.zone_service import ZoneService
            zone_service = ZoneService(self.db)
            if not zone_service.can_add_entity_to_zone(zone_id):
                return None
                
        # Create the entity with tier 1 by default
        entity = Entity(
            name=name,
            description=description,
            type=entity_type,
            zone_id=zone_id,
            world_id=world_id,
            properties=properties,
            tier=1  # Default tier for new entities
        )
        
        self.db.add(entity)
        self.db.commit()
        self.db.refresh(entity)
        
        return entity
    
    def delete_entity(self, entity_id: str) -> bool:
        """Delete any entity by ID"""
        entity = self.get_entity(entity_id)
        if not entity:
            return False
        
        self.db.delete(entity)
        self.db.commit()
        
        return True
    
    def move_entity_to_zone(self, entity_id: str, zone_id: str) -> bool:
        """
        Move an entity to a different zone
        
        Args:
            entity_id: ID of the entity to move
            zone_id: ID of the destination zone
            
        Returns:
            True if successful, False if zone has reached its tier-based entity limit
        """
        entity = self.get_entity(entity_id)
        zone = self.db.query(Zone).filter(Zone.id == zone_id).first()
        
        if not entity or not zone:
            return False
        
        # If moving to the same zone, just return success
        if entity.zone_id == zone_id:
            return True
        
        # Check if zone has reached its entity limit based on tier
        from app.services.zone_service import ZoneService
        zone_service = ZoneService(self.db)
        if not zone_service.can_add_entity_to_zone(zone_id):
            return False
        
        # Move the entity
        entity.zone_id = zone_id
        self.db.commit()
        
        return True
        
    def upgrade_entity_tier(self, entity_id: str) -> bool:
        """
        Upgrade an entity's tier
        
        Args:
            entity_id: ID of the entity to upgrade
            
        Returns:
            True if successful, False otherwise
        """
        entity = self.get_entity(entity_id)
        if not entity:
            return False
            
        # Increment tier
        entity.tier += 1
        self.db.commit()
        
        return True