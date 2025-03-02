# app/services/object_service.py
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy import or_, func
import math

from app.models.object import Object, ObjectType
from app.models.entity import Entity, EntityType
from app.models.zone import Zone


class ObjectService:
    """Service for handling object entities"""
    
    def __init__(self, db: Session):
        self.db = db
        self.entity_service = None  # Initialized lazily to avoid circular imports
    
    def _get_entity_service(self):
        """Lazy initialization of EntityService to avoid circular imports"""
        if self.entity_service is None:
            from app.services.entity_service import EntityService
            self.entity_service = EntityService(self.db)
        return self.entity_service
    
    def create_object(self, 
                     name: str,
                     description: Optional[str] = None,
                     zone_id: Optional[str] = None,
                     world_id: Optional[str] = None,
                     is_interactive: bool = False,
                     object_type: Optional[str] = None,
                     settings: Optional[Dict[str, Any]] = None) -> Optional[Object]:
        """
        Create a new object entity
        
        Args:
            name: Name of the object
            description: Description of the object
            zone_id: Optional zone to place the object in
            world_id: Optional world ID for the object
            is_interactive: Whether the object can be interacted with
            object_type: Type of object (e.g., "item", "furniture", etc.)
            settings: JSON settings for object configuration
            
        Returns:
            The created object or None if the zone has reached its entity limit
        """
        # First, create an entity
        entity_service = self._get_entity_service()
        
        entity = entity_service.create_entity(
            name=name,
            description=description,
            entity_type=EntityType.OBJECT,
            zone_id=zone_id,
            world_id=world_id
        )
        
        if not entity:
            return None  # Failed to create entity (e.g., zone reached limit)
        
        # Create object with default tier 1
        obj = Object(
            name=name,
            description=description,
            type=ObjectType.GENERIC if not object_type else object_type,
            is_interactive=is_interactive,
            zone_id=zone_id,
            world_id=world_id,
            entity_id=entity.id,
            settings=settings,
            tier=1  # Default tier for new objects
        )
        
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        
        return obj
    
    def get_object(self, object_id: str) -> Optional[Object]:
        """Get an object by ID"""
        return self.db.query(Object).filter(Object.id == object_id).first()
    
    def get_objects(self, 
                   filters: Dict[str, Any] = None, 
                   page: int = 1, 
                   page_size: int = 20, 
                   sort_by: str = "name", 
                   sort_desc: bool = False) -> Tuple[List[Object], int, int]:
        """
        Get objects with flexible filtering options
        
        Args:
            filters: Dictionary of filter conditions
            page: Page number (starting from 1)
            page_size: Number of records per page
            sort_by: Field to sort by
            sort_desc: Whether to sort in descending order
            
        Returns:
            Tuple of (objects, total_count, total_pages)
        """
        query = self.db.query(Object)
        
        # Apply filters if provided
        if filters:
            if 'zone_id' in filters:
                query = query.filter(Object.zone_id == filters['zone_id'])
                
            if 'world_id' in filters:
                query = query.filter(Object.world_id == filters['world_id'])
            
            if 'name' in filters:
                query = query.filter(Object.name.ilike(f"%{filters['name']}%"))
            
            if 'description' in filters:
                query = query.filter(Object.description.ilike(f"%{filters['description']}%"))
            
            if 'is_interactive' in filters:
                query = query.filter(Object.is_interactive == filters['is_interactive'])
                
            if 'object_type' in filters:
                query = query.filter(Object.type == filters['object_type'])
                
            if 'search' in filters and filters['search']:
                search_term = f"%{filters['search']}%"
                query = query.filter(
                    or_(
                        Object.name.ilike(search_term),
                        Object.description.ilike(search_term)
                    )
                )
        
        # Get total count before pagination
        total_count = query.count()
        total_pages = math.ceil(total_count / page_size) if total_count > 0 else 1
        
        # Apply sorting
        if hasattr(Object, sort_by):
            sort_field = getattr(Object, sort_by)
            query = query.order_by(sort_field.desc() if sort_desc else sort_field)
        else:
            # Default to name
            query = query.order_by(Object.name.desc() if sort_desc else Object.name)
        
        # Apply pagination - convert page to offset
        offset = (page - 1) * page_size if page > 0 else 0
        
        # Get paginated results
        objects = query.offset(offset).limit(page_size).all()
        
        return objects, total_count, total_pages
    
    def update_object(self, object_id: str, update_data: Dict[str, Any]) -> Optional[Object]:
        """Update an object"""
        obj = self.get_object(object_id)
        if not obj:
            return None
        
        # If we're updating basic properties, update the entity as well
        entity = None
        entity_updates = {}
        if obj.entity_id:
            entity = self.db.query(Entity).filter(Entity.id == obj.entity_id).first()
            
            if entity:
                # Collect entity updates
                if 'name' in update_data:
                    entity_updates['name'] = update_data['name']
                if 'description' in update_data:
                    entity_updates['description'] = update_data['description']
                
                # Apply entity updates
                for key, value in entity_updates.items():
                    setattr(entity, key, value)
        
        # Update object fields
        for key, value in update_data.items():
            if hasattr(obj, key):
                setattr(obj, key, value)
        
        self.db.commit()
        
        if obj:
            self.db.refresh(obj)
        if entity:
            self.db.refresh(entity)
        
        return obj
    
    def delete_object(self, object_id: str) -> bool:
        """Delete an object and its associated entity"""
        obj = self.get_object(object_id)
        if not obj:
            return False
        
        # Get the associated entity
        entity_id = obj.entity_id
        
        # Delete the object
        self.db.delete(obj)
        self.db.commit()
        
        # Delete the associated entity if it exists
        if entity_id:
            entity = self.db.query(Entity).filter(Entity.id == entity_id).first()
            if entity:
                self.db.delete(entity)
                self.db.commit()
        
        return True
    
    def search_objects(self, 
                      query: str, 
                      zone_id: Optional[str] = None,
                      world_id: Optional[str] = None,
                      is_interactive: Optional[bool] = None,
                      object_type: Optional[str] = None,
                      page: int = 1, 
                      page_size: int = 20) -> Tuple[List[Object], int, int]:
        """
        Search for objects by name or description
        
        Args:
            query: Search term
            zone_id: Optional zone ID to search within
            world_id: Optional world ID to search within
            is_interactive: Optional filter for interactive objects
            object_type: Optional filter for object type
            page: Page number
            page_size: Results per page
        """
        # Start with basic search filter
        filters = {'search': query}
        
        # Add optional filters
        if zone_id:
            filters['zone_id'] = zone_id
            
        if world_id:
            filters['world_id'] = world_id
            
        if is_interactive is not None:
            filters['is_interactive'] = is_interactive
            
        if object_type:
            filters['object_type'] = object_type
        
        return self.get_objects(
            filters=filters,
            page=page,
            page_size=page_size
        )
    
    def move_object_to_zone(self, object_id: str, zone_id: str) -> bool:
        """
        Move an object to a different zone
        
        Args:
            object_id: ID of the object to move
            zone_id: ID of the destination zone
            
        Returns:
            True if successful, False if the zone has reached its entity limit
        """
        obj = self.get_object(object_id)
        if not obj or not obj.entity_id:
            return False
            
        # Use EntityService to move the underlying entity
        entity_service = self._get_entity_service()
        
        if entity_service.move_entity_to_zone(obj.entity_id, zone_id):
            # Update the object's zone_id to match
            obj.zone_id = zone_id
            self.db.commit()
            return True
        
        return False
        
    def upgrade_object_tier(self, object_id: str) -> bool:
        """
        Upgrade an object's tier
        
        Args:
            object_id: ID of the object to upgrade
            
        Returns:
            True if successful, False otherwise
        """
        obj = self.get_object(object_id)
        if not obj:
            return False
            
        # Increment tier
        obj.tier += 1
        self.db.commit()
        
        # Also upgrade the entity if present
        if obj.entity_id:
            entity_service = self._get_entity_service()
            entity_service.upgrade_entity_tier(obj.entity_id)
        
        return True