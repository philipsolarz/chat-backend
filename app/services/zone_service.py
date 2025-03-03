# app/services/zone_service.py
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from typing import List, Optional, Dict, Any, Tuple
import math

from app.models.zone import Zone
from app.models.world import World
from app.models.entity import Entity


class ZoneService:
    """Service for handling zone operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_zone(self, 
                    world_id: str,
                    name: str,
                    description: Optional[str] = None,
                    properties: Optional[Dict[str, Any]] = None,
                    parent_zone_id: Optional[str] = None,
                    tier: int = 1) -> Optional[Zone]:
        """
        Create a new zone
        
        Args:
            world_id: ID of the world this zone belongs to
            name: Name of the zone
            description: Description of the zone
            properties: JSON properties for zone configuration
            parent_zone_id: ID of the parent zone (for sub-zones)
            tier: Initial tier level (defaults to 1)
            
        Returns:
            The created zone or None if world or parent zone is invalid, or zone limit is reached.
        """
        # Check world existence
        world = self.db.query(World).filter(World.id == world_id).first()
        if not world:
            return None
        
        # Check zone limit based on world's tier via world service (assumes WorldService is implemented)
        from app.services.world_service import WorldService
        world_service = WorldService(self.db)
        if not world_service.can_add_zone_to_world(world_id):
            return None
        
        # Validate parent zone if provided
        if parent_zone_id:
            parent_zone = self.db.query(Zone).filter(
                Zone.id == parent_zone_id,
                Zone.world_id == world_id  # Ensure parent zone is in the same world
            ).first()
            if not parent_zone:
                return None
        
        # Create the zone using the updated property name
        zone = Zone(
            name=name,
            description=description,
            properties=properties,
            world_id=world_id,
            parent_zone_id=parent_zone_id,
            tier=tier
        )
        
        self.db.add(zone)
        self.db.commit()
        self.db.refresh(zone)
        
        return zone
    
    def get_zone(self, zone_id: str) -> Optional[Zone]:
        """Get a zone by ID"""
        return self.db.query(Zone).filter(Zone.id == zone_id).first()
    
    def get_zones(self, 
                  filters: Dict[str, Any] = None, 
                  page: int = 1, 
                  page_size: int = 20, 
                  sort_by: str = "name", 
                  sort_desc: bool = False) -> Tuple[List[Zone], int, int]:
        """
        Get zones with flexible filtering options
        
        Args:
            filters: Dictionary of filter conditions
            page: Page number (starting from 1)
            page_size: Number of records per page
            sort_by: Field to sort by
            sort_desc: Whether to sort in descending order
            
        Returns:
            Tuple of (zones, total_count, total_pages)
        """
        query = self.db.query(Zone)
        
        # Apply filters if provided
        if filters:
            if 'world_id' in filters:
                query = query.filter(Zone.world_id == filters['world_id'])
            
            if 'name' in filters:
                query = query.filter(Zone.name.ilike(f"%{filters['name']}%"))
            
            if 'description' in filters:
                query = query.filter(Zone.description.ilike(f"%{filters['description']}%"))
            
            if 'tier' in filters:
                query = query.filter(Zone.tier == filters['tier'])
            
            if 'parent_zone_id' in filters:
                if filters['parent_zone_id'] is None:
                    # Get top-level zones (no parent)
                    query = query.filter(Zone.parent_zone_id.is_(None))
                else:
                    # Get sub-zones of a specific parent
                    query = query.filter(Zone.parent_zone_id == filters['parent_zone_id'])
                
            if 'search' in filters and filters['search']:
                search_term = f"%{filters['search']}%"
                query = query.filter(
                    or_(
                        Zone.name.ilike(search_term),
                        Zone.description.ilike(search_term)
                    )
                )
        
        # Get total count before pagination
        total_count = query.count()
        total_pages = math.ceil(total_count / page_size) if total_count > 0 else 1
        
        # Apply sorting (default to name)
        if hasattr(Zone, sort_by):
            sort_field = getattr(Zone, sort_by)
            query = query.order_by(sort_field.desc() if sort_desc else sort_field)
        else:
            query = query.order_by(Zone.name.desc() if sort_desc else Zone.name)
        
        # Apply pagination
        offset = (page - 1) * page_size if page > 0 else 0
        zones = query.offset(offset).limit(page_size).all()
        
        return zones, total_count, total_pages
    
    def get_zone_hierarchy(self, world_id: str) -> List[Dict[str, Any]]:
        """
        Get the full zone hierarchy for a world
        
        Args:
            world_id: ID of the world
            
        Returns:
            List of top-level zones with nested sub-zones
        """
        all_zones = self.db.query(Zone).filter(Zone.world_id == world_id).all()
        
        # Build a dictionary mapping parent IDs to children
        parent_to_children = {}
        for zone in all_zones:
            parent_id = zone.parent_zone_id
            parent_to_children.setdefault(parent_id, []).append(zone)
        
        # Build the hierarchy starting with top-level zones
        top_level_zones = parent_to_children.get(None, [])
        
        def build_tree(zone: Zone) -> Dict[str, Any]:
            """Recursively build the zone tree"""
            result = {
                "id": zone.id,
                "name": zone.name,
                "description": zone.description,
                "tier": zone.tier,
                "properties": zone.properties,
                "world_id": zone.world_id,
                "parent_zone_id": zone.parent_zone_id,
                "created_at": zone.created_at.isoformat(),
                "updated_at": zone.updated_at.isoformat(),
                "sub_zones": []
            }
            children = parent_to_children.get(zone.id, [])
            for child in children:
                result["sub_zones"].append(build_tree(child))
            return result
        
        hierarchy = [build_tree(zone) for zone in top_level_zones]
        return hierarchy
    
    def update_zone(self, zone_id: str, update_data: Dict[str, Any]) -> Optional[Zone]:
        """
        Update a zone's properties
        
        Args:
            zone_id: ID of the zone to update
            update_data: Dictionary of fields to update
            
        Returns:
            Updated zone or None if not found or update failed.
        """
        zone = self.get_zone(zone_id)
        if not zone:
            return None
        
        # Validate parent zone if being changed
        if 'parent_zone_id' in update_data and update_data['parent_zone_id'] is not None:
            if update_data['parent_zone_id'] == zone_id:
                return None  # Cannot set self as parent
                
            parent_zone = self.db.query(Zone).filter(
                Zone.id == update_data['parent_zone_id'],
                Zone.world_id == zone.world_id
            ).first()
            if not parent_zone:
                return None
            if self.is_descendant(update_data['parent_zone_id'], zone_id):
                return None  # Would create circular reference
        
        # Update only the fields provided; note that we now use 'properties'
        for key, value in update_data.items():
            # If the update uses "settings", map it to "properties"
            if key == "settings":
                key = "properties"
            if hasattr(zone, key):
                setattr(zone, key, value)
        
        self.db.commit()
        self.db.refresh(zone)
        return zone
    
    def delete_zone(self, zone_id: str) -> bool:
        """
        Delete a zone.
        
        If the zone has sub-zones:
          - Their parent_zone_id is updated to the deleted zone's parent_zone_id.
        If the zone has entities:
          - They are moved to the parent zone (if one exists). Otherwise, deletion is disallowed.
        
        Args:
            zone_id: ID of the zone to delete.
            
        Returns:
            True if successful, False otherwise.
        """
        zone = self.get_zone(zone_id)
        if not zone:
            return False
        
        # Handle entities in this zone
        entities = self.db.query(Entity).filter(Entity.zone_id == zone_id).all()
        if entities and not zone.parent_zone_id:
            return False  # Cannot delete a zone with entities if no parent exists
        
        if zone.parent_zone_id and entities:
            for entity in entities:
                entity.zone_id = zone.parent_zone_id
        
        # Update sub-zones' parent pointers
        sub_zones = self.db.query(Zone).filter(Zone.parent_zone_id == zone_id).all()
        for sub_zone in sub_zones:
            sub_zone.parent_zone_id = zone.parent_zone_id
        
        self.db.delete(zone)
        self.db.commit()
        return True
    
    def is_descendant(self, potential_descendant_id: str, ancestor_id: str) -> bool:
        """
        Check if a zone is a descendant of another zone.
        
        Args:
            potential_descendant_id: ID of the zone to check.
            ancestor_id: ID of the potential ancestor.
            
        Returns:
            True if potential_descendant_id is a descendant of ancestor_id.
        """
        zone = self.get_zone(potential_descendant_id)
        if not zone:
            return False
        while zone.parent_zone_id:
            if zone.parent_zone_id == ancestor_id:
                return True
            zone = self.get_zone(zone.parent_zone_id)
            if not zone:
                break
        return False
    
    def count_zones_in_world(self, world_id: str) -> int:
        """Count the number of zones in a world."""
        return self.db.query(func.count(Zone.id)).filter(Zone.world_id == world_id).scalar() or 0
    
    def count_entities_in_zone(self, zone_id: str) -> int:
        """Count the number of entities in a zone."""
        return self.db.query(func.count(Entity.id)).filter(Entity.zone_id == zone_id).scalar() or 0

    def calculate_entity_limit(self, tier: int) -> int:
        """
        Calculate entity limit based on zone tier.
        
        Args:
            tier: The zone's tier.
            
        Returns:
            The maximum number of entities allowed.
        """
        BASE_ENTITY_LIMIT = 25  # Base limit for tier 1
        return BASE_ENTITY_LIMIT * tier

    def can_add_entity_to_zone(self, zone_id: str) -> bool:
        """
        Check if more entities can be added to a zone.
        
        Args:
            zone_id: ID of the zone.
            
        Returns:
            True if the current entity count is below the limit, False otherwise.
        """
        zone = self.get_zone(zone_id)
        if not zone:
            return False
        entity_count = self.count_entities_in_zone(zone_id)
        entity_limit = self.calculate_entity_limit(zone.tier)
        return entity_count < entity_limit

    def get_zone_entity_limits(self, zone_id: str) -> Dict[str, Any]:
        """
        Get entity limit information for a zone.
        
        Args:
            zone_id: ID of the zone.
            
        Returns:
            Dictionary with counts, limit, remaining capacity, and usage percentage.
        """
        zone = self.get_zone(zone_id)
        if not zone:
            return {
                "entity_count": 0,
                "entity_limit": 0,
                "remaining_capacity": 0,
                "usage_percentage": 0,
                "tier": 0
            }
            
        entity_count = self.count_entities_in_zone(zone_id)
        entity_limit = self.calculate_entity_limit(zone.tier)
        remaining_capacity = max(0, entity_limit - entity_count)
        usage_percentage = (entity_count / entity_limit * 100) if entity_limit > 0 else 100
        
        return {
            "entity_count": entity_count,
            "entity_limit": entity_limit,
            "remaining_capacity": remaining_capacity,
            "usage_percentage": round(usage_percentage, 2),
            "tier": zone.tier
        }

    def upgrade_zone_tier(self, zone_id: str) -> bool:
        """
        Upgrade a zone's tier.
        
        Args:
            zone_id: ID of the zone to upgrade.
            
        Returns:
            True if the upgrade is successful, False otherwise.
        """
        zone = self.get_zone(zone_id)
        if not zone:
            return False
        zone.tier += 1
        self.db.commit()
        return True
        
    def get_zone_with_entities(self, zone_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a zone's details along with counts of entities by type and sub-zone count.
        
        Args:
            zone_id: ID of the zone.
            
        Returns:
            Dictionary containing zone details and entity counts, or None if not found.
        """
        zone = self.get_zone(zone_id)
        if not zone:
            return None
        
        # Count entities by type
        from app.models.enums import EntityType
        entity_counts = {}
        for entity_type in EntityType:
            count = self.db.query(func.count(Entity.id)).filter(
                Entity.zone_id == zone_id,
                Entity.type == entity_type.value
            ).scalar() or 0
            entity_counts[entity_type.value] = count
        
        # Count sub-zones
        sub_zone_count = self.db.query(func.count(Zone.id)).filter(
            Zone.parent_zone_id == zone_id
        ).scalar() or 0
        
        entity_limit = self.calculate_entity_limit(zone.tier)
        total_entities = sum(entity_counts.values())
        
        result = {
            "id": zone.id,
            "name": zone.name,
            "description": zone.description,
            "world_id": zone.world_id,
            "parent_zone_id": zone.parent_zone_id,
            "tier": zone.tier,
            "properties": zone.properties,
            "created_at": zone.created_at.isoformat(),
            "updated_at": zone.updated_at.isoformat(),
            "entity_counts": entity_counts,
            "total_entities": total_entities,
            "sub_zone_count": sub_zone_count,
            "entity_limit": entity_limit,
            "remaining_capacity": max(0, entity_limit - total_entities)
        }
        
        return result
