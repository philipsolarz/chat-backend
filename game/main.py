"""
Simple example game using the Agentique Game Engine.
"""
import asyncio
import os
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from base_models import (
    World, Zone, NPC, Player, Object, Item, Event, EventType
)

from game_engine import SimpleGameEngine

# Load environment variables for API keys
load_dotenv()

# Setup console
console = Console()

async def create_fantasy_game() -> SimpleGameEngine:
    """Create a simple fantasy game world"""
    engine = SimpleGameEngine()
    
    # Create the world
    engine.create_world("Mythoria", "A land of magic and adventure")
    
    # Create zones
    village_square = Zone(
        name="Village Square",
        description="The central square of Eldervale Village. A fountain bubbles in the center, and villagers go about their daily business."
    )
    
    forest_path = Zone(
        name="Forest Path",
        description="A winding dirt path through the ancient forest. Towering trees block much of the sunlight, and strange sounds echo in the distance."
    )
    
    tavern = Zone(
        name="The Dragon's Rest Tavern",
        description="A cozy tavern with a roaring fireplace. The smell of ale and hearty stew fills the air, and patrons chat quietly at wooden tables."
    )
    
    riverside = Zone(
        name="Riverside",
        description="A peaceful spot where the river widens and slows. Reeds sway in the gentle current, and you can see fish swimming beneath the surface."
    )
    
    cave_entrance = Zone(
        name="Mysterious Cave",
        description="A dark opening in the cliff face. Cool air flows from within, carrying strange echoes. Moss grows around the entrance."
    )
    
    # Add zones to the world
    engine.add_zone(village_square)
    engine.add_zone(forest_path)
    engine.add_zone(tavern)
    engine.add_zone(riverside)
    engine.add_zone(cave_entrance)
    
    # Connect zones
    engine.connect_zones(village_square.id, tavern.id)
    engine.connect_zones(village_square.id, forest_path.id)
    engine.connect_zones(forest_path.id, riverside.id)
    engine.connect_zones(forest_path.id, cave_entrance.id)
    
    # Create items
    sword = Item(
        name="Rusty Sword",
        description="An old sword with a rusted blade but still sharp enough to be useful.",
        properties={"damage": 3, "value": 5}
    )
    
    potion = Item(
        name="Healing Potion",
        description="A small glass vial containing a red liquid that smells of herbs.",
        properties={"healing": 20, "value": 10}
    )
    
    map_item = Item(
        name="Faded Map",
        description="A weathered map showing the local area. Some locations are marked with X's.",
        properties={"value": 5}
    )
    
    amulet = Item(
        name="Strange Amulet",
        description="A silver amulet with a blue stone that seems to glow faintly in the dark.",
        properties={"magic": True, "value": 30}
    )
    
    apple = Item(
        name="Fresh Apple",
        description="A crisp, juicy apple with bright red skin.",
        properties={"food": True, "value": 1}
    )
    
    # Add items to the world's registry
    engine.add_item(sword)
    engine.add_item(potion)
    engine.add_item(map_item)
    engine.add_item(amulet)
    engine.add_item(apple)
    
    # Create NPCs
    innkeeper = NPC(
        name="Marta the Innkeeper",
        description="A middle-aged woman with a warm smile and flour-dusted apron. She runs the tavern and knows all the local gossip."
    )
    innkeeper.inventory.add_item(apple, 5)
    innkeeper.inventory.add_item(potion, 2)
    
    guard = NPC(
        name="Guard Tomas",
        description="A village guard with a stern expression but kind eyes. He takes his duty of protecting the village very seriously."
    )
    guard.inventory.add_item(sword, 1)
    
    fisherwoman = NPC(
        name="Elara the Fisherwoman",
        description="A weathered woman with sun-tanned skin who knows the river better than anyone. She's rarely seen without her fishing rod."
    )
    fisherwoman.inventory.add_item(map_item, 1)
    
    mysterious_stranger = NPC(
        name="Hooded Stranger",
        description="A figure in a dark cloak whose face is shadowed by their hood. They seem to be watching the cave entrance intently."
    )
    mysterious_stranger.inventory.add_item(amulet, 1)
    
    # Add NPCs to zones
    engine.add_npc(innkeeper, tavern.id)
    engine.add_npc(guard, village_square.id)
    engine.add_npc(fisherwoman, riverside.id)
    engine.add_npc(mysterious_stranger, cave_entrance.id)
    
    # Create objects
    fountain = Object(
        name="Stone Fountain",
        description="A circular stone fountain with a statue of a fish in the center. The water looks clean and refreshing.",
        properties={"drinkable": True}
    )
    
    notice_board = Object(
        name="Notice Board",
        description="A wooden board covered with various notices and announcements. Some look official, others are handwritten.",
        properties={"readable": True}
    )
    
    old_tree = Object(
        name="Ancient Oak",
        description="An enormous oak tree that must be centuries old. Its gnarled branches spread wide, providing shade.",
        properties={"climbable": True}
    )
    
    fishing_spot = Object(
        name="Fishing Spot",
        description="A calm area of the river that seems perfect for fishing. You can see fish swimming beneath the surface.",
        properties={"fishable": True}
    )
    
    glowing_crystal = Object(
        name="Glowing Crystal",
        description="A strange crystal formation that emits a soft blue glow. It seems to pulse gently, almost like it's breathing.",
        properties={"magical": True}
    )
    
    # Add objects to zones
    engine.add_object(fountain, village_square.id)
    engine.add_object(notice_board, village_square.id)
    engine.add_object(old_tree, forest_path.id)
    engine.add_object(fishing_spot, riverside.id)
    engine.add_object(glowing_crystal, cave_entrance.id)
    
    # Create a player
    player = Player(
        name="Adventurer",
        description="A brave adventurer seeking fortune and glory."
    )
    player.inventory.add_item(potion, 1)
    
    # Add the player to the starting zone
    engine.add_player(player, village_square.id)
    
    return engine, player.id

