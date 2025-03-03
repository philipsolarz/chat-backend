# app/services/object_service.py
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy import or_
import math

from app.models.object import Object, ObjectType
from app.models.zone import Zone

class ObjectService:
    """Service for handling object entities"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_object(self, 
                      name: str,
                      description: Optional[str] = None,
                      zone_id: Optional[str] = None,
                      settings: Optional[Dict[str, Any]] = None) -> Optional[Object]:
        """
        Create a new object entity.
        
        Args:
            name: Name of the object.
            description: Description of the object.
            zone_id: Zone ID where the object should be placed.
            settings: JSON settings for object configuration (stored in properties).
            
        Returns:
            The created Object instance or None if creation fails.
        """
        # Create an Object instance directly; this creates an underlying entity record.
        obj = Object(
            name=name,
            description=description,
            zone_id=zone_id,
            object_type=ObjectType.GENERIC,
            properties=settings,
            tier=1  # Default tier for new objects
        )
        
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj
    
    def get_object(self, object_id: str) -> Optional[Object]:
        """Retrieve an object by its ID."""
        return self.db.query(Object).filter(Object.id == object_id).first()
    
    def get_objects(self, 
                    filters: Optional[Dict[str, Any]] = None, 
                    page: int = 1, 
                    page_size: int = 20, 
                    sort_by: str = "name", 
                    sort_desc: bool = False) -> Tuple[List[Object], int, int]:
        """
        Retrieve objects with optional filters, sorting, and pagination.
        
        Args:
            filters: Dictionary of filter conditions.
            page: Page number (starting from 1).
            page_size: Number of records per page.
            sort_by: Field name to sort by.
            sort_desc: Sort descending if True.
            
        Returns:
            A tuple of (list of objects, total record count, total pages).
        """
        query = self.db.query(Object)
        
        if filters:
            if 'zone_id' in filters:
                query = query.filter(Object.zone_id == filters['zone_id'])
            if 'world_id' in filters:
                # Filter by world via joining the Zone relationship.
                query = query.join(Object.zone).filter(Zone.world_id == filters['world_id'])
            if 'name' in filters:
                query = query.filter(Object.name.ilike(f"%{filters['name']}%"))
            if 'description' in filters:
                query = query.filter(Object.description.ilike(f"%{filters['description']}%"))
            if 'search' in filters and filters['search']:
                search_term = f"%{filters['search']}%"
                query = query.filter(
                    or_(
                        Object.name.ilike(search_term),
                        Object.description.ilike(search_term)
                    )
                )
        
        total_count = query.count()
        total_pages = math.ceil(total_count / page_size) if total_count > 0 else 1
        
        if hasattr(Object, sort_by):
            sort_field = getattr(Object, sort_by)
            query = query.order_by(sort_field.desc() if sort_desc else sort_field)
        else:
            query = query.order_by(Object.name.desc() if sort_desc else Object.name)
        
        offset = (page - 1) * page_size if page > 0 else 0
        objects = query.offset(offset).limit(page_size).all()
        
        return objects, total_count, total_pages
    
    def update_object(self, object_id: str, update_data: Dict[str, Any]) -> Optional[Object]:
        """
        Update an object's fields.
        
        Args:
            object_id: ID of the object to update.
            update_data: Dictionary of fields to update.
            
        Returns:
            The updated Object instance, or None if not found.
        """
        obj = self.get_object(object_id)
        if not obj:
            return None
        
        for key, value in update_data.items():
            if hasattr(obj, key):
                setattr(obj, key, value)
        
        self.db.commit()
        self.db.refresh(obj)
        return obj
    
    def delete_object(self, object_id: str) -> bool:
        """
        Delete an object.
        
        Args:
            object_id: ID of the object to delete.
            
        Returns:
            True if deletion is successful, otherwise False.
        """
        obj = self.get_object(object_id)
        if not obj:
            return False
        
        self.db.delete(obj)
        self.db.commit()
        return True
    
    def search_objects(self, 
                       query_str: str, 
                       zone_id: Optional[str] = None,
                       world_id: Optional[str] = None,
                       page: int = 1, 
                       page_size: int = 20) -> Tuple[List[Object], int, int]:
        """
        Search for objects by name or description.
        
        Args:
            query_str: Search term.
            zone_id: Optional zone ID to narrow the search.
            world_id: Optional world ID to narrow the search.
            page: Page number.
            page_size: Number of results per page.
            
        Returns:
            A tuple of (list of objects, total record count, total pages).
        """
        filters = {'search': query_str}
        if zone_id:
            filters['zone_id'] = zone_id
        if world_id:
            filters['world_id'] = world_id
        
        return self.get_objects(filters=filters, page=page, page_size=page_size)
    
    def move_object_to_zone(self, object_id: str, zone_id: str) -> bool:
        """
        Move an object to a new zone.
        
        Args:
            object_id: ID of the object to move.
            zone_id: ID of the destination zone.
            
        Returns:
            True if the move was successful, False otherwise.
        """
        obj = self.get_object(object_id)
        if not obj:
            return False
        
        obj.zone_id = zone_id
        self.db.commit()
        return True
        
    def upgrade_object_tier(self, object_id: str) -> bool:
        """
        Upgrade the tier of an object.
        
        Args:
            object_id: ID of the object to upgrade.
            
        Returns:
            True if successful, False otherwise.
        """
        obj = self.get_object(object_id)
        if not obj:
            return False
        
        obj.tier += 1
        self.db.commit()
        return True
