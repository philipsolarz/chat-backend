import asyncio
from datetime import datetime
from enum import Enum
import hashlib
from typing import List, Optional, Tuple, Union
from uuid import uuid4
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from rich.console import Console
from rich.panel import Panel
import logging

# Set up logging configuration
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

load_dotenv()
console = Console()

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
        try:
            for i, (existing_item, existing_quantity) in enumerate(self.items):
                if existing_item.id == item.id:
                    self.items[i] = (existing_item, existing_quantity + quantity)
                    return
        
            # Item not found, add it
            self.items.append((item, quantity))
        except Exception as e:
            logger.error("Error in add_item: %s", e)
            raise

    def remove_item(self, item: Item, quantity: int = 1) -> bool:
        """Remove an item from the inventory"""
        try:
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
        except Exception as e:
            logger.error("Error in remove_item: %s", e)
            raise

    def has_item(self, item_id: str, quantity: int = 1) -> bool:
        """Check if inventory has enough of an item"""
        try:
            for item, item_quantity in self.items:
                if item.id == item_id and item_quantity >= quantity:
                    return True
            return False
        except Exception as e:
            logger.error("Error in has_item: %s", e)
            raise

    def get_item_count(self, item_id: str) -> int:
        """Get quantity of an item"""
        try:
            for item, quantity in self.items:
                if item.id == item_id:
                    return quantity
            return 0
        except Exception as e:
            logger.error("Error in get_item_count: %s", e)
            raise

    def get_items_string(self) -> str:
        """Get a readable representation of inventory contents"""
        try:
            if not self.items:
                return "nothing"
        
            return ", ".join([f"{item.name} ({quantity})" for item, quantity in self.items])
        except Exception as e:
            logger.error("Error in get_items_string: %s", e)
            raise
    
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

    def is_valid(self) -> Tuple[bool, str]:
        """Checks if the trade can be executed (both parties have required items)."""
        # Validate if source has all offered items
        for item, quantity in self.offered_items.items:
            if not self.source.inventory.has_item(item.id, quantity):
                return False, "Source lacks offered items"

        # Validate if target has all requested items (if applicable)
        for item, quantity in self.requested_items.items:
            if not self.target.inventory.has_item(item.id, quantity):
                return False, "Target lacks requested items"

        return True, ""

    def execute(self) -> bool:
        """Executes the trade by transferring items between inventories."""
        valid, _ = self.is_valid()
        if not valid:
            return False

        # Transfer offered items from source to target
        for item, quantity in self.offered_items.items:
            self.source.inventory.remove_item(item, quantity)
            self.target.inventory.add_item(item, quantity)

        # Transfer requested items from target to source
        for item, quantity in self.requested_items.items:
            self.target.inventory.remove_item(item, quantity)
            self.source.inventory.add_item(item, quantity)

        self.status = TradeStatus.ACCEPTED
        return True
    
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
        try:
            if (event.type == EventType.MESSAGE) and isinstance(event.content, Message):
                message = event.content
                self.handle_message(message)
            elif event.type == EventType.TRADE and isinstance(event.content, Trade):
                trade = event.content
                self.handle_trade(trade)
            else:
                return
        except Exception as e:
            logger.error("Error in handle_event: %s", e)

    def handle_message(self, message: Message):
        try:
            color = f"#{hashlib.md5(message.source.name.encode()).hexdigest()[:6]}"

            panel = Panel(
                f"[white]{message.content}[/white]",
                title=f"[bold {color}]{message.source.name}[/bold {color}]",
                border_style=color
            )

            console.print(panel)
        except Exception as e:
            logger.error("Error in handle_message: %s", e)

    def handle_trade(self, trade: Trade):
        try:
            valid, reason = trade.is_valid()

            if not valid:
                trade.status = TradeStatus.REJECTED
                self.display_trade(trade, reason=reason)
                return

            # Execute trade
            trade.execute()

            # Display the trade
            source_color = f"#{hashlib.md5(trade.source.name.encode()).hexdigest()[:6]}"
            target_color = f"#{hashlib.md5(trade.target.name.encode()).hexdigest()[:6]}"

            offered_items = trade.offered_items.get_items_string()
            requested_items = trade.requested_items.get_items_string()

            trade_text = (
                f"[bold {source_color}]{trade.source.name}[/bold {source_color}] "
                f": [green]{offered_items}[/green]\n"
                f"[bold {target_color}]{trade.target.name}[/bold {target_color}] "
                f": [red]{requested_items}[/red]\n"
                f"Status: [bold]{trade.status.value}[/bold]"
            )

            panel = Panel(
                trade_text,
                title=f"[bold {source_color}]{trade.source.name}[/bold {source_color}] <=> "
                    f"[bold {target_color}]{trade.target.name}[/bold {target_color}]",
                border_style=source_color
            )

            console.print(panel)
        except Exception as e:
            logger.error("Error in handle_trade: %s", e)

