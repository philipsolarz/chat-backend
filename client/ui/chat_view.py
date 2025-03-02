#!/usr/bin/env python
# Zone chat interface and WebSocket handling
import asyncio
import os
from typing import Dict, Any, Optional, List, Tuple

from client.game.state import game_state
from client.game.chat import chat_manager
from client.api.zone_service import ZoneService
from client.api.character_service import CharacterService
from client.api.entity_service import EntityService
from client.ui.console import (
    console, clear_screen, show_title, show_error, show_success, show_warning,
    prompt_input, confirm_action, create_menu, display_loading, display_table,
    ChatUI
)


class ChatView:
    """User interface for zone-based chat"""
    
    def __init__(self):
        self.zone_service = ZoneService()
        self.character_service = CharacterService()
        self.entity_service = EntityService()
        
        self.chat_ui = None
        self.zone_name = None
        self.character_name = None
        self.exit_requested = False
        self.message_queue = asyncio.Queue()
        
        # Keep track of entities in the zone
        self.zone_characters = []
        self.zone_objects = []
    
    async def initialize_chat(self, zone_id: str, character_id: str) -> bool:
        """Initialize chat for a specific zone and character"""
        # Load zone details
        zone = await display_loading(
            "Loading zone details...",
            self.zone_service.get_zone(zone_id)
        )
        
        if not zone:
            show_error("Failed to load zone details")
            return False
        
        self.zone_name = zone.get("name", "Unknown Zone")
        
        # Load character details
        character = await display_loading(
            "Loading character details...",
            self.character_service.get_character(character_id)
        )
        
        if not character:
            show_error("Failed to load character details")
            return False
        
        self.character_name = character.get("name", "Unknown Character")
        
        # Initialize chat UI
        self.chat_ui = ChatUI(
            f"Zone Chat: {self.zone_name}",
            f"You are chatting as: {self.character_name}"
        )
        
        # Set up chat manager callbacks
        chat_manager.on_message = self.on_message
        chat_manager.on_error = self.on_error
        chat_manager.on_connect = self.on_connect
        chat_manager.on_disconnect = self.on_disconnect
        chat_manager.on_typing = self.on_typing
        chat_manager.on_presence = self.on_presence
        
        # Load zone entities
        await self.load_zone_entities(zone_id)
        
        return True
    
    async def load_zone_entities(self, zone_id: str) -> bool:
        """Load entities in the zone"""
        try:
            # Get characters in the zone
            characters = await self.zone_service.get_zone_characters(zone_id)
            self.zone_characters = characters
            
            # Get objects in the zone
            entities = await self.entity_service.get_entities_in_zone(zone_id)
            self.zone_objects = [e for e in entities if e.get("type") == "object"]
            
            return True
        except Exception as e:
            console.print(f"[red]Error loading zone entities: {str(e)}[/red]")
            return False
    
    async def on_message(self, sender: str, content: str, is_self: bool = False, 
                         is_ai: bool = False, is_system: bool = False):
        """Handle incoming chat message"""
        # Add message to UI
        self.chat_ui.add_message(sender, content, is_self, is_system)
        
        # Add to message queue for live display
        await self.message_queue.put({
            "type": "message",
            "sender": sender,
            "content": content,
            "is_self": is_self,
            "is_system": is_system
        })
    
    async def on_error(self, error_message: str):
        """Handle error messages"""
        await self.on_message("System", f"Error: {error_message}", False, False, True)
    
    async def on_connect(self, message: str):
        """Handle connection status messages"""
        await self.on_message("System", message, False, False, True)
    
    async def on_disconnect(self, message: str):
        """Handle disconnection messages"""
        await self.on_message("System", message, False, False, True)
    
    async def on_typing(self, user_id: str, participant_id: str, is_typing: bool):
        """Handle typing notifications"""
        # This might not be supported in the new WebSocket format,
        # but we'll keep it for now
        pass
    
    async def on_presence(self, active_users: List[Dict[str, Any]]):
        """Handle presence information"""
        character_count = len(active_users)
        if character_count > 0:
            character_names = [user.get("name", "Unknown") for user in active_users]
            await self.on_message(
                "System", 
                f"Characters in zone: {', '.join(character_names)}", 
                False, False, True
            )
        else:
            await self.on_message(
                "System", 
                "No other characters detected in this zone", 
                False, False, True
            )
    
    async def handle_command(self, command: str) -> bool:
        """Handle special client-side chat commands"""
        parts = command.split(maxsplit=1)
        cmd = parts[0].lower()
        
        if cmd == '/clear':
            # Clear chat history
            self.chat_ui.clear_messages()
            return True
            
        elif cmd == '/help':
            # Show help in addition to server-side help
            self.chat_ui.add_message("System", 
                "Client commands:\n"
                "/exit - Exit chat\n"
                "/clear - Clear chat history\n"
                "/info - Show zone information\n"
                "/list_objects - List objects in zone\n"
                "/list_characters - List characters in zone\n", 
                False, True)
            return False  # Let server handle it too
            
        elif cmd == '/info':
            # Show zone info
            self.chat_ui.add_message("System", 
                f"Current zone: {self.zone_name} (ID: {game_state.current_zone_id})\n"
                f"Your character: {self.character_name} (ID: {game_state.current_character_id})\n"
                f"Characters in zone: {len(self.zone_characters)}\n"
                f"Objects in zone: {len(self.zone_objects)}", 
                False, True)
            return True
            
        elif cmd == '/list_objects':
            # List objects in zone
            if self.zone_objects:
                object_list = "\n".join([f"{i+1}. {obj.get('name', 'Unknown')} (ID: {obj.get('id', 'unknown')})" 
                                        for i, obj in enumerate(self.zone_objects)])
                self.chat_ui.add_message("System", f"Objects in zone:\n{object_list}", False, True)
            else:
                self.chat_ui.add_message("System", "No objects in this zone", False, True)
            return True
            
        elif cmd == '/list_characters':
            # List characters in zone
            if self.zone_characters:
                char_list = "\n".join([f"{i+1}. {char.get('name', 'Unknown')} (ID: {char.get('id', 'unknown')})" 
                                      for i, char in enumerate(self.zone_characters)])
                self.chat_ui.add_message("System", f"Characters in zone:\n{char_list}", False, True)
            else:
                self.chat_ui.add_message("System", "No other characters in this zone", False, True)
            return True
            
        # If not handled, return False to let the server handle it
        return False
    
    async def start_chat(self) -> bool:
        """Start the chat interface"""
        self.exit_requested = False
        
        # Check requirements
        if not game_state.current_zone_id or not game_state.current_character_id:
            show_error("Zone or character ID not set")
            return False
            
        # Initialize chat
        if not await self.initialize_chat(game_state.current_zone_id, game_state.current_character_id):
            show_error("Failed to initialize chat")
            return False
        
        # Display static chat interface
        clear_screen()
        self.chat_ui.display()
        
        # Connect to WebSocket
        connection_task = asyncio.create_task(
            chat_manager.start(
                game_state.current_character_id,
                game_state.current_zone_id
            )
        )
        
        # Process user input in a loop
        while not self.exit_requested and not chat_manager.shutdown_requested:
            # Clear current line and get input
            user_input = input("> ")
            
            if user_input.strip().lower() == '/exit':
                self.exit_requested = True
                chat_manager.shutdown_requested = True
                break
            
            # Handle client-side commands
            if user_input.startswith('/'):
                # If command wasn't handled by client, send to server
                if not await self.handle_command(user_input):
                    # Let the server handle it
                    chat_manager.user_input_queue.put_nowait(user_input)
            else:
                # Regular message - add to UI and send to server
                if user_input.strip():
                    self.chat_ui.add_message(self.character_name, user_input, True)
                    chat_manager.user_input_queue.put_nowait(user_input)
        
        # Wait for connection task to complete
        try:
            await connection_task
        except Exception as e:
            console.print(f"[red]Error in chat connection: {str(e)}[/red]")
        
        return True
    
    async def show_zone_info(self) -> None:
        """Show information about the current zone"""
        if not game_state.current_zone_id:
            show_error("No zone selected")
            return
        
        zone = await display_loading(
            "Loading zone details...",
            self.zone_service.get_zone(game_state.current_zone_id)
        )
        
        if not zone:
            show_error("Failed to load zone details")
            return
        
        # Get characters in zone
        characters = await display_loading(
            "Loading characters in zone...",
            self.zone_service.get_zone_characters(game_state.current_zone_id)
        )
        
        # Get objects in zone
        entities = await display_loading(
            "Loading entities in zone...",
            self.entity_service.get_entities_in_zone(game_state.current_zone_id)
        )
        
        objects = [e for e in entities if e.get("type") == "object"]
        
        show_title(f"Zone: {zone['name']}", "Zone Information")
        
        # Show zone details
        console.print(f"[bold]Description:[/bold] {zone.get('description', 'No description')}")
        console.print(f"[bold]Type:[/bold] {zone.get('zone_type', 'general')}")
        
        # Show characters
        console.print("\n[bold]Characters in this zone:[/bold]")
        if characters:
            for i, char in enumerate(characters, 1):
                is_self = char.get("id") == game_state.current_character_id
                owner = "(You)" if is_self else ""
                console.print(f"[cyan]{i}.[/cyan] {char['name']} {owner}")
        else:
            console.print("[yellow]No other characters in this zone[/yellow]")
        
        # Show objects
        console.print("\n[bold]Objects in this zone:[/bold]")
        if objects:
            for i, obj in enumerate(objects, 1):
                console.print(f"[cyan]{i}.[/cyan] {obj['name']} (ID: {obj['id']})")
        else:
            console.print("[yellow]No objects in this zone[/yellow]")
        
        # Wait for user to press enter
        input("\nPress Enter to continue...")


# class EntityService:
#     """Service for entity-related API operations"""
    
#     def __init__(self):
#         from client.api.base_service import BaseService
#         self.base_service = BaseService()
    
#     async def get_entities_in_zone(self, zone_id: str):
#         """Get all entities in a zone"""
#         try:
#             response = await self.base_service.get(f"/entities/?zone_id={zone_id}")
#             return response.get("items", [])
#         except Exception as e:
#             console.print(f"[red]Error getting entities in zone: {str(e)}[/red]")
#             return []