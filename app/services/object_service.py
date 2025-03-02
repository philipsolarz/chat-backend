# app/services/object_service.py
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any, Tuple

from app.models.object import Object
from app.models.zone import Zone
from app.models.entity import EntityType
from app.services.entity_service import EntityService


class ObjectService:
    """Service for handling object entities"""
    
    def __init__(self, db: Session):
        self.db = db
        self.entity_service = EntityService(db)
    
    def create_object(self, 
                     name: str,
                     description: Optional[str] = None,
                     zone_id: Optional[str] = None,
                     is_interactive: bool = False,
                     object_type: Optional[str] = None,
                     settings: Optional[Dict[str, Any]] = None) -> Optional[Object]:
        """
        Create a new object entity
        
        Args:
            name: Name of the object
            description: Description of the object
            zone_id: Optional zone to place the object in
            is_interactive: Whether the object can be interacted with
            object_type: Type of object (e.g., "item", "furniture", etc.)
            settings: JSON settings for object configuration
            
        Returns:
            The created object or None if the zone has reached its entity limit
        """
        # If zone_id is provided, check the zone's entity limit
        if zone_id:
            zone = self.db.query(Zone).filter(Zone.id == zone_id).first()
            if not zone:
                return None
                
            # Check entity limit
            from app.services.zone_service import ZoneService
            zone_service = ZoneService(self.db)
            if not zone_service.can_add_entity_to_zone(zone_id):
                return None
        
        # Create the object
        obj = Object(
            name=name,
            description=description,
            type=EntityType.OBJECT,
            zone_id=zone_id,
            is_interactive=is_interactive,
            object_type=object_type,
            settings=settings
        )
        
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        
        return obj
    
    def get_object(self, object_id: str) -> Optional[Object]:
        """Get an object by ID"""
        return self.db.query(Object).filter(Object.id == object_id).first()
    
    def get_objects(self, 
                   zone_id: Optional[str] = None,
                   object_type: Optional[str] = None,
                   is_interactive: Optional[bool] = None,
                   page: int = 1, 
                   page_size: int = 20,
                   sort_by: str = "name") -> Tuple[List[Object], int, int]:
        """
        Get objects with filtering options
        
        Args:
            zone_id: Optional zone ID to filter by
            object_type: Optional object type to filter by
            is_interactive: Optional interactivity filter
            page: Page number
            page_size: Results per page
            sort_by: Field to sort by
            
        Returns:
            Tuple of (objects, total_count, total_pages)
        """
        # Start with entity filters
        filters = {'type': EntityType.OBJECT}
        
        if zone_id is not None:
            filters['zone_id'] = zone_id
        
        # Get entities with basic filters
        entities, total_count, total_pages = self.entity_service.get_entities(
            filters=filters,
            page=page,
            page_size=page_size,
            sort_by=sort_by
        )
        
        # Convert entities to objects
        objects = [entity for entity in entities if isinstance(entity, Object)]
        
        # Apply object-specific filters client-side
        if object_type is not None:
            objects = [obj for obj in objects if obj.object_type == object_type]
            
        if is_interactive is not None:
            objects = [obj for obj in objects if obj.is_interactive == is_interactive]
        
        # Recalculate counts if we filtered further
        if object_type is not None or is_interactive is not None:
            total_count = len(objects)
            total_pages = (total_count + page_size - 1) // page_size
        
        return objects, total_count, total_pages
    
    def update_object(self, object_id: str, update_data: Dict[str, Any]) -> Optional[Object]:
        """Update an object"""
        obj = self.get_object(object_id)
        if not obj:
            return None
        
        # Update only the fields provided
        for key, value in update_data.items():
            if hasattr(obj, key):
                setattr(obj, key, value)
        
        self.db.commit()
        self.db.refresh(obj)
        
        return obj
    
    def delete_object(self, object_id: str) -> bool:
        """Delete an object"""
        return self.entity_service.delete_entity(object_id)
    
    def move_object_to_zone(self, object_id: str, zone_id: str) -> bool:
        """Move an object to a different zone"""
        return self.entity_service.move_entity_to_zone(object_id, zone_id)