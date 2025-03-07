"""
Example game using the refactored Agentique Game Engine with GameMaster architecture.
"""
import asyncio
import os
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from typing import List, Tuple, Dict

from base_models import (
    World, Zone, Character, Object, Item, Event, EventType
)

from game_engine import GameEngine
from event_system import EventBus

# Load environment variables for API keys
load_dotenv()

# Setup console
console = Console()

async def create_fantasy_world() -> Tuple[World, List[Character]]:
    """Create a simple fantasy game world"""
    # Create the world
    world = World(name="Mythoria", description="A land of magic and adventure")
    
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
    world.add_zone(village_square)
    world.add_zone(forest_path)
    world.add_zone(tavern)
    world.add_zone(riverside)
    world.add_zone(cave_entrance)
    
    # Connect zones
    world.connect_zones(village_square.id, tavern.id)
    world.connect_zones(village_square.id, forest_path.id)
    world.connect_zones(forest_path.id, riverside.id)
    world.connect_zones(forest_path.id, cave_entrance.id)
    
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
    world.add_item(sword)
    world.add_item(potion)
    world.add_item(map_item)
    world.add_item(amulet)
    world.add_item(apple)
    
    # Create characters
    
    # AI-controlled characters
    innkeeper = Character(
        name="Marta the Innkeeper",
        description="A middle-aged woman with a warm smile and flour-dusted apron. She runs the tavern and knows all the local gossip.",
        controller_type="AI"
    )
    innkeeper.inventory.add_item(apple, 5)
    innkeeper.inventory.add_item(potion, 2)
    
    guard = Character(
        name="Guard Tomas",
        description="A village guard with a stern expression but kind eyes. He takes his duty of protecting the village very seriously.",
        controller_type="AI"
    )
    guard.inventory.add_item(sword, 1)
    
    fisherwoman = Character(
        name="Elara the Fisherwoman",
        description="A weathered woman with sun-tanned skin who knows the river better than anyone. She's rarely seen without her fishing rod.",
        controller_type="AI"
    )
    fisherwoman.inventory.add_item(map_item, 1)
    
    mysterious_stranger = Character(
        name="Hooded Stranger",
        description="A figure in a dark cloak whose face is shadowed by their hood. They seem to be watching the cave entrance intently.",
        controller_type="AI"
    )
    mysterious_stranger.inventory.add_item(amulet, 1)
    
    # Player character
    player = Character(
        name="Adventurer",
        description="A brave adventurer seeking fortune and glory.",
        controller_type="PLAYER"
    )
    player.inventory.add_item(potion, 1)
    
    # Add characters to zones
    tavern.add_character(innkeeper)
    village_square.add_character(guard)
    riverside.add_character(fisherwoman)
    cave_entrance.add_character(mysterious_stranger)
    village_square.add_character(player)
    
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
    village_square.add_object(fountain)
    village_square.add_object(notice_board)
    forest_path.add_object(old_tree)
    riverside.add_object(fishing_spot)
    cave_entrance.add_object(glowing_crystal)
    
    return world, [player]

class GameInterface:
    """Interface for interacting with the game"""
    
    def __init__(self, engine: GameEngine):
        self.engine = engine
        self.console = Console()
        self.current_player_id = None
        self.event_queue = asyncio.Queue()
        
        # Set up event handler for player messages
        asyncio.create_task(self._setup_event_handlers())
    
    async def _setup_event_handlers(self) -> None:
        """Set up event handlers for the interface"""
        # Handle messages to the player
        async def handle_player_events(event: Event) -> None:
            if not self.current_player_id:
                return
                
            # Only handle events targeted at the current player
            if event.target_id == self.current_player_id:
                await self.event_queue.put(event)
        
        self.engine.event_bus.subscribe(None, handle_player_events)
    
    async def start_game(self) -> None:
        """Start the game and run the main loop"""
        self.console.print(Panel.fit(
            "[bold magenta]Welcome to Mythoria[/bold magenta]\n"
            "A fantasy adventure powered by AI agents",
            title="Agentique Game Engine Demo",
            border_style="magenta"
        ))
        
        self.console.print("Creating game world...", style="yellow")
        player_ids = await self.engine.setup_world(create_fantasy_world)
        
        if not player_ids:
            self.console.print("Error: No player characters found!", style="bold red")
            return
        
        self.current_player_id = player_ids[0]
        self.console.print("Game world created!", style="green")
        
        # Start the game loop in the background
        game_loop_task = asyncio.create_task(self.engine.run_game_loop())
        
        # Show initial description
        self.console.print("\n[bold yellow]You find yourself in the village square of Eldervale.[/bold yellow]")
        self.console.print("[yellow]Type 'help' for available commands, or simply describe what you want to do.[/yellow]\n")
        
        # Auto-look at the beginning
        await self.process_command("look")
        
        # Process any queued events
        await self._process_event_queue()
        
        try:
            while True:
                user_input = await asyncio.to_thread(
                    Prompt.ask, "[bold green]What would you like to do?[/bold green]"
                )
                
                if user_input.lower() in ["quit", "exit"]:
                    break
                
                # Process the input
                await self.process_command(user_input)
                
                # Process any queued events
                await self._process_event_queue()
                
        except KeyboardInterrupt:
            self.console.print("\n[bold red]Game interrupted by user.[/bold red]")
        except Exception as e:
            self.console.print(f"\n[bold red]Error: {str(e)}[/bold red]")
        finally:
            # Stop the game loop
            self.engine.stop()
            game_loop_task.cancel()
            try:
                await game_loop_task
            except asyncio.CancelledError:
                pass
            
            self.console.print("\n[bold magenta]Thank you for playing![/bold magenta]")
    
    async def process_command(self, command: str) -> None:
        """Process a player command"""
        if not self.current_player_id:
            self.console.print("Error: No active player!", style="bold red")
            return
        
        # Send the command to the engine
        event = await self.engine.process_character_input(self.current_player_id, command)
        
        # Display the response
        self._display_event(event)
    
    async def _process_event_queue(self) -> None:
        """Process all queued events"""
        # Get all events that are currently in the queue
        while not self.event_queue.empty():
            event = await self.event_queue.get()
            self._display_event(event)
    
    def _display_event(self, event: Event) -> None:
        """Display an event to the user"""
        world = self.engine.world_manager.get_world()
        
        if event.type == EventType.MESSAGE:
            self.console.print(f"[cyan]{event.content}[/cyan]")
        elif event.type == EventType.DIALOGUE:
            if event.source_id == self.current_player_id:
                self.console.print(f"[green]You: {event.content}[/green]")
            else:
                # Get character name if possible
                char_name = "Someone"
                char = world.get_character_by_id(event.source_id)
                if char:
                    char_name = char.name
                self.console.print(f"[yellow]{char_name}: {event.content}[/yellow]")
        elif event.type == EventType.MOVEMENT:
            self.console.print(f"[magenta]{event.content}[/magenta]")
        elif event.type == EventType.INTERACTION:
            self.console.print(f"[blue]{event.content}[/blue]")
        else:
            self.console.print(f"{event.content}")
        
        self.console.print()  # Empty line for readability

async def main():
    """Main function to run the game"""
    # Create the game engine
    engine = GameEngine()
    
    # Create the game interface
    interface = GameInterface(engine)
    
    # Start the game
    await interface.start_game()

if __name__ == "__main__":
    asyncio.run(main())