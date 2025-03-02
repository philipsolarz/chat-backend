#!/usr/bin/env python
# Entity service for managing entities
from typing import Dict, Any, Optional, List, Tuple

from client.api.base_service import BaseService, APIError
from client.game.state import game_state
from client.ui.console import console


class EntityService(BaseService):
    """Service for entity-related API operations"""
    
    async def get_entities(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Get entities with filters"""
        try:
            # Build query params
            params = {}
            if filters:
                for key, value in filters.items():
                    params[key] = value
                    
            response = await self.get("/entities/", params)
            entities = response.get("items", [])
            
            return entities
        except APIError as e:
            console.print(f"[red]Failed to get entities: {e.detail}[/red]")
            return []
        except Exception as e:
            console.print(f"[red]Error getting entities: {str(e)}[/red]")
            return []
    
    async def get_entities_in_zone(self, zone_id: str, entity_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all entities in a zone, optionally filtered by type"""
        filters = {"zone_id": zone_id}
        if entity_type:
            filters["entity_type"] = entity_type
            
        return await self.get_entities(filters)
    
    async def get_entity(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific entity by ID"""
        try:
            return await self.get(f"/entities/{entity_id}")
        except APIError as e:
            console.print(f"[red]Failed to get entity: {e.detail}[/red]")
            return None
        except Exception as e:
            console.print(f"[red]Error getting entity: {str(e)}[/red]")
            return None
    
    async def move_entity_to_zone(self, entity_id: str, zone_id: str) -> bool:
        """Move an entity to a different zone"""
        try:
            await self.post(f"/entities/{entity_id}/move?zone_id={zone_id}", {})
            return True
        except APIError as e:
            console.print(f"[red]Failed to move entity: {e.detail}[/red]")
            return False
        except Exception as e:
            console.print(f"[red]Error moving entity: {str(e)}[/red]")
            return False
    
    async def interact_with_entity(self, entity_id: str, action: str, details: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
        """Perform an interaction with an entity"""
        try:
            payload = {
                "action": action,
            }
            
            if details:
                payload["details"] = details
                
            return await self.post(f"/entities/{entity_id}/interact", payload)
        except APIError as e:
            console.print(f"[red]Failed to interact with entity: {e.detail}[/red]")
            return None
        except Exception as e:
            console.print(f"[red]Error interacting with entity: {str(e)}[/red]")
            return None
    
    async def search_entities(self, query: str, zone_id: Optional[str] = None, entity_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Search for entities by name or description"""
        try:
            params = {"query": query}
            
            if zone_id:
                params["zone_id"] = zone_id
                
            if entity_type:
                params["entity_type"] = entity_type
                
            response = await self.get("/entities/search/", params)
            return response.get("items", [])
        except APIError as e:
            console.print(f"[red]Failed to search entities: {e.detail}[/red]")
            return []
        except Exception as e:
            console.print(f"[red]Error searching entities: {str(e)}[/red]")
            return []