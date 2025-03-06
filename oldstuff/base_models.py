from enum import Enum
from typing import Dict, List, Optional, Set, Tuple, Union, Any
from pydantic import BaseModel, Field
from uuid import UUID, uuid4
from datetime import datetime

# Base model with common functionality
class AgentiqueModel(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    created_at: datetime = Field(default_factory=datetime.now)
    
    class Config:
        arbitrary_types_allowed = True

# Item Models
class Item(AgentiqueModel):
    name: str
    description: str
    properties: Dict[str, Any] = Field(default_factory=dict)

class InventoryItem(AgentiqueModel):
    item: Item
    quantity: int = 1

class Inventory(AgentiqueModel):
    items: List[InventoryItem] = Field(default_factory=list)
    
    def add_item(self, item: Item, quantity: int = 1) -> None:
        """Add an item to the inventory"""
        # Check if item already exists
        for inv_item in self.items:
            if inv_item.item.id == item.id:
                inv_item.quantity += quantity
                return
        
        # Add new item
        self.items.append(InventoryItem(item=item, quantity=quantity))
    
    def remove_item(self, item_id: str, quantity: int = 1) -> bool:
        """Remove an item from the inventory"""
        for i, inv_item in enumerate(self.items):
            if inv_item.item.id == item_id:
                if inv_item.quantity <= quantity:
                    self.items.pop(i)
                else:
                    inv_item.quantity -= quantity
                return True
        return False
    
    def get_item(self, item_id: str) -> Optional[InventoryItem]:
        """Get an item from the inventory"""
        for inv_item in self.items:
            if inv_item.item.id == item_id:
                return inv_item
        return None

# Character Models
class Character(AgentiqueModel):
    name: str
    description: str
    inventory: Inventory = Field(default_factory=Inventory)
    attributes: Dict[str, Any] = Field(default_factory=dict)
    location_id: Optional[str] = None

class Player(Character):
    is_online: bool = True
    last_active: datetime = Field(default_factory=datetime.now)

class NPC(Character):
    dialogue_history: List[Dict[str, Any]] = Field(default_factory=list)
    behavior_traits: Dict[str, Any] = Field(default_factory=dict)

# World Structure Models
class Object(AgentiqueModel):
    name: str
    description: str
    properties: Dict[str, Any] = Field(default_factory=dict)
    can_interact: bool = True

class Zone(AgentiqueModel):
    name: str
    description: str
    parent_id: Optional[str] = None
    objects: List[Object] = Field(default_factory=list)
    npcs: List[NPC] = Field(default_factory=list)
    players: List[Player] = Field(default_factory=list)
    properties: Dict[str, Any] = Field(default_factory=dict)
    adjacent_zones: List[str] = Field(default_factory=list)  # IDs of connected zones
    
    def add_object(self, obj: Object) -> None:
        """Add an object to the zone"""
        self.objects.append(obj)
    
    def add_npc(self, npc: NPC) -> None:
        """Add an NPC to the zone"""
        self.npcs.append(npc)
        npc.location_id = self.id
    
    def add_player(self, player: Player) -> None:
        """Add a player to the zone"""
        self.players.append(player)
        player.location_id = self.id
    
    def remove_player(self, player_id: str) -> bool:
        """Remove a player from the zone"""
        for i, player in enumerate(self.players):
            if player.id == player_id:
                self.players.pop(i)
                return True
        return False
    
    def get_character(self, character_id: str) -> Optional[Union[Player, NPC]]:
        """Get a character (player or NPC) by ID"""
        for player in self.players:
            if player.id == character_id:
                return player
        
        for npc in self.npcs:
            if npc.id == character_id:
                return npc
        
        return None
    
    def get_object(self, object_id: str) -> Optional[Object]:
        """Get an object by ID"""
        for obj in self.objects:
            if obj.id == object_id:
                return obj
        
        return None

class World(AgentiqueModel):
    name: str
    description: str
    zones: Dict[str, Zone] = Field(default_factory=dict)
    global_properties: Dict[str, Any] = Field(default_factory=dict)
    
    def add_zone(self, zone: Zone) -> None:
        """Add a zone to the world"""
        self.zones[zone.id] = zone
    
    def get_zone(self, zone_id: str) -> Optional[Zone]:
        """Get a zone by ID"""
        return self.zones.get(zone_id)
    
    def connect_zones(self, zone_id1: str, zone_id2: str) -> bool:
        """Create a bidirectional connection between two zones"""
        zone1 = self.get_zone(zone_id1)
        zone2 = self.get_zone(zone_id2)
        
        if not zone1 or not zone2:
            return False
        
        if zone_id2 not in zone1.adjacent_zones:
            zone1.adjacent_zones.append(zone_id2)
        
        if zone_id1 not in zone2.adjacent_zones:
            zone2.adjacent_zones.append(zone_id1)
        
        return True
    
    def find_character(self, character_id: str) -> Tuple[Optional[Union[Player, NPC]], Optional[Zone]]:
        """Find a character in the world and return them along with their zone"""
        for zone_id, zone in self.zones.items():
            character = zone.get_character(character_id)
            if character:
                return character, zone
        
        return None, None
    
    def move_player(self, player_id: str, target_zone_id: str) -> bool:
        """Move a player from their current zone to a target zone"""
        player, current_zone = self.find_character(player_id)
        
        if not player or not isinstance(player, Player) or not current_zone:
            return False
        
        target_zone = self.get_zone(target_zone_id)
        if not target_zone:
            return False
        
        # Check if zones are connected
        if target_zone_id not in current_zone.adjacent_zones:
            return False
        
        # Remove from current zone and add to target zone
        current_zone.remove_player(player_id)
        target_zone.add_player(player)
        
        return True

# Event Models
class EventType(str, Enum):
    MESSAGE = "message"
    MOVEMENT = "movement"
    INTERACTION = "interaction"
    DIALOGUE = "dialogue"
    COMBAT = "combat"
    TRADE = "trade"
    ITEM_USE = "item_use"
    SYSTEM = "system"

class Event(AgentiqueModel):
    type: EventType
    source_id: str
    target_id: Optional[str] = None
    content: Any
    metadata: Dict[str, Any] = Field(default_factory=dict)

# Memory Models
class Memory(AgentiqueModel):
    owner_id: str
    content: str
    context: Dict[str, Any] = Field(default_factory=dict)
    importance: int = 1  # 1-10 scale
    related_ids: List[str] = Field(default_factory=list)
    
class MemoryStore:
    def __init__(self):
        self.memories: Dict[str, List[Memory]] = {}
    
    def add_memory(self, memory: Memory) -> None:
        """Add a memory to the store"""
        if memory.owner_id not in self.memories:
            self.memories[memory.owner_id] = []
        
        self.memories[memory.owner_id].append(memory)
    
    def get_memories(self, owner_id: str, limit: int = 10) -> List[Memory]:
        """Get memories for an entity, sorted by recency"""
        if owner_id not in self.memories:
            return []
        
        # Sort by recency (newest first)
        sorted_memories = sorted(
            self.memories[owner_id],
            key=lambda m: m.created_at,
            reverse=True
        )
        
        return sorted_memories[:limit]
    
    def get_memories_by_relevance(self, owner_id: str, context_ids: List[str], limit: int = 5) -> List[Memory]:
        """Get memories most relevant to a given context"""
        if owner_id not in self.memories:
            return []
        
        # Score memories by relevance to context IDs
        def relevance_score(memory: Memory) -> int:
            score = memory.importance
            for context_id in context_ids:
                if context_id in memory.related_ids:
                    score += 2
            return score
        
        sorted_memories = sorted(
            self.memories[owner_id],
            key=relevance_score,
            reverse=True
        )
        
        return sorted_memories[:limit]
    
    def clear_memories(self, owner_id: str) -> None:
        """Clear all memories for an entity"""
        if owner_id in self.memories:
            self.memories[owner_id] = []