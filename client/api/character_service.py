#!/usr/bin/env python
# Character service for managing characters on the client side
from typing import Dict, Any, Optional, List, Tuple

from client.api.base_service import BaseService, APIError
from client.game.state import game_state


class CharacterService(BaseService):
    """Service for character-related API operations"""
    
    async def get_characters(self) -> List[Dict[str, Any]]:
        """Get list of user's characters"""
        try:
            response = await self.get("/characters/")
            characters = response.get("items", [])
            # Update cache
            game_state.cache_characters(characters)
            return characters
        except APIError as e:
            print(f"Failed to get characters: {e.detail}")
            return []
        except Exception as e:
            print(f"Error getting characters: {str(e)}")
            return []
    
    async def get_public_characters(self) -> List[Dict[str, Any]]:
        """Get list of public characters"""
        try:
            response = await self.get("/characters/public")
            return response.get("items", [])
        except APIError as e:
            print(f"Failed to get public characters: {e.detail}")
            return []
        except Exception as e:
            print(f"Error getting public characters: {str(e)}")
            return []
    
    async def create_character(self, name: str, description: Optional[str] = None, 
                               zone_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Create a new character.
        
        Note: The updated API only requires a zone_id, name, and description.
        """
        try:
            payload = {
                "name": name,
                "description": description,
                "zone_id": zone_id
            }
            character = await self.post("/characters/", payload)
            if character:
                # Update current character in state
                game_state.current_character_id = character.get("id")
                game_state.current_character_name = character.get("name")
                # Refresh characters cache
                await self.get_characters()
            return character
        except APIError as e:
            print(f"Failed to create character: {e.detail}")
            return None
        except Exception as e:
            print(f"Error creating character: {str(e)}")
            return None
    
    async def get_character(self, character_id: str) -> Optional[Dict[str, Any]]:
        """Get details of a specific character"""
        try:
            return await self.get(f"/characters/{character_id}")
        except APIError as e:
            print(f"Failed to get character: {e.detail}")
            return None
        except Exception as e:
            print(f"Error getting character: {str(e)}")
            return None
    
    async def update_character(self, character_id: str, 
                               update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update a character's details"""
        try:
            updated_character = await self.put(f"/characters/{character_id}", update_data)
            if character_id == game_state.current_character_id:
                game_state.current_character_name = updated_character.get("name")
            # Refresh characters cache
            await self.get_characters()
            return updated_character
        except APIError as e:
            print(f"Failed to update character: {e.detail}")
            return None
        except Exception as e:
            print(f"Error updating character: {str(e)}")
            return None
    
    async def delete_character(self, character_id: str) -> bool:
        """Delete a character"""
        try:
            await self.delete(f"/characters/{character_id}")
            if character_id == game_state.current_character_id:
                game_state.clear_character()
            # Refresh characters cache
            await self.get_characters()
            return True
        except APIError as e:
            print(f"Failed to delete character: {e.detail}")
            return False
        except Exception as e:
            print(f"Error deleting character: {str(e)}")
            return False
            
    async def get_characters_in_zone(self, zone_id: str) -> List[Dict[str, Any]]:
        """Get all characters in a zone (filtered locally)"""
        try:
            all_characters = await self.get_characters()
            return [char for char in all_characters if char.get("zone_id") == zone_id]
        except Exception as e:
            print(f"Error getting characters in zone: {str(e)}")
            return []
