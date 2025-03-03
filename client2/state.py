# Game state management for RPG Client
from typing import Dict, Any, Optional

class GameState:
    """Simple state management for tracking the current game session"""
    
    def __init__(self):
        # Authentication
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.user_id: Optional[str] = None
        self.user_email: Optional[str] = None
        
        # World
        self.current_world_id: Optional[str] = None
        self.current_world_name: Optional[str] = None
        
        # Character
        self.current_character_id: Optional[str] = None
        self.current_character_name: Optional[str] = None
        
        # Zone
        self.current_zone_id: Optional[str] = None
        self.current_zone_name: Optional[str] = None
    
    def is_authenticated(self) -> bool:
        """Check if user is currently authenticated"""
        return self.access_token is not None
    
    def set_auth(self, data: Dict[str, Any]) -> None:
        """Set authentication data from API response"""
        self.access_token = data.get("access_token")
        self.refresh_token = data.get("refresh_token")
        self.user_id = data.get("user_id")
        self.user_email = data.get("email")
    
    def clear_auth(self) -> None:
        """Clear authentication data"""
        self.access_token = None
        self.refresh_token = None
        self.user_id = None
        self.user_email = None
    
    def set_world(self, world: Dict[str, Any]) -> None:
        """Set the current world"""
        self.current_world_id = world.get("id")
        self.current_world_name = world.get("name")
    
    def set_character(self, character: Dict[str, Any]) -> None:
        """Set the current character"""
        self.current_character_id = character.get("id")
        self.current_character_name = character.get("name")
        
        # If character has a zone, set it as current
        if character.get("zone_id"):
            self.current_zone_id = character.get("zone_id")
    
    def set_zone(self, zone: Dict[str, Any]) -> None:
        """Set the current zone"""
        self.current_zone_id = zone.get("id")
        self.current_zone_name = zone.get("name")
    
    def clear(self) -> None:
        """Reset all state"""
        self.__init__()

# Global state instance
game_state = GameState()