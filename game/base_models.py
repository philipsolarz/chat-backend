"""
Simple base models for the Agentique Game Engine.
"""
from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from uuid import uuid4
from datetime import datetime

# Base model with ID generation
class GameModel(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4())[:8])
    
    class Config:
        arbitrary_types_allowed = True

# Item and Inventory
class Item(GameModel):
    name: str
    description: str
    properties: Dict[str, Any] = Field(default_factory=dict)

class Inventory(GameModel):
    items: Dict[str, int] = Field(default_factory=dict)  # item_id -> quantity
    
    def add_item(self, item: Item, quantity: int = 1) -> None:
        """Add an item to the inventory"""
        if item.id in self.items:
            self.items[item.id] += quantity
        else:
            self.items[item.id] = quantity
    
    def remove_item(self, item_id: str, quantity: int = 1) -> bool:
        """Remove an item from the inventory"""
        if item_id in self.items:
            if self.items[item_id] <= quantity:
                del self.items[item_id]
            else:
                self.items[item_id] -= quantity
            return True
        return False

# Characters
class Character(GameModel):
    name: str
    description: str
    inventory: Inventory = Field(default_factory=Inventory)
    location_id: Optional[str] = None

class Player(Character):
    pass

class NPC(Character):
    dialogue_history: List[str] = Field(default_factory=list)

# World structure
class Object(GameModel):
    name: str
    description: str
    properties: Dict[str, Any] = Field(default_factory=dict)

class Zone(GameModel):
    name: str
    description: str
    objects: Dict[str, Object] = Field(default_factory=dict)  # object_id -> Object
    npcs: Dict[str, NPC] = Field(default_factory=dict)  # npc_id -> NPC
    players: Dict[str, Player] = Field(default_factory=dict)  # player_id -> Player
    connected_zones: List[str] = Field(default_factory=list)  # List of zone_ids
    
    def add_object(self, obj: Object) -> None:
        """Add an object to the zone"""
        self.objects[obj.id] = obj
    
    def add_npc(self, npc: NPC) -> None:
        """Add an NPC to the zone"""
        self.npcs[npc.id] = npc
        npc.location_id = self.id
    
    def add_player(self, player: Player) -> None:
        """Add a player to the zone"""
        self.players[player.id] = player
        player.location_id = self.id
    
    def remove_player(self, player_id: str) -> bool:
        """Remove a player from the zone"""
        if player_id in self.players:
            del self.players[player_id]
            return True
        return False

class World(GameModel):
    name: str
    description: str
    zones: Dict[str, Zone] = Field(default_factory=dict)  # zone_id -> Zone
    items: Dict[str, Item] = Field(default_factory=dict)  # item_id -> Item
    
    def add_zone(self, zone: Zone) -> None:
        """Add a zone to the world"""
        self.zones[zone.id] = zone
    
    def add_item(self, item: Item) -> None:
        """Add an item to the world's item registry"""
        self.items[item.id] = item
    
    def connect_zones(self, zone_id1: str, zone_id2: str) -> bool:
        """Create a bidirectional connection between two zones"""
        if zone_id1 not in self.zones or zone_id2 not in self.zones:
            return False
        
        if zone_id2 not in self.zones[zone_id1].connected_zones:
            self.zones[zone_id1].connected_zones.append(zone_id2)
        
        if zone_id1 not in self.zones[zone_id2].connected_zones:
            self.zones[zone_id2].connected_zones.append(zone_id1)
        
        return True
    
    def get_zone_for_player(self, player_id: str) -> Optional[Zone]:
        """Find which zone a player is in"""
        for zone in self.zones.values():
            if player_id in zone.players:
                return zone
        return None
    
    def move_player(self, player_id: str, from_zone_id: str, to_zone_id: str) -> bool:
        """Move a player from one zone to another"""
        if from_zone_id not in self.zones or to_zone_id not in self.zones:
            return False
        
        from_zone = self.zones[from_zone_id]
        to_zone = self.zones[to_zone_id]
        
        if player_id not in from_zone.players:
            return False
        
        if to_zone_id not in from_zone.connected_zones:
            return False
        
        player = from_zone.players[player_id]
        from_zone.remove_player(player_id)
        to_zone.add_player(player)
        
        return True
    
    def get_item(self, item_id: str) -> Optional[Item]:
        """Get an item from the world's item registry"""
        return self.items.get(item_id)

# Events
class EventType(str, Enum):
    MESSAGE = "message"
    MOVEMENT = "movement"
    DIALOGUE = "dialogue"
    INTERACTION = "interaction"

class Event(GameModel):
    type: EventType
    content: str
    source_id: Optional[str] = None
    target_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)