class GameState(BaseModel):
    items: List[Item] = Field(default_factory=list)
    characters: List[Character] = Field(default_factory=list)
    events: List[Event] = Field(default_factory=list)

    def get_character_by_name(self, name: str) -> Character:
        for character in self.characters:
            if character.name.lower() == name.lower():
                return character
        logger.error("Character with name '%s' not found", name)
        raise ValueError(f"Character with name '{name}' not found")

    def get_item_by_name(self, name: str) -> Item:
        for item in self.items:
            if item.name.lower() == name.lower():
                return item
        logger.error("Item with name '%s' not found", name)
        raise ValueError(f"Item with name '{name}' not found")


class GameMaster:
    def __init__(self, state: GameState):
        self.state = state
        
        system_prompt = """
        Your task is to interpret the input into a structured response in the form of an Event.

        You may make use of the tools get_character_by_name(name: str) and get_item_by_name(name: str)
        to get all the information you need about a character or an item.

        """
        # In the case that the input is perceived as an event of any other type than message, but the
        # rest of the information is lacking, then you may make use of the tool get_more_context()
        # to request more context from the character that sent the initial input.

        self.agent = Agent(
            "openai:gpt-4o-mini",
            result_type=Event,
            system_prompt=system_prompt
        )

        @self.agent.tool_plain
        def get_character_by_name(name: str) -> Character:
            return self.state.get_character_by_name(name)

        @self.agent.tool_plain
        def get_item_by_name(name: str) -> Item:
            return self.state.get_item_by_name(name)

        # @self.agent.tool_plain
        # def get_more_context(instructions: str) -> str:
        #     response = await 
        #     pass
    
    async def interpret(self, message: str):
        try:
            event = await self.agent.run(message)
            return event
        except Exception as e:
            logger.error("Error in GameMaster.interpret: %s", e)
            raise

class CharacterAgent:
    """Agent that controls a character in conversations"""
    
    def __init__(self, character: Character):
        self.character = character

        system_prompt = f"""
        You are roleplaying as {character.name}.
        
        {character.description}
        
        Always stay in character and respond as {character.name} would.
        Keep responses conversational and concise (1-3 sentences).
        
        Respond with just the dialogue - no quotation marks or narration.

        You may use the function get_inventory() to get your characters inventory, i.e. list of tupled items with quantity.

        You may use the function request_trade(target: Character, offered_items: Inventory, requested_items: Inventory) to request a trade.
        """
        
        # Create the AI agent
        self.agent = Agent(
            "openai:gpt-4o-mini",
            result_type=str,
            system_prompt=system_prompt
        )

        @self.agent.tool_plain
        def get_inventory() -> Inventory:
            return self.character.inventory
        
        @self.agent.tool_plain
        # def request_trade(target: Character, offered_items: Inventory, requested_items: Inventory) -> Trade:
        def request_trade(target_character_name: str, offered_item_name: str, requested_item_name: str) -> str:
            return f"Trade Request: Source: {self.character.name} Offered item: [{offered_item_name}] <-> Target: {target_character_name} Requested item: [{requested_item_name}]"
            # return Trade(
            #     source=self.character,
            #     target=self.state.get_character_by_name(target_character_name),
            #     offered_items=Inventory([(self.state.get_item_by_name("offered_item_name"), 1)]),
            #     requested_items=Inventory([(self.state.get_item_by_name(requested_item_name), 1)]),
            # )


    async def generate(self, 
                       context: str, 
                    #    message_history: list[ModelMessage]
    ) -> str:
        try:
            response = await self.agent.run(
                context, 
                # message_history=message_history
            )
            return response
        except Exception as e:
            logger.error("Error in CharacterAgent.generate: %s", e)
            raise

