# app/services/entity_service.py
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import List, Optional, Dict, Any, Tuple
import math

from app.models.entity import Entity
from app.models.enums import EntityType

class EntityService:
    """Service for handling entity operations."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_entity(self, entity_id: str) -> Optional[Entity]:
        """Get any entity by ID."""
        return self.db.query(Entity).filter(Entity.id == entity_id).first()
    
    def get_entities(
        self, 
        filters: Dict[str, Any] = None, 
        page: int = 1, 
        page_size: int = 20, 
        sort_by: str = "name", 
        sort_desc: bool = False
    ) -> Tuple[List[Entity], int, int]:
        """
        Get entities with flexible filtering options.
        
        Returns:
            Tuple of (entities, total_count, total_pages)
        """
        query = self.db.query(Entity)
        
        if filters:
            if 'zone_id' in filters:
                query = query.filter(Entity.zone_id == filters['zone_id'])
            
            if 'world_id' in filters:
                # Since Entity no longer has world_id, join via the Zone relationship.
                from app.models.zone import Zone
                query = query.join(Entity.zone).filter(Zone.world_id == filters['world_id'])
            
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
        
        total_count = query.count()
        total_pages = math.ceil(total_count / page_size) if total_count > 0 else 1
        
        if hasattr(Entity, sort_by):
            sort_field = getattr(Entity, sort_by)
            query = query.order_by(sort_field.desc() if sort_desc else sort_field)
        else:
            query = query.order_by(Entity.name.desc() if sort_desc else Entity.name)
        
        offset = (page - 1) * page_size if page > 0 else 0
        entities = query.offset(offset).limit(page_size).all()
        
        return entities, total_count, total_pages
    
    def get_entities_in_zone(
        self, 
        zone_id: str, 
        entity_type: Optional[EntityType] = None,
        page: int = 1, 
        page_size: int = 20
    ) -> Tuple[List[Entity], int, int]:
        """
        Get entities in a specific zone with optional type filtering.
        """
        filters = {'zone_id': zone_id}
        if entity_type is not None:
            filters['type'] = entity_type
        return self.get_entities(
            filters=filters,
            page=page,
            page_size=page_size
        )
    
    def search_entities(
        self, 
        query_str: str,
        zone_id: Optional[str] = None,
        world_id: Optional[str] = None,
        entity_type: Optional[EntityType] = None,
        page: int = 1, 
        page_size: int = 20
    ) -> Tuple[List[Entity], int, int]:
        """
        Search for entities by name or description.
        """
        filters = {'search': query_str}
        if zone_id is not None:
            filters['zone_id'] = zone_id
        if world_id is not None:
            filters['world_id'] = world_id
        if entity_type is not None:
            filters['type'] = entity_type
        return self.get_entities(
            filters=filters,
            page=page,
            page_size=page_size
        )
    
    def create_entity(
        self, 
        name: str,
        description: Optional[str] = None,
        entity_type: EntityType = None,
        zone_id: Optional[str] = None,
        properties: Optional[Dict[str, Any]] = None
    ) -> Optional[Entity]:
        """
        Create a new entity.
        """
        if zone_id:
            from app.services.zone_service import ZoneService
            zone_service = ZoneService(self.db)
            if not zone_service.can_add_entity_to_zone(zone_id):
                return None
                
        entity = Entity(
            name=name,
            description=description,
            type=entity_type,
            zone_id=zone_id,
            properties=properties,
        )
        
        self.db.add(entity)
        self.db.commit()
        self.db.refresh(entity)
        
        return entity
    
    def delete_entity(self, entity_id: str) -> bool:
        """Delete any entity by ID."""
        entity = self.get_entity(entity_id)
        if not entity:
            return False
        
        self.db.delete(entity)
        self.db.commit()
        
        return True

    def update_entity_fields(self, entity_id: str, update_data: Dict[str, Any]) -> Optional[Entity]:
        """
        Update common fields of an entity (e.g., name and description).
        """
        entity = self.get_entity(entity_id)
        if not entity:
            return None
        
        for key in ['name', 'description']:
            if key in update_data:
                setattr(entity, key, update_data[key])
        
        # Caller should commit after this update.
        return entity
    
    def move_entity_to_zone(self, entity_id: str, zone_id: str) -> bool:
        """
        Move an entity to a different zone.
        """
        entity = self.get_entity(entity_id)
        from app.models.zone import Zone
        zone = self.db.query(Zone).filter(Zone.id == zone_id).first()
        
        if not entity or not zone:
            return False
        
        if entity.zone_id == zone_id:
            return True
        
        from app.services.zone_service import ZoneService
        zone_service = ZoneService(self.db)
        if not zone_service.can_add_entity_to_zone(zone_id):
            return False
        
        entity.zone_id = zone_id
        self.db.commit()
        
        return True

    def move_entity_with_related(self, entity_id: str, related_obj: Any, zone_id: str) -> bool:
        """
        Move an entity and update its related object's zone_id.
        """
        success = self.move_entity_to_zone(entity_id, zone_id)
        if not success:
            return False
            
        if related_obj and hasattr(related_obj, 'zone_id'):
            related_obj.zone_id = zone_id
            self.db.commit()
            
        return True
        
    def upgrade_entity_tier(self, entity_id: str) -> bool:
        """
        Upgrade an entity's tier if applicable.
        """
        entity = self.get_entity(entity_id)
        if not entity:
            return False
            
        # If the entity (or its subclass) has a tier attribute, upgrade it.
        if hasattr(entity, "tier"):
            entity.tier += 1
            self.db.commit()
            return True
        return False
        
    def check_entity_ownership(self, entity_id: str, user_id: str) -> bool:
        """
        Check if an entity is owned by a user.
        Ownership is determined by checking if the owner of the associated world
        (via the entity's zone) matches the given user_id.
        """
        entity = self.get_entity(entity_id)
        if not entity:
            return False
            
        from app.services.zone_service import ZoneService
        zone_service = ZoneService(self.db)
        zone = zone_service.get_zone(entity.zone_id)
        if not zone:
            return False
                
        from app.services.world_service import WorldService
        world_service = WorldService(self.db)
        world = world_service.get_world(zone.world_id)
        return world is not None and world.owner_id == user_id
