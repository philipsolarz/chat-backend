#!/usr/bin/env python
# World service for managing worlds
from typing import Dict, Any, Optional, List, Tuple

from client.api.base_service import BaseService, APIError
from client.game.state import game_state
from client.ui import console


class WorldService(BaseService):
    """Service for world-related API operations"""
    
    async def get_worlds(self) -> List[Dict[str, Any]]:
        """Get list of accessible worlds for the current user"""
        try:
            response = await self.get("/worlds/")
            worlds = response.get("items", [])
            
            # Update cache
            game_state.cache_worlds(worlds)
            
            return worlds
        except APIError as e:
            print(f"Failed to get worlds: {e.detail}")
            return []
        except Exception as e:
            print(f"Error getting worlds: {str(e)}")
            return []
    
    async def get_starter_worlds(self) -> List[Dict[str, Any]]:
        """Get list of starter worlds"""
        try:
            response = await self.get("/worlds/starter")
            return response.get("items", [])
        except APIError as e:
            print(f"Failed to get starter worlds: {e.detail}")
            return []
        except Exception as e:
            print(f"Error getting starter worlds: {str(e)}")
            return []
    
    async def create_world(self, name: str, description: Optional[str] = None, 
                          genre: Optional[str] = None, is_public: bool = False) -> Optional[Dict[str, Any]]:
        """Create a new world"""
        try:
            payload = {
                "name": name,
                "description": description,
                "genre": genre,
                "is_public": is_public
            }
            
            world = await self.post("/worlds/", payload)
            
            if world:
                # Update current world in state
                game_state.current_world_id = world.get("id")
                game_state.current_world_name = world.get("name")
                
                # Refresh worlds cache
                await self.get_worlds()
            
            return world
        except APIError as e:
            print(f"Failed to create world: {e.detail}")
            return None
        except Exception as e:
            print(f"Error creating world: {str(e)}")
            return None
    
    async def get_world(self, world_id: str) -> Optional[Dict[str, Any]]:
        """Get details of a specific world"""
        try:
            return await self.get(f"/worlds/{world_id}")
        except APIError as e:
            print(f"Failed to get world: {e.detail}")
            return None
        except Exception as e:
            print(f"Error getting world: {str(e)}")
            return None
    
    async def update_world(self, world_id: str, 
                          update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update a world's details"""
        try:
            updated_world = await self.put(f"/worlds/{world_id}", update_data)
            
            # If this is the current world, update state
            if world_id == game_state.current_world_id:
                game_state.current_world_name = updated_world.get("name")
            
            # Refresh worlds cache
            await self.get_worlds()
            
            return updated_world
        except APIError as e:
            print(f"Failed to update world: {e.detail}")
            return None
        except Exception as e:
            print(f"Error updating world: {str(e)}")
            return None
    
    async def delete_world(self, world_id: str) -> bool:
        """Delete a world"""
        try:
            await self.delete(f"/worlds/{world_id}")
            
            # If this was the current world, clear selection
            if world_id == game_state.current_world_id:
                game_state.clear_world()
            
            # Refresh worlds cache
            await self.get_worlds()
            
            return True
        except APIError as e:
            print(f"Failed to delete world: {e.detail}")
            return False
        except Exception as e:
            print(f"Error deleting world: {str(e)}")
            return False
    
    async def purchase_premium_world(self, name: str, description: Optional[str] = None, 
                                    genre: Optional[str] = None) -> Optional[Dict[str, str]]:
        """
        Start premium world purchase process.
        This is a two-step process:
        1. Create a regular world
        2. Initiate tier upgrade checkout for that world
        """
        try:
            # First create a regular world
            world = await self.create_world(name, description, genre)
            
            if not world or "id" not in world:
                console.print("[bold red]Failed to create base world[/bold red]")
                return None
                
            # Then initiate tier upgrade checkout
            payload = {
                "world_id": world["id"],
                "success_url": "http://localhost:3000/success",
                "cancel_url": "http://localhost:3000/cancel"
            }
            
            result = await self.post("/worlds/tier-upgrade-checkout", payload)
            
            if result and "checkout_url" in result:
                console.print(f"[bold green]Premium world purchase initiated for {name}![/bold green]")
                return result
            else:
                console.print(f"[bold yellow]World '{name}' created, but premium upgrade failed to initiate[/bold yellow]")
                return {"world_id": world["id"], "error": "Failed to initiate premium upgrade"}
        except Exception as e:
            console.print(f"[bold red]Error initiating premium world purchase: {str(e)}[/bold red]")
            return None