class Game:
    def __init__(self, state: GameState, agents: List[CharacterAgent]):
        self.state = state
        self.agents = agents

        self.game_master = GameMaster(state)
        self.event_handler = EventHandler()

    # def __init__(self, items: List[Item], characters: List[Character], agents: List[CharacterAgent]):
    #     self.items = items
    #     self.characters = characters
    #     self.agents = agents

    #     self.events = []

    #     self.game_master = GameMaster()
    #     self.event_handler = EventHandler()

    def tmp_context_from_event_history(self, limit: int = 10) -> str:
        recent_events = self.state.events[-limit:] if len(self.state.events) > limit else self.state.events
        if not recent_events:
            return ""
        
        lines = []
        for event in recent_events:
            if isinstance(event.content, Message):
                target_name = event.content.target.name if event.content.target else "All"
                lines.append(f"[{event.timestamp:%Y-%m-%d %H:%M}] {event.content.source.name} -> {target_name}: {event.content.content}")
            elif isinstance(event.content, Trade):
                lines.append(f"[{event.timestamp:%Y-%m-%d %H:%M}] Trade from {event.content.source.name} to {event.content.target.name} (Status: {event.content.status.value})")
            else:
                lines.append(str(event))
        
        return "\n".join(lines)

    async def run(self):
        while True:
            # for character in self.characters:
            for agent in self.agents:
                try:
                    ctx = self.tmp_context_from_event_history() # This is temporary way of getting context
                    response = await agent.generate(ctx)
                    console.print(f"DEBUG: {response.data}")
                    # create and call some method self._handle_raw_response until then we just use response.data in the below
                    event = await self.game_master.interpret(response.data)
                    # same here call self._handle_raw_response until then
                    event_data: Event = event.data
                    # self.event_handler.handle_event(event)
                    self.event_handler.handle_event(event_data)
                    self.state.events.append(event)
                except Exception as e:
                    logger.error("Error during game loop: %s", e)
                await asyncio.sleep(10)

async def main():
    console.print(Panel.fit(
        "[bold magenta]Welcome to Fantasia[/bold magenta]",
        border_style="magenta"
    ))
    sword = Item(name="Sword", description="A finely crafted blade", value=100)
    potion = Item(name="Health Potion", description="Restores health", value=50)
    gold_coin = Item(name="Gold Coin", description="Currency", value=1)

    thorin = Character(
        name="Thorin Ironhammer",
        description="""
        A stocky dwarven blacksmith with a thick braided beard. Thorin is gruff and direct, 
        valuing hard work and craftsmanship above all else. He's suspicious of magic and speaks 
        in short, sometimes abrupt sentences. He often refers to "the old days" and his ancestors' 
        achievements. He comes from a long line of master smiths and now runs the local forge, 
        known for crafting the finest weapons in the region.
        """,
        inventory=Inventory(
            items=[
                (sword, 1),
                (potion, 5),
                (gold_coin, 100)
            ]
        )
    )

    thorin_agent = CharacterAgent(character=thorin)
    
    sylvia = Character(
        name="Sylvia Nightbloom",
        description="""
        A tall, slender elven herbalist with silver-streaked dark hair. Sylvia is eloquent and 
        thoughtful, often using flowery language and botanical metaphors. She's over 300 years old 
        and has spent centuries studying plants and remedies. She runs an apothecary shop in town 
        after leaving the Elven High Council, disillusioned with court politics. She's patient but 
        can be dismissive of those who disregard knowledge or nature.
        """,
        inventory=Inventory(
            items=[
                (gold_coin, 500)
            ]
        )
    )

    sylvia_agent = CharacterAgent(character=sylvia)

    console.print("[bold]Starting game...[/bold]\n")
    initial_state = GameState(
        items=[sword, potion, gold_coin],
        characters=[thorin, sylvia],
        events=[]
    )

    game = Game(
        state=initial_state,
        agents=[thorin_agent, sylvia_agent]
    )

    try:
        await game.run()
    except KeyboardInterrupt:
        console.print("\n[bold red]Game interrupted![/bold red]")
        logger.info("Game interrupted by user.")
    except Exception as e:
        console.print(f"\n[bold red]Error: {str(e)}[/bold red]")
        logger.error("Unhandled exception in main: %s", e)

    console.print("\n[bold]Game finished![/bold]")

if __name__ == "__main__":
    asyncio.run(main())
