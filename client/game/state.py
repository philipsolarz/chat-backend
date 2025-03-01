#!/usr/bin/env python
# Game state management for RPG Chat client
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List


@dataclass
class GameState:
    """Central state management for the RPG Chat client application"""
    
    # Authentication state
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    current_user_id: Optional[str] = None
    user_email: Optional[str] = None
    is_premium: bool = False
    
    # World state
    current_world_id: Optional[str] = None
    current_world_name: Optional[str] = None
    worlds_cache: List[Dict[str, Any]] = field(default_factory=list)
    
    # Zone state
    current_zone_id: Optional[str] = None 
    current_zone_name: Optional[str] = None
    zones_cache: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)  # world_id -> zones
    
    # Character state
    current_character_id: Optional[str] = None
    current_character_name: Optional[str] = None
    characters_cache: List[Dict[str, Any]] = field(default_factory=list)
    
    # Conversation state
    current_conversation_id: Optional[str] = None
    current_participant_id: Optional[str] = None
    
    # WebSocket state
    connected: bool = False
    
    # Application control
    shutdown_requested: bool = False
    
    # Websocket input control
    waiting_for_field: Optional[str] = None
    waiting_for_prompt: Optional[str] = None
    
    def is_authenticated(self) -> bool:
        """Check if user is currently authenticated"""
        return self.access_token is not None
    
    def clear_auth(self):
        """Clear authentication data"""
        self.access_token = None
        self.refresh_token = None
        self.current_user_id = None
        self.user_email = None
        self.is_premium = False
    
    def clear_world(self):
        """Clear world selection"""
        self.current_world_id = None
        self.current_world_name = None
    
    def clear_zone(self):
        """Clear zone selection"""
        self.current_zone_id = None
        self.current_zone_name = None
    
    def clear_character(self):
        """Clear character selection"""
        self.current_character_id = None
        self.current_character_name = None
    
    def clear_conversation(self):
        """Clear conversation data"""
        self.current_conversation_id = None
        self.current_participant_id = None
    
    def cache_worlds(self, worlds: List[Dict[str, Any]]):
        """Cache world data"""
        self.worlds_cache = worlds
    
    def cache_zones(self, world_id: str, zones: List[Dict[str, Any]]):
        """Cache zone data for a specific world"""
        self.zones_cache[world_id] = zones
    
    def cache_characters(self, characters: List[Dict[str, Any]]):
        """Cache character data"""
        self.characters_cache = characters
    
    def reset(self):
        """Reset all state (except auth)"""
        self.clear_world()
        self.clear_zone()
        self.clear_character()
        self.clear_conversation()
        self.worlds_cache = []
        self.zones_cache = {}
        self.characters_cache = []
        self.connected = False


# Global state instance
game_state = GameState()