"""
Simplified models for character conversations.
"""
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple, Union
from pydantic import BaseModel, Field
from uuid import uuid4
from datetime import datetime

class Item(BaseModel):
    """Simple item model"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    description: str
    value: int = 0
    
    def __eq__(self, other):
        if not isinstance(other, Item):
            return False
        return self.id == other.id
        
    def __hash__(self):
        return hash(self.id)
    
class Inventory(BaseModel):
    """Inventory tracking items and quantities"""
    items: List[Tuple[Item, int]] = Field(default_factory=list)

    def add_item(self, item: Item, quantity: int = 1) -> None:
        """Add an item to the inventory"""
        for i, (existing_item, existing_quantity) in enumerate(self.items):
            if existing_item.id == item.id:
                self.items[i] = (existing_item, existing_quantity + quantity)
                return
        
        # Item not found, add it
        self.items.append((item, quantity))
    
    def remove_item(self, item: Item, quantity: int = 1) -> bool:
        """Remove an item from the inventory"""
        for i, (existing_item, existing_quantity) in enumerate(self.items):
            if existing_item.id == item.id:
                if existing_quantity <= quantity:
                    # Remove the item entirely
                    self.items.pop(i)
                else:
                    # Reduce the quantity
                    self.items[i] = (existing_item, existing_quantity - quantity)
                return True
        
        return False
    
    def has_item(self, item_id: str, quantity: int = 1) -> bool:
        """Check if inventory has enough of an item"""
        for item, item_quantity in self.items:
            if item.id == item_id and item_quantity >= quantity:
                return True
        return False
    
    def get_item_count(self, item_id: str) -> int:
        """Get quantity of an item"""
        for item, quantity in self.items:
            if item.id == item_id:
                return quantity
        return 0
    
    def get_items_string(self) -> str:
        """Get a readable representation of inventory contents"""
        if not self.items:
            return "nothing"
        
        return ", ".join([f"{item.name} ({quantity})" for item, quantity in self.items])
    
class Character(BaseModel):
    """Simple character with just the essential information"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    description: str
    inventory: Inventory = Field(default_factory=Inventory)

class TradeStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"

class Trade(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    source: Character
    target: Character
    offered_items: Inventory = Field(default_factory=Inventory)
    requested_items: Inventory = Field(default_factory=Inventory)
    status: TradeStatus = TradeStatus.PENDING
    timestamp: datetime = Field(default_factory=datetime.now)

class Message(BaseModel):
    source: Character
    target: Optional[Character]
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)

class EventType(str, Enum):
    MESSAGE = "message"
    TRADE = "trade"

class Event(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    type: EventType
    content: Union[Message, Trade]
    timestamp: datetime = Field(default_factory=datetime.now)

class EventHandler:
    def __init__(self):
        pass

    def handle_event(self, event: Event):
        if (event.type == EventType.MESSAGE) and isinstance(event.content, Message):
            message = event.content
            self.handle_message(message)
        elif event.type == EventType.TRADE and isinstance(event.content, Trade):
            trade = event.content
            self.handle_trade(trade)
        else:
            return
        
    def handle_message(self, event: Event):
        pass

    def handle_trade(self, event: Event):
        pass

class GameState(BaseModel):
    """Tracks the current state of the Game"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    characters: List[Character] = Field(default_factory=list)
    items: List[Item] = Field(default_factory=list)
    events: List[Event] = Field(default_factory=list)

    def add_character(self, character: Character):
        self.characters.append(character)

    def remove_character(self, character: Character):
        self.characters.remove(character)

    def add_item(self, item: Item):
        self.items.append(item)

    def remove_item(self, item: Item):
        self.items.remove(item)

    def add_event(self, event: Event):
        self.events.append(event)

    def remove_event(self, event: Event):
        self.events.remove(event)

    # characters: Dict[str, Character] = Field(default_factory=dict)  # character_id -> Character
    # messages: List[Dict] = Field(default_factory=list)  # List of message dicts
    
    def add_message(self, character_id: str, content: str) -> None:
        """Add a message to the conversation"""
        character = self.characters.get(character_id)
        if not character:
            raise ValueError(f"Character {character_id} not found in conversation")
        
        message = {
            "character_id": character_id,
            "character_name": character.name,
            "content": content,
            "timestamp": datetime.now().isoformat()
        }
        
        self.messages.append(message)
    
    def get_conversation_history(self, limit: int = 10) -> str:
        """Get formatted conversation history"""
        recent_messages = self.messages[-limit:] if len(self.messages) > limit else self.messages
        
        if not recent_messages:
            return "The conversation has not started yet."
        
        history = ""
        for msg in recent_messages:
            history += f"{msg['character_name']}: {msg['content']}\n\n"
        
        return history.strip()
    

