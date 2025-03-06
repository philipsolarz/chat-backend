import asyncio
import os
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from base_models import (
    World, Zone, NPC, Player, Object, Item, Event, EventType,
    Memory, MemoryStore, Inventory, InventoryItem
)

from game_engine import GameEngine

# Load environment variables for API keys
load_dotenv()

# Setup console
console = Console()

async def create_fantasy_game() -> GameEngine:
    """Create a simple fantasy game world"""
    engine = GameEngine()
    
    # Create the world
    engine.create_world("Eldoria", "A land of magic, mystery, and adventure.")
    
    # Create zones
    town_square = Zone(
        id="town_square",
        name="Town Square",
        description="The bustling center of Silverwood Village. Merchants hawk their wares and villagers gather around the central fountain."
    )
    
    forest_edge = Zone(
        id="forest_edge",
        name="Forest Edge",
        description="The boundary between civilization and the wild. Tall trees loom ahead, their shadows deep and mysterious."
    )
    
    tavern = Zone(
        id="tavern",
        name="The Golden Goblet Tavern",
        description="A warm, inviting tavern filled with the sounds of laughter and music. The smell of hearty stew fills the air."
    )
    
    blacksmith = Zone(
        id="blacksmith", 
        name="Ironheart Forge",
        description="The heat from the forge is intense. Weapons and armor of various designs line the walls."
    )
    
    deep_forest = Zone(
        id="deep_forest",
        name="Deep Forest",
        description="Ancient trees tower overhead, blocking much of the sunlight. Strange sounds echo in the distance."
    )
    
    # Add zones to the world
    engine.add_zone(town_square)
    engine.add_zone(forest_edge)
    engine.add_zone(tavern)
    engine.add_zone(blacksmith)
    engine.add_zone(deep_forest)
    
    # Connect zones
    engine.connect_zones("town_square", "forest_edge")
    engine.connect_zones("town_square", "tavern")
    engine.connect_zones("town_square", "blacksmith")
    engine.connect_zones("forest_edge", "deep_forest")
    
    # Create items
    sword = Item(
        id="iron_sword",
        name="Iron Sword",
        description="A standard iron sword with a leather grip. It's well-balanced and sharp.",
        properties={"damage": 5, "value": 10}
    )
    
    healing_potion = Item(
        id="healing_potion",
        name="Healing Potion",
        description="A small vial containing a red liquid. It smells of herbs and honey.",
        properties={"healing": 20, "value": 5}
    )
    
    map = Item(
        id="forest_map",
        name="Forest Map",
        description="A weathered map showing paths through the forest. Some areas are marked with warnings.",
        properties={"value": 2}
    )
    
    amulet = Item(
        id="ancient_amulet",
        name="Ancient Amulet",
        description="A strange amulet with intricate engravings. It seems to pulse with a faint magical energy.",
        properties={"value": 50, "magical": True}
    )
    
    # Create NPCs
    innkeeper = NPC(
        id="innkeeper",
        name="Mira the Innkeeper",
        description="A friendly middle-aged woman with a warm smile. She knows all the local gossip.",
        behavior_traits={"friendly": 8, "talkative": 7, "helpful": 6}
    )
    innkeeper.inventory.add_item(healing_potion, 3)
    
    blacksmith_npc = NPC(
        id="blacksmith_npc",
        name="Tordek Ironheart",
        description="A burly dwarf with a thick beard. His arms are muscled from years at the forge.",
        behavior_traits={"gruff": 6, "honest": 8, "skilled": 9}
    )
    blacksmith_npc.inventory.add_item(sword, 2)
    
    forest_guide = NPC(
        id="forest_guide",
        name="Elara the Ranger",
        description="A lithe elf with keen eyes. She knows the forest better than anyone.",
        behavior_traits={"observant": 9, "cautious": 7, "knowledgeable": 8}
    )
    forest_guide.inventory.add_item(map, 1)
    
    # Create objects
    fountain = Object(
        id="town_fountain",
        name="Town Fountain",
        description="A large stone fountain at the center of the square. The water is clear and cool.",
        properties={"can_drink": True, "refreshment": 2}
    )
    
    notice_board = Object(
        id="notice_board",
        name="Notice Board",
        description="A wooden board covered with notices, wanted posters, and advertisements.",
        properties={"quests": ["missing_shipment", "herb_gathering"]}
    )
    
    ancient_tree = Object(
        id="ancient_tree",
        name="Ancient Oak",
        description="An enormous oak tree that must be centuries old. There's a strange symbol carved into its trunk.",
        properties={"magical": True, "secret_passage": "forest_shrine"}
    )
    
    mysterious_altar = Object(
        id="forest_altar",
        name="Mysterious Altar",
        description="A stone altar deep in the forest. It seems to be very old and is covered in strange runes.",
        properties={"magical": True, "requires_item": "ancient_amulet"}
    )
    
    # Add NPCs to zones
    engine.add_npc(innkeeper, "tavern")
    engine.add_npc(blacksmith_npc, "blacksmith")
    engine.add_npc(forest_guide, "forest_edge")
    
    # Add objects to zones
    engine.add_object(fountain, "town_square")
    engine.add_object(notice_board, "town_square")
    engine.add_object(ancient_tree, "deep_forest")
    engine.add_object(mysterious_altar, "deep_forest")
    
    # Create a player (we'll add them when a player connects)
    starter_inventory = Inventory(id="player_inventory")
    starter_inventory.add_item(healing_potion, 2)
    
    player = Player(
        id="player",
        name="Adventurer",
        description="A brave adventurer seeking fame and fortune.",
        inventory=starter_inventory
    )
    
    # Add the player to the town square
    engine.add_player(player, "town_square")
    
    return engine

