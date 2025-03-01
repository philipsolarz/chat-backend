#!/usr/bin/env python
# Main entry point for RPG Chat Client
import asyncio
import sys
import signal
import os
from datetime import datetime

from client.utils.config import config
from client.game.state import game_state
from client.ui.console import (
    console, clear_screen, show_title, show_error, show_success, 
    show_warning, confirm_action, create_menu
)
from client.auth.auth_view import AuthView
from client.ui.world_menu import WorldMenu
from client.ui.character_menu import CharacterMenu
from client.ui.zone_menu import ZoneMenu
from client.ui.chat_view import ChatView


async def shutdown(sig=None):
    """Handle graceful shutdown"""
    if sig:
        console.print(f"\n[yellow]Received signal {sig.name}, shutting down...[/yellow]")
    else:
        console.print("\n[yellow]Shutting down...[/yellow]")
        
    game_state.shutdown_requested = True
    
    # Additional cleanup logic
    # ...
    
    return True


def setup_signal_handlers():
    """Set up signal handlers for graceful shutdown"""
    for sig in (signal.SIGINT, signal.SIGTERM):
        asyncio.get_event_loop().add_signal_handler(
            sig, lambda s=sig: asyncio.create_task(shutdown(s))
        )


async def display_welcome():
    """Display welcome message and instructions"""
    clear_screen()
    
    title = "RPG CHAT CLIENT"
    show_title(title)
    
    welcome_text = (
        "Welcome to the RPG Chat Client!\n\n"
        "This client allows you to explore virtual worlds, create characters, \n"
        "and interact with other players and AI-controlled agents.\n\n"
        "- Select or create a world to begin your adventure\n"
        "- Create and customize characters to represent you\n"
        "- Navigate through different zones in your world\n"
        "- Chat with other players and intelligent agents\n\n"
        "Let's begin your journey!"
    )
    
    console.print(f"[green]{welcome_text}[/green]")
    console.print(f"\n[dim]API URL: {config.api_url}[/dim]")
    console.print(f"[dim]WebSocket URL: {config.ws_url}[/dim]")
    
    await asyncio.sleep(2)  # Short pause to allow reading


async def handle_authentication() -> bool:
    """Handle user authentication flow"""
    auth_view = AuthView()
    
    # Try auto-login first if not explicitly disabled
    args = config.parse_args()
    
    if not args.no_auto_login:
        result = await auth_view.auto_login()
        if result:
            return True
    
    # Show auth menu if auto-login failed or was disabled
    return await auth_view.show_auth_menu()


async def handle_world_selection() -> bool:
    """Handle world selection flow"""
    world_menu = WorldMenu()
    
    # If already have a world selected, confirm using it
    if game_state.current_world_id:
        clear_screen()
        show_title("World Selection")
        console.print(f"[green]Current world: {game_state.current_world_name}[/green]")
        
        if confirm_action("Continue with this world?", default=True):
            return True
        else:
            game_state.clear_world()
    
    # Show world selection menu
    return await world_menu.show_world_selection()


async def handle_character_selection() -> bool:
    """Handle character selection flow"""
    character_menu = CharacterMenu()
    
    # If already have a character selected, confirm using it
    if game_state.current_character_id:
        clear_screen()
        show_title("Character Selection")
        console.print(f"[green]Current character: {game_state.current_character_name}[/green]")
        
        if confirm_action("Continue with this character?", default=True):
            return True
        else:
            game_state.clear_character()
    
    # Show character selection menu
    return await character_menu.show_character_selection()


async def handle_zone_navigation() -> bool:
    """Handle zone navigation flow"""
    zone_menu = ZoneMenu()
    
    # If already have a zone selected, confirm using it
    if game_state.current_zone_id:
        clear_screen()
        show_title("Zone Selection")
        console.print(f"[green]Current zone: {game_state.current_zone_name}[/green]")
        
        if confirm_action("Enter this zone?", default=True):
            return True
        else:
            game_state.clear_zone()
    
    # Show zone navigation menu
    return await zone_menu.show_zone_selection()


