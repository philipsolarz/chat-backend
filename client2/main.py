#!/usr/bin/env python
# Main entry point for RPG Chat Client

import os
import sys
import asyncio
import signal
from typing import Dict, Any, List, Optional

from client2 import auth, api, chat, ui
from client2.state import game_state
from client2.config import config

# Handle graceful shutdown
def setup_signal_handlers():
    """Set up signal handlers for graceful shutdown"""
    def handle_exit(signum, frame):
        print("\nExiting RPG Chat Client...")
        sys.exit(0)
        
    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)

async def select_world() -> bool:
    """Select or create a world"""
    # Get available worlds
    worlds = api.get_worlds()
    
    # If no worlds, create one
    if not worlds:
        return await create_world()
        
    # Show options menu
    options = [
        "Select an existing world",
        "Create a new world"
    ]
    
    choice = ui.show_menu("World Selection", options, f"Welcome, {game_state.user_email}")
    
    if not choice:
        return False
        
    if choice == "1":  # Select existing
        world = ui.select_item(
            worlds, 
            lambda w: f"{w['name']} ({w.get('genre', 'No genre')})",
            "Select a World"
        )
        
        if world:
            game_state.set_world(world)
            ui.show_success(f"Selected world: {world['name']}")
            return True
    elif choice == "2":  # Create new
        return await create_world()
            
    return False

async def create_world() -> bool:
    """Create a new world"""
    ui.show_title("Create World", "Create your own custom world")
    
    name = ui.prompt("World Name")
    description = ui.prompt("Description (optional)", required=False)
    genre = ui.prompt("Genre (e.g., Fantasy, Sci-Fi)", required=False)
    
    ui.show_info("Creating world...")
    world = api.create_world(name, description, genre)
    
    if world:
        game_state.set_world(world)
        ui.show_success(f"World '{name}' created successfully!")
        return True
    else:
        ui.show_error("Failed to create world")
        return False

async def select_character() -> bool:
    """Select or create a character in the current world"""
    if not game_state.current_world_id:
        ui.show_error("No world selected")
        return False
    
    # Get characters in current world
    all_characters = api.get_characters()
    world_characters = [c for c in all_characters if c.get("world_id") == game_state.current_world_id]
    
    # If no characters, create one
    if not world_characters:
        ui.show_info("You don't have any characters in this world.")
        return await create_character()
    
    # Show options menu
    options = [
        "Select an existing character",
        "Create a new character"
    ]
    
    choice = ui.show_menu(
        "Character Selection", 
        options,
        f"World: {game_state.current_world_name}"
    )
    
    if not choice:
        return False
        
    if choice == "1":  # Select existing
        character = ui.select_item(
            world_characters, 
            lambda c: f"{c['name']} ({c.get('description', '')[:30]}...)",
            "Select a Character"
        )
        
        if character:
            game_state.set_character(character)
            ui.show_success(f"Selected character: {character['name']}")
            
            # Get zone info if needed
            if character.get("zone_id") and not game_state.current_zone_name:
                zone = api.get_zone(character["zone_id"])
                if zone:
                    game_state.set_zone(zone)
            
            return True
    elif choice == "2":  # Create new
        return await create_character()
            
    return False

async def create_character() -> bool:
    """Create a new character in the current world"""
    if not game_state.current_world_id:
        ui.show_error("No world selected")
        return False
        
    ui.show_title("Create Character", "Create a new character for this world")
    
    name = ui.prompt("Character Name")
    description = ui.prompt("Description (personality, appearance, etc.)", required=False)
    
    # Get zones for selection
    zones = api.get_zones(game_state.current_world_id)
    
    zone_id = None
    if zones:
        zone = ui.select_item(
            zones,
            lambda z: f"{z['name']} ({z.get('zone_type', 'general')})",
            "Select Starting Zone"
        )
        
        if zone:
            zone_id = zone["id"]
            game_state.set_zone(zone)
    else:
        ui.show_warning("No zones found in this world. Creating default zone...")
        
        # Create a default zone
        zone = api.create_zone(
            game_state.current_world_id,
            "Town Square",
            "The central meeting place of the world.",
            "town"
        )
        
        if zone:
            zone_id = zone["id"]
            game_state.set_zone(zone)
    
    ui.show_info("Creating character...")
    character = api.create_character(name, game_state.current_world_id, description, zone_id)
    
    if character:
        game_state.set_character(character)
        ui.show_success(f"Character '{name}' created successfully!")
        return True
    else:
        ui.show_error("Failed to create character")
        return False

async def enter_chat() -> None:
    """Connect to game chat"""
    if not all([game_state.current_character_id, game_state.current_zone_id]):
        ui.show_error("Character or zone not selected")
        return
    
    ui.show_title(
        f"RPG Chat - {game_state.current_world_name}", 
        f"Playing as {game_state.current_character_name} in {game_state.current_zone_name}"
    )
    
    # Connect to chat
    client = chat.ChatClient(
        game_state.current_character_id,
        game_state.current_zone_id
    )
    
    if not await client.connect():
        ui.show_error("Failed to connect to chat")
        return
    
    ui.show_info("Type your messages below. Type /help for commands.")
    
    # Chat loop
    while not client.shutdown_requested:
        try:
            message = ui.get_input()
            
            if not message:
                continue
            
            # Process commands
            if message.startswith('/'):
                if message.lower() in ['/exit', '/quit']:
                    break
                
                handled = await client.process_command(message)
                if not handled:
                    # Command not recognized, send as regular message
                    await client.send_message(message)
            else:
                # Regular message
                await client.send_message(message)
        
        except KeyboardInterrupt:
            break
        except Exception as e:
            ui.show_error(f"Error: {str(e)}")
    
    # Disconnect from chat
    await client.disconnect()

async def main() -> None:
    """Main application flow"""
    setup_signal_handlers()
    
    # Display welcome message
    ui.show_title("RPG CHAT CLIENT", "Connect to Interactive Virtual Worlds")
    ui.show_info(f"API URL: {config.api_url}")
    ui.show_info(f"WebSocket URL: {config.ws_url}")
    
    # Step 1: Authentication
    if not await auth.authenticate():
        ui.show_warning("Authentication cancelled. Exiting.")
        return
    
    # Step 2: World Selection
    if not await select_world():
        ui.show_warning("World selection cancelled. Exiting.")
        return
    
    # Step 3: Character Selection
    if not await select_character():
        ui.show_warning("Character selection cancelled. Exiting.")
        return
    
    # Step 4: Enter the world and start chatting
    await enter_chat()
    
    ui.show_info("Thank you for playing RPG Chat!")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExiting RPG Chat Client. Goodbye!")
    except Exception as e:
        ui.show_error(f"Unhandled error: {str(e)}")
        import traceback
        traceback.print_exc()