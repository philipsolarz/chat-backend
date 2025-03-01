#!/usr/bin/env python
# Zone service for managing zones
from typing import Dict, Any, Optional, List, Tuple

from client.api.base_service import BaseService, APIError
from client.game.state import game_state


class ZoneService(BaseService):
    """Service for zone-related API operations"""
    
    async def get_zones(self, world_id: str, parent_zone_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get zones for a world, optionally filtered by parent zone"""
        try:
            params = {
                "world_id": world_id
            }
            
            if parent_zone_id is not None:
                params["parent_zone_id"] = parent_zone_id
            
            response = await self.get("/zones/", params)
            zones = response.get("items", [])
            
            # Update cache if this is a top-level request
            if parent_zone_id is None:
                game_state.cache_zones(world_id, zones)
            
            return zones
        except APIError as e:
            print(f"Failed to get zones: {e.detail}")
            return []
        except Exception as e:
            print(f"Error getting zones: {str(e)}")
            return []
    
    async def get_zone_hierarchy(self, world_id: str) -> List[Dict[str, Any]]:
        """Get complete zone hierarchy for a world"""
        try:
            params = {
                "world_id": world_id
            }
            
            response = await self.get("/zones/hierarchy", params)
            return response.get("zones", [])
        except APIError as e:
            print(f"Failed to get zone hierarchy: {e.detail}")
            return []
        except Exception as e:
            print(f"Error getting zone hierarchy: {str(e)}")
            return []
    
    async def get_zone(self, zone_id: str) -> Optional[Dict[str, Any]]:
        """Get details of a specific zone"""
        try:
            return await self.get(f"/zones/{zone_id}")
        except APIError as e:
            print(f"Failed to get zone: {e.detail}")
            return None
        except Exception as e:
            print(f"Error getting zone: {str(e)}")
            return None
    
    async def create_zone(self, world_id: str, name: str, description: str, 
                         zone_type: Optional[str] = None, 
                         parent_zone_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Create a new zone"""
        try:
            payload = {
                "world_id": world_id,
                "name": name,
                "description": description,
                "zone_type": zone_type,
                "parent_zone_id": parent_zone_id
            }
            
            zone = await self.post("/zones/", payload)
            
            if zone:
                # Update current zone in state
                game_state.current_zone_id = zone.get("id")
                game_state.current_zone_name = zone.get("name")
                
                # Refresh zones cache
                await self.get_zones(world_id)
            
            return zone
        except APIError as e:
            print(f"Failed to create zone: {e.detail}")
            return None
        except Exception as e:
            print(f"Error creating zone: {str(e)}")
            return None
    
    async def update_zone(self, zone_id: str, update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update a zone's details"""
        try:
            updated_zone = await self.put(f"/zones/{zone_id}", update_data)
            
            # If this is the current zone, update state
            if zone_id == game_state.current_zone_id:
                game_state.current_zone_name = updated_zone.get("name")
            
            # Refresh zones cache if we know the world
            if game_state.current_world_id:
                await self.get_zones(game_state.current_world_id)
            
            return updated_zone
        except APIError as e:
            print(f"Failed to update zone: {e.detail}")
            return None
        except Exception as e:
            print(f"Error updating zone: {str(e)}")
            return None
    
    async def delete_zone(self, zone_id: str) -> bool:
        """Delete a zone"""
        try:
            # Get the zone first to know its world_id
            zone = await self.get_zone(zone_id)
            world_id = None
            if zone:
                world_id = zone.get("world_id")
            
            await self.delete(f"/zones/{zone_id}")
            
            # If this was the current zone, clear selection
            if zone_id == game_state.current_zone_id:
                game_state.clear_zone()
            
            # Refresh zones cache if we know the world
            if world_id:
                await self.get_zones(world_id)
            
            return True
        except APIError as e:
            print(f"Failed to delete zone: {e.detail}")
            return False
        except Exception as e:
            print(f"Error deleting zone: {str(e)}")
            return False
    
    async def get_zone_characters(self, zone_id: str) -> List[Dict[str, Any]]:
        """Get all characters in a zone"""
        try:
            return await self.get(f"/zones/{zone_id}/characters")
        except APIError as e:
            print(f"Failed to get characters in zone: {e.detail}")
            return []
        except Exception as e:
            print(f"Error getting characters in zone: {str(e)}")
            return []
    
    async def get_zone_agents(self, zone_id: str) -> List[Dict[str, Any]]:
        """Get all AI agents (NPCs) in a zone"""
        try:
            return await self.get(f"/zones/{zone_id}/agents")
        except APIError as e:
            print(f"Failed to get agents in zone: {e.detail}")
            return []
        except Exception as e:
            print(f"Error getting agents in zone: {str(e)}")
            return []
    
    async def purchase_zone_upgrade(self, world_id: str) -> Optional[Dict[str, str]]:
        """
        Purchase a zone limit upgrade
        Returns a checkout URL to complete payment
        """
        try:
            payload = {
                "world_id": world_id,
                "success_url": "http://localhost:3000/success",
                "cancel_url": "http://localhost:3000/cancel"
            }
            
            result = await self.post("/zones/zone-upgrade-checkout", payload)
            return result
        except APIError as e:
            print(f"Failed to initiate zone upgrade purchase: {e.detail}")
            return None
        except Exception as e:
            print(f"Error initiating zone upgrade purchase: {str(e)}")
            return None
    
    async def get_agent_limits(self, zone_id: str) -> Optional[Dict[str, Any]]:
        """Get agent limit information for a zone"""
        try:
            return await self.get(f"/zones/{zone_id}/agent-limits")
        except APIError as e:
            print(f"Failed to get agent limits: {e.detail}")
            return None
        except Exception as e:
            print(f"Error getting agent limits: {str(e)}")
            return None
    
    async def purchase_agent_limit_upgrade(self, zone_id: str) -> Optional[Dict[str, str]]:
        """
        Purchase an agent limit upgrade for a zone
        Returns a checkout URL to complete payment
        """
        try:
            payload = {
                "zone_id": zone_id,
                "success_url": "http://localhost:3000/success",
                "cancel_url": "http://localhost:3000/cancel"
            }
            
            result = await self.post("/zones/agent-limit-upgrade-checkout", payload)
            return result
        except APIError as e:
            print(f"Failed to initiate agent limit upgrade purchase: {e.detail}")
            return None
        except Exception as e:
            print(f"Error initiating agent limit upgrade purchase: {str(e)}")
            return None
    
    async def move_character_to_zone(self, character_id: str, zone_id: str) -> Optional[Dict[str, Any]]:
        """Move a character to a different zone"""
        try:
            payload = {
                "zone_id": zone_id
            }
            
            return await self.post(f"/zones/characters/{character_id}/move", payload)
        except APIError as e:
            print(f"Failed to move character: {e.detail}")
            return None
        except Exception as e:
            print(f"Error moving character: {str(e)}")
            return None