async def handle_chat() -> bool:
    """Handle chat interface"""
    chat_view = ChatView()
    
    return await chat_view.start_chat()


async def handle_main_menu() -> str:
    """Show main menu and handle selection"""
    options = [
        ("world", "World Management"),
        ("character", "Character Management"),
        ("zone", "Zone Navigation"),
        ("chat", "Enter Chat"),
        ("account", "Account Settings"),
        ("exit", "Exit Game")
    ]
    
    subtitle = None
    if game_state.is_authenticated():
        subtitle = f"Logged in as: {game_state.user_email}"
        if game_state.current_world_name:
            subtitle += f" | World: {game_state.current_world_name}"
        if game_state.current_character_name:
            subtitle += f" | Character: {game_state.current_character_name}"
        if game_state.current_zone_name:
            subtitle += f" | Zone: {game_state.current_zone_name}"
    
    return create_menu("RPG Chat - Main Menu", options, subtitle)


async def main_loop():
    """Main application loop"""
    # Display welcome message
    await display_welcome()
    
    # Handle authentication
    if not await handle_authentication():
        console.print("[yellow]Exiting due to authentication failure.[/yellow]")
        return
    
    # Main game loop
    while not game_state.shutdown_requested:
        # Show main menu
        choice = await handle_main_menu()
        
        if choice == "world":
            # Handle world management
            world_menu = WorldMenu()
            result = await world_menu.show_world_menu()
            
            if result == "enter":
                # If entering a world, proceed to character selection
                if not await handle_character_selection():
                    continue
                
                # Then to zone selection
                if not await handle_zone_navigation():
                    continue
                
                # Finally to chat
                await handle_chat()
        
        elif choice == "character":
            # Check if world is selected first
            if not game_state.current_world_id:
                show_warning("Please select a world first")
                if not await handle_world_selection():
                    continue
            
            # Handle character management
            character_menu = CharacterMenu()
            await character_menu.show_character_menu()
        
        elif choice == "zone":
            # Check if world and character are selected first
            if not game_state.current_world_id:
                show_warning("Please select a world first")
                if not await handle_world_selection():
                    continue
            
            if not game_state.current_character_id:
                show_warning("Please select a character first")
                if not await handle_character_selection():
                    continue
            
            # Handle zone navigation
            zone_menu = ZoneMenu()
            result = await zone_menu.show_zone_menu()
            
            if result == "enter":
                # If entering a zone, proceed to chat
                await handle_chat()
        
        elif choice == "chat":
            # Check if world, character, and zone are selected first
            if not game_state.current_world_id:
                show_warning("Please select a world first")
                if not await handle_world_selection():
                    continue
            
            if not game_state.current_character_id:
                show_warning("Please select a character first")
                if not await handle_character_selection():
                    continue
            
            if not game_state.current_zone_id:
                show_warning("Please select a zone first")
                if not await handle_zone_navigation():
                    continue
            
            # Handle chat interface
            await handle_chat()
        
        elif choice == "account":
            # Handle account settings
            auth_view = AuthView()
            account_choice = await auth_view.show_account_menu()
            
            if account_choice == "logout":
                # Log out and return to authentication
                if await auth_view.logout():
                    game_state.reset()
                    if not await handle_authentication():
                        console.print("[yellow]Exiting due to authentication failure.[/yellow]")
                        return
        
        elif choice == "exit" or choice is None:
            # Exit game
            if confirm_action("Are you sure you want to exit?", default=False):
                await shutdown()
                break


async def run():
    """Run the main application"""
    # Parse command line arguments
    args = config.parse_args()
    
    # Setup signal handlers
    setup_signal_handlers()
    
    try:
        await main_loop()
    except Exception as e:
        console.print(f"[bold red]Error in main loop: {str(e)}[/bold red]")
        import traceback
        console.print(traceback.format_exc())
    finally:
        console.print("[blue]Thank you for playing RPG Chat![/blue]")


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        console.print("\n[yellow]Application terminated by user[/yellow]")
    except Exception as e:
        console.print(f"\n[bold red]Fatal error: {str(e)}[/bold red]")
        import traceback
        console.print(traceback.format_exc())