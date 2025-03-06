import asyncio
from enum import Enum
from typing import List, Optional, Tuple, Union
from pydantic import BaseModel
from rich.console import Console
from pydantic_ai import Agent, RunContext
from dotenv import load_dotenv

load_dotenv()

console = Console()

# ---------------------------
# Create a common base model that allows arbitrary types
# ---------------------------
class GameModel(BaseModel):
    class Config:
        arbitrary_types_allowed = True

# ---------------------------
# Models for Items and Inventory
# ---------------------------
class Item(GameModel):
    id: int
    name: str
    description: str

class Inventory(GameModel):
    id: int
    items: List[Tuple[Item, int]] = []

# ---------------------------
# Models for Player and NPC
# ---------------------------
class Player(GameModel):
    id: int
    name: str
    description: str
    inventory: Inventory

class NPC(GameModel):
    id: int
    name: str
    description: str
    inventory: Inventory

# ---------------------------
# Model for Objects
# ---------------------------
class Object(GameModel):
    id: int
    name: str
    description: str

# ---------------------------
# Models for Zones and World
# ---------------------------
class Zone(GameModel):
    id: int
    name: str
    description: str
    parent_zone: Optional['Zone'] = None
    sub_zones: Optional[List['Zone']] = None
    objects: List[Object] = []
    npcs: List[NPC] = []
    players: List[Player] = []

class World(GameModel):
    id: int
    name: str
    description: str
    zones: List[Zone] = []

# ---------------------------
# Models for Events
# ---------------------------
class EventType(str, Enum):
    CHECK_INVENTORY = "check_inventory"
    INTERACT = "interact"
    TRADE = "trade"
    COMBAT = "combat"
    USE = "use"
    MESSAGE = "message"
    ATTACK = "attack"
    DEFEND = "defend"

class Event(GameModel):
    id: int
    type: EventType
    content: str

class Game(GameModel):
    world_state: World
    events: Optional[List[Event]]

# ---------------------------
# Creating Items (defined separately for reuse)
# ---------------------------
sword = Item(id=1, name="Ancient Sword", description="A rusted sword with magical engravings.")
potion = Item(id=2, name="Healing Potion", description="Restores a small amount of health.")

# ---------------------------
# Instantiating the Player (with inline inventory and AI agent)
# ---------------------------
player = Player(
    id=1,
    name="Alden the Brave",
    description="A wandering warrior seeking adventure.",
    inventory=Inventory(id=1, items=[(sword, 1), (potion, 5)])
)

player_agent = Agent(
    "openai:gpt-4o-mini",
    result_type=Event,
    system_prompt="""
Use check_inventory if the player wants to check their inventory.
"""
)

# ---------------------------
# Instantiating NPCs with inline inventory and AI agents
# ---------------------------
eldrin_the_merchant = NPC(
    id=1,
    name="Eldrin the Merchant",
    description="A mysterious trader with exotic wares.",
    inventory=Inventory(id=2, items=[(potion, 25)])
)

eldrin_the_merchant_agent = Agent(
    "openai:gpt-4o-mini",
    result_type=Event,
    system_prompt="""
You are Eldrin the Merchant, a mysterious trader with exotic wares.
You can trade items with the player.
If the player asks to buy or sell an item, use:
- list_items() to show your available stock
- buy_item(item_name) when they want to purchase
- sell_item(item_name) when they want to sell an item
Do NOT respond with messages; only call the tools.
"""
)

vorrak_the_cursed = NPC(
    id=2,
    name="Vorrak the Cursed",
    description="A fallen warlord twisted by dark magic.",
    inventory=Inventory(id=3, items=[(potion, 3), (sword, 1)])
)

vorrak_the_cursed_agent = Agent(
    "openai:gpt-4o-mini",
    result_type=Event,
    system_prompt="""
You are Vorrak the Cursed, a fallen warlord twisted by dark magic.
You guard forbidden secrets and are always ready to engage in combat or intimidate challengers.
When the player confronts you, choose from these tools:
- attack() : to simulate a combat strike
- taunt() : to hurl a menacing remark
- defend() : to respond when the player parries or defends
Do NOT send plain messages; only call the tools.
"""
)

# ---------------------------
# Instantiating Objects with inline AI agents
# ---------------------------
ancient_statue = Object(
    id=1,
    name="Ancient Statue",
    description="A weathered stone figure of a forgotten deity."
)

ancient_statue_agent = Agent(
    "openai:gpt-4o-mini",
    result_type=Event,
    system_prompt="""
You are the spirit of the Ancient Statue.
When the player interacts with you, use the tool:
- examine_statue() : to reveal its mysterious past and divine presence.
Do NOT respond with plain messages; only call the tools.
"""
)

@ancient_statue.agent.tool
def examine_statue(ctx: RunContext[str]) -> Event:
    return Event(
        id=101,
        type=EventType.INTERACT,
        content="You examine the ancient statue. Its weathered features and mysterious engravings hint at a long-forgotten deity watching over the land."
    )

enchanted_altar = Object(
    id=2,
    name="Enchanted Altar",
    description="A glowing altar with unknown runes."
)

enchanted_altar_agent = Agent(
    "openai:gpt-4o-mini",
    result_type=Event,
    system_prompt="""
You are the spirit of the Enchanted Altar.
When the player interacts with you, use the tool:
- use_altar() : to activate your mystical healing power.
Do NOT respond with plain messages; only call the tools.
"""
)