async def main():
    """Main function to run the game"""
    console.print(Panel.fit(
        "[bold magenta]Welcome to Mythoria[/bold magenta]\n"
        "A simple fantasy adventure powered by AI agents",
        title="Agentique Game Engine Demo",
        border_style="magenta"
    ))
    
    console.print("Creating game world...", style="yellow")
    engine, player_id = await create_fantasy_game()
    console.print("Game world created!", style="green")
    
    # Start the game loop in the background
    game_loop_task = asyncio.create_task(engine.run_game_loop())
    
    # Show initial description
    console.print("\n[bold yellow]You find yourself in the village square of Eldervale.[/bold yellow]")
    console.print("[yellow]Type 'help' for available commands, or simply describe what you want to do.[/yellow]\n")
    
    # Auto-look at the beginning
    initial_look = await engine.process_player_input(player_id, "look")
    console.print(f"[cyan]{initial_look.content}[/cyan]\n")
    
    try:
        while True:
            user_input = Prompt.ask("[bold green]What would you like to do?[/bold green]")
            
            if user_input.lower() in ["quit", "exit"]:
                break
            
            # Process the input
            event = await engine.process_player_input(player_id, user_input)
            
            # Display the response based on event type
            if event.type == EventType.MESSAGE:
                console.print(f"[cyan]{event.content}[/cyan]")
            elif event.type == EventType.DIALOGUE:
                if event.source_id == player_id:
                    console.print(f"[green]You: {event.content}[/green]")
                else:
                    # Get NPC name if possible
                    npc_name = "Someone"
                    for zone in engine.world.zones.values():
                        if event.source_id in zone.npcs:
                            npc_name = zone.npcs[event.source_id].name
                    console.print(f"[yellow]{npc_name}: {event.content}[/yellow]")
            elif event.type == EventType.MOVEMENT:
                console.print(f"[magenta]{event.content}[/magenta]")
            elif event.type == EventType.INTERACTION:
                console.print(f"[blue]{event.content}[/blue]")
            else:
                console.print(f"{event.content}")
            
            console.print()  # Empty line for readability
    
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
        
        console.print("\n[bold magenta]Thank you for playing![/bold magenta]")

if __name__ == "__main__":
    asyncio.run(main())