async def main():
    """Main function to run the game"""
    console.print(Panel.fit(
        "[bold cyan]Welcome to Eldoria[/bold cyan]\n"
        "A simple fantasy adventure powered by AI agents",
        title="AI-Augmented Agentique Game Engine",
        border_style="cyan"
    ))
    
    console.print("Creating game world...", style="yellow")
    engine = await create_fantasy_game()
    console.print("Game world created!", style="green")
    
    # Start the game loop in a separate task
    game_loop_task = asyncio.create_task(engine.run_game_loop())
    
    player_id = "player"  # We use a fixed player ID for this simple example
    
    try:
        console.print("\n[bold yellow]You find yourself in the town square of Silverwood Village.[/bold yellow]")
        console.print("[yellow]Type 'help' for a list of commands, or just describe what you want to do.[/yellow]\n")
        
        while True:
            user_input = Prompt.ask("[bold cyan]What would you like to do?[/bold cyan]")
            
            if user_input.lower() in ["quit", "exit"]:
                break
            
            # Process the player's input
            event = await engine.process_player_input(player_id, user_input)
            
            # Display the response based on event type
            if event.type == EventType.MESSAGE:
                console.print(f"[yellow]{event.content}[/yellow]")
            elif event.type == EventType.DIALOGUE:
                console.print(f"[green]{event.source_id}: {event.content}[/green]")
            elif event.type == EventType.MOVEMENT:
                console.print(f"[cyan]{event.content}[/cyan]")
            elif event.type == EventType.INTERACTION:
                console.print(f"[magenta]{event.content}[/magenta]")
            elif event.type == EventType.TRADE:
                console.print(f"[blue]{event.content}[/blue]")
            else:
                console.print(f"[gray]{event.content}[/gray]")
    
    except KeyboardInterrupt:
        console.print("\n[bold red]Game interrupted by user.[/bold red]")
    except Exception as e:
        console.print(f"\n[bold red]Error: {str(e)}[/bold red]")
    finally:
        # Stop the game loop
        engine.stop()
        game_loop_task.cancel()
        try:
            await game_loop_task
        except asyncio.CancelledError:
            pass
        
        console.print("\n[bold cyan]Thank you for playing![/bold cyan]")

if __name__ == "__main__":
    asyncio.run(main())