@enchanted_altar.agent.tool
def use_altar(ctx: RunContext[str]) -> Event:
    return Event(
        id=102,
        type=EventType.USE,
        content="You press your hand against the enchanted altar. A surge of healing warmth fills you as mystical runes glow beneath your touch."
    )

mystic_portal = Object(
    id=3,
    name="Mystic Portal",
    description="A shimmering gateway linking two distant lands."
)

mystic_portal_agent = Agent(
    "openai:gpt-4o-mini",
    result_type=Event,
    system_prompt="""
You are the essence of the Mystic Portal.
When the player interacts with you, use the tool:
- enter_portal() : to transport the player to another realm.
Do NOT respond with plain messages; only call the tools.
"""
)

@mystic_portal_agent.tool
def enter_portal(ctx: RunContext[str]) -> Event:
    return Event(
        id=103,
        type=EventType.INTERACT,
        content="You step into the mystic portal. In an instant, the world around you dissolves into a swirl of colors as you are transported to a distant realm."
    )

ancient_dungeon_gate = Object(
    id=4,
    name="Ancient Dungeon Gate",
    description="A heavy stone gate, requiring a key to open."
)

ancient_dungeon_gate_agent = Agent(
    "openai:gpt-4o-mini",
    result_type=Event,
    system_prompt="""
You are the guardian spirit of the Ancient Dungeon Gate.
When the player interacts with you, use the tool:
- open_gate() : to indicate that a special key or clue is required.
Do NOT respond with plain messages; only call the tools.
"""
)

@ancient_dungeon_gate_agent.tool
def open_gate(ctx: RunContext[str]) -> Event:
    return Event(
        id=104,
        type=EventType.INTERACT,
        content="You approach the ancient dungeon gate. Its heavy stone and mysterious lock suggest that only a special key or clue can grant you access."
    )

# ---------------------------
# Defining Zones inline with their objects, NPCs, and players
# ---------------------------
deep_woods = Zone(
    id=4,
    name="Deep Woods",
    description="A dark, eerie part of the Mystic Forest.",
    objects=[enchanted_altar, mystic_portal]
)

deep_woods_agent = Agent(
    "openai:gpt-4o-mini",
    result_type=Event
)

mystic_forest = Zone(
    id=1,
    name="Mystic Forest",
    description="A dense forest filled with magical creatures.",
    objects=[ancient_statue],
    sub_zones=[deep_woods]
)

mystic_forest_agent = Agent(
    "openai:gpt-4o-mini",
    result_type=Event
)

silverwood_town = Zone(
    id=2,
    name="Silverwood Town",
    description="A small town bustling with traders and adventurers.",
    npcs=[eldrin_the_merchant],
    players=[player]
)

mystic_forest_agent = Agent(
    "openai:gpt-4o-mini",
    result_type=Event
)

chamber_of_secrets = Zone(
    id=5,
    name="Chamber of Secrets",
    description="A hidden chamber deep in the dungeon.",
    npcs=[vorrak_the_cursed]
)

chamber_of_secrets_agent = Agent(
    "openai:gpt-4o-mini",
    result_type=Event
)

forgotten_ruins = Zone(
    id=3,
    name="Forgotten Ruins",
    description="An abandoned dungeon filled with secrets and dangers.",
    objects=[ancient_dungeon_gate],
    sub_zones=[chamber_of_secrets]
)

forgotten_ruins_agent = Agent(
    "openai:gpt-4o-mini",
    result_type=Event
)

# ---------------------------
# Defining the World with inline zones
# ---------------------------
eldoria = World(
    id=1,
    name="Eldoria",
    description="A land of magic, mystery, and adventure.",
    zones=[mystic_forest, silverwood_town, forgotten_ruins]
)

eldoria_agent = Agent(
    "openai:gpt-4o-mini",
    result_type=Event
)

console.print(eldoria)

# ---------------------------
# Defining Player AI tools (attached to player's agent)
# ---------------------------
@player_agent.tool_plain
def get_current_zone():
    pass

@player_agent.tool_plain
def check_inventory():
    return player.inventory.items

@player_agent.tool
async def trade_with_merchant(ctx: RunContext[str], input_text: str) -> Event:
    """
    Forwards the player's trade request to Eldrin the Merchant's agent.
    """
    return await eldrin_the_merchant.agent.run(input_text)

@player_agent.tool
async def interact_with_object(ctx: RunContext[str], object_name: str) -> Event:
    """
    Forwards the player's interaction command to the appropriate object's agent.
    Valid options: "statue", "altar", "portal", "gate".
    """
    object_name = object_name.lower().strip()
    if object_name == "statue":
        return await ancient_statue.agent.run("examine_statue")
    elif object_name == "altar":
        return await enchanted_altar.agent.run("use_altar")
    elif object_name == "portal":
        return await mystic_portal.agent.run("enter_portal")
    elif object_name == "gate":
        return await ancient_dungeon_gate.agent.run("open_gate")
    else:
        return Event(
            id=999,
            type=EventType.MESSAGE,
            content=f"Unknown object: {object_name}. Try statue, altar, portal, or gate."
        )

@player_agent.tool
async def confront_boss(ctx: RunContext[str], input_text: str) -> Event:
    return await vorrak_the_cursed.agent.run(input_text)

async def handle_player_input(input_text: str):
    response = await player.agent.run(input_text)
    return response.data

async def main():
    while True:
        x = input(": ")
        event = await handle_player_input(x)
        print(event)

asyncio.run(main())
