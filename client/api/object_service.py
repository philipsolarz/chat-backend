#!/usr/bin/env python
# Object service for managing game objects
from typing import Dict, Any, Optional, List, Tuple

from client.api.base_service import BaseService, APIError
from client.game.state import game_state
from client.ui.console import console

class ObjectService(BaseService):
    """Service for object-related API operations"""
    
    async def get_objects(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Get objects with filters"""
        try:
            # Build query params
            params = {}
            if filters:
                for key, value in filters.items():
                    params[key] = value
                    
            response = await self.get("/objects/", params)
            return response.get("items", [])
        except APIError as e:
            console.print(f"[red]Failed to get objects: {e.detail}[/red]")
            return []
        except Exception as e:
            console.print(f"[red]Error getting objects: {str(e)}[/red]")
            return []
    
    async def get_objects_in_zone(self, zone_id: str) -> List[Dict[str, Any]]:
        """Get all objects in a zone"""
        filters = {"zone_id": zone_id}
        return await self.get_objects(filters)
    
    async def get_object(self, object_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific object by ID"""
        try:
            return await self.get(f"/objects/{object_id}")
        except APIError as e:
            console.print(f"[red]Failed to get object: {e.detail}[/red]")
            return None
        except Exception as e:
            console.print(f"[red]Error getting object: {str(e)}[/red]")
            return None
    
    async def create_object(self, name: str, description: str, zone_id: str, 
                          properties: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """Create a new object in a zone"""
        try:
            payload = {
                "name": name,
                "description": description,
                "zone_id": zone_id,
                "properties": properties or {}
            }
            
            return await self.post("/objects/", payload)
        except APIError as e:
            console.print(f"[red]Failed to create object: {e.detail}[/red]")
            return None
        except Exception as e:
            console.print(f"[red]Error creating object: {str(e)}[/red]")
            return None
    
    async def update_object(self, object_id: str, 
                          update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update an object's properties"""
        try:
            return await self.put(f"/objects/{object_id}", update_data)
        except APIError as e:
            console.print(f"[red]Failed to update object: {e.detail}[/red]")
            return None
        except Exception as e:
            console.print(f"[red]Error updating object: {str(e)}[/red]")
            return None
    
    async def delete_object(self, object_id: str) -> bool:
        """Delete an object"""
        try:
            await self.delete(f"/objects/{object_id}")
            return True
        except APIError as e:
            console.print(f"[red]Failed to delete object: {e.detail}[/red]")
            return False
        except Exception as e:
            console.print(f"[red]Error deleting object: {str(e)}[/red]")
            return False
    
    async def move_object_to_zone(self, object_id: str, zone_id: str) -> Optional[Dict[str, Any]]:
        """Move an object to a different zone"""
        try:
            return await self.post(f"/objects/{object_id}/move?zone_id={zone_id}", {})
        except APIError as e:
            console.print(f"[red]Failed to move object: {e.detail}[/red]")
            return None
        except Exception as e:
            console.print(f"[red]Error moving object: {str(e)}[/red]")
            return None
    
    async def search_objects(self, query: str, zone_id: Optional[str] = None, 
                           world_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Search for objects by name or description"""
        try:
            params = {"query": query}
            
            if zone_id:
                params["zone_id"] = zone_id
                
            if world_id:
                params["world_id"] = world_id
                
            response = await self.get("/objects/search/", params)
            return response.get("items", [])
        except APIError as e:
            console.print(f"[red]Failed to search objects: {e.detail}[/red]")
            return []
        except Exception as e:
            console.print(f"[red]Error searching objects: {str(e)}[/red]")
            return []
    
    async def upgrade_object_tier(self, object_id: str, 
                                success_url: str = "http://localhost:3000/success", 
                                cancel_url: str = "http://localhost:3000/cancel") -> Optional[Dict[str, str]]:
        """Purchase a tier upgrade for an object"""
        try:
            params = {
                "success_url": success_url,
                "cancel_url": cancel_url
            }
            
            response = await self.post(f"/objects/{object_id}/upgrade-tier", params)
            return response
        except APIError as e:
            console.print(f"[red]Failed to create upgrade checkout: {e.detail}[/red]")
            return None
        except Exception as e:
            console.print(f"[red]Error creating upgrade checkout: {str(e)}[/red]")
            return None