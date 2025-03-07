"""
Refactored base models for the Agentique Game Engine.
"""
from enum import Enum
from typing import Dict, List, Optional, Any, Literal, Set
from pydantic import BaseModel, Field
from uuid import uuid4
from datetime import datetime

# Item and Inventory
class Item(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4())[:8])
    name: str
    description: str
    properties: Dict[str, Any] = Field(default_factory=dict)
    
    def __eq__(self, other):
        if not isinstance(other, Item):
            return False
        return self.id == other.id
    
    def __hash__(self):
        return hash(self.id)

class Inventory(BaseModel):
    items: Dict[str, int] = Field(default_factory=dict)  # item_id -> quantity
    owner_id: Optional[str] = None
    
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
    
    def has_item(self, item_id: str, quantity: int = 1) -> bool:
        """Check if the inventory has enough of a specific item"""
        return item_id in self.items and self.items[item_id] >= quantity
    
    def get_item_count(self, item_id: str) -> int:
        """Get the quantity of a specific item"""
        return self.items.get(item_id, 0)
    
    def clear(self) -> None:
        """Clear all items from the inventory"""
        self.items.clear()

# Controller types for entities
ControllerType = Literal["AI", "PLAYER", "SYSTEM", "NONE"]

# Character (unified Player and NPC)
class Character(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4())[:8])
    name: str
    description: str
    inventory: Inventory = Field(default_factory=Inventory)
    location_id: Optional[str] = None
    controller_type: ControllerType = "AI"
    dialogue_history: List[Dict[str, str]] = Field(default_factory=list)
    properties: Dict[str, Any] = Field(default_factory=dict)
    
    def __init__(self, **data):
        super().__init__(**data)
        if self.inventory.owner_id is None:
            self.inventory.owner_id = self.id
    
    def add_dialogue(self, speaker_id: str, content: str) -> None:
        """Add a dialogue entry to the character's history"""
        self.dialogue_history.append({
            "speaker_id": speaker_id,
            "content": content,
            "timestamp": datetime.now().isoformat()
        })
    
    def get_recent_dialogue(self, limit: int = 10) -> List[Dict[str, str]]:
        """Get the most recent dialogue entries"""
        return self.dialogue_history[-limit:] if self.dialogue_history else []
    
    def is_player_controlled(self) -> bool:
        """Check if this character is player-controlled"""
        return self.controller_type == "PLAYER"
    
    def set_controller(self, controller_type: ControllerType) -> None:
        """Change the controller of this character"""
        self.controller_type = controller_type
    
    def serialize(self) -> Dict[str, Any]:
        """Convert character to a dictionary for storage"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "inventory": self.inventory.items,
            "location_id": self.location_id,
            "controller_type": self.controller_type,
            "properties": self.properties
        }

# Object
class Object(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4())[:8])
    name: str
    description: str
    properties: Dict[str, Any] = Field(default_factory=dict)
    interaction_history: List[Dict[str, str]] = Field(default_factory=list)
    
    def record_interaction(self, character_id: str, action: str) -> None:
        """Record an interaction with this object"""
        self.interaction_history.append({
            "character_id": character_id,
            "action": action,
            "timestamp": datetime.now().isoformat()
        })
    
    def get_recent_interactions(self, limit: int = 5) -> List[Dict[str, str]]:
        """Get the most recent interactions"""
        return self.interaction_history[-limit:] if self.interaction_history else []

# Zone
class Zone(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4())[:8])
    name: str
    description: str
    objects: Dict[str, Object] = Field(default_factory=dict)  # object_id -> Object
    characters: Dict[str, Character] = Field(default_factory=dict)  # character_id -> Character
    connected_zones: List[str] = Field(default_factory=list)  # List of zone_ids
    properties: Dict[str, Any] = Field(default_factory=dict)
    
    def add_object(self, obj: Object) -> None:
        """Add an object to the zone"""
        self.objects[obj.id] = obj
    
    def remove_object(self, object_id: str) -> bool:
        """Remove an object from the zone"""
        if object_id in self.objects:
            del self.objects[object_id]
            return True
        return False
    
    def add_character(self, character: Character) -> None:
        """Add a character to the zone"""
        self.characters[character.id] = character
        character.location_id = self.id
    
    def remove_character(self, character_id: str) -> bool:
        """Remove a character from the zone"""
        if character_id in self.characters:
            del self.characters[character_id]
            return True
        return False
    
    def get_player_characters(self) -> List[Character]:
        """Get all player-controlled characters in this zone"""
        return [char for char in self.characters.values() if char.is_player_controlled()]
    
    def get_ai_characters(self) -> List[Character]:
        """Get all AI-controlled characters in this zone"""
        return [char for char in self.characters.values() if char.controller_type == "AI"]
    
    def describe(self) -> str:
        """Get a full description of the zone"""
        objects_desc = ", ".join([obj.name for obj in self.objects.values()]) if self.objects else "nothing notable"
        characters_desc = ", ".join([char.name for char in self.characters.values()]) if self.characters else "no one"
        
        return f"""
        {self.name}
        {self.description}
        
        You can see: {objects_desc}
        Present here: {characters_desc}
        """
    
    def has_connection_to(self, zone_id: str) -> bool:
        """Check if this zone has a connection to another zone"""
        return zone_id in self.connected_zones

# World
class World(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4())[:8])
    name: str
    description: str
    zones: Dict[str, Zone] = Field(default_factory=dict)  # zone_id -> Zone
    items: Dict[str, Item] = Field(default_factory=dict)  # item_id -> Item
    global_time: float = 0.0  # Time in arbitrary units for world simulation
    properties: Dict[str, Any] = Field(default_factory=dict)
    
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
    
    def disconnect_zones(self, zone_id1: str, zone_id2: str) -> bool:
        """Remove a connection between two zones"""
        if zone_id1 not in self.zones or zone_id2 not in self.zones:
            return False
        
        if zone_id2 in self.zones[zone_id1].connected_zones:
            self.zones[zone_id1].connected_zones.remove(zone_id2)
        
        if zone_id1 in self.zones[zone_id2].connected_zones:
            self.zones[zone_id2].connected_zones.remove(zone_id1)
        
        return True
    
    def get_character_location(self, character_id: str) -> Optional[Zone]:
        """Find which zone a character is in"""
        for zone in self.zones.values():
            if character_id in zone.characters:
                return zone
        return None
    
    def move_character(self, character_id: str, from_zone_id: str, to_zone_id: str) -> bool:
        """Move a character from one zone to another"""
        if from_zone_id not in self.zones or to_zone_id not in self.zones:
            return False
        
        from_zone = self.zones[from_zone_id]
        to_zone = self.zones[to_zone_id]
        
        if character_id not in from_zone.characters:
            return False
        
        if to_zone_id not in from_zone.connected_zones:
            return False
        
        character = from_zone.characters[character_id]
        from_zone.remove_character(character_id)
        to_zone.add_character(character)
        
        return True
    
    def get_item(self, item_id: str) -> Optional[Item]:
        """Get an item from the world's item registry"""
        return self.items.get(item_id)
    
    def get_all_characters(self) -> List[Character]:
        """Get all characters in the world"""
        characters = []
        for zone in self.zones.values():
            characters.extend(zone.characters.values())
        return characters
    
    def get_character_by_id(self, character_id: str) -> Optional[Character]:
        """Find a character by ID"""
        for zone in self.zones.values():
            if character_id in zone.characters:
                return zone.characters[character_id]
        return None
    
    def advance_time(self, time_units: float = 1.0) -> None:
        """Advance the global time of the world"""
        self.global_time += time_units

# Event system
class EventType(str, Enum):
    MESSAGE = "message"
    MOVEMENT = "movement"
    DIALOGUE = "dialogue"
    INTERACTION = "interaction"
    ITEM_TRANSFER = "item_transfer"
    WORLD_STATE = "world_state"
    SYSTEM = "system"
    TICK = "tick"

class Event(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4())[:8])
    type: EventType
    content: str
    source_id: Optional[str] = None
    target_id: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict[str, Any] = Field(default_factory=dict)