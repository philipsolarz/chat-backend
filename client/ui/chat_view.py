#!/usr/bin/env python
# Zone chat interface and WebSocket handling
import asyncio
import os
from typing import Dict, Any, Optional, List, Tuple

from client.game.state import game_state
from client.game.chat import chat_manager
from client.api.zone_service import ZoneService
from client.api.character_service import CharacterService
from client.api.conversation_service import ConversationService
from client.api.message_service import MessageService
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
        self.conversation_service = ConversationService()
        self.message_service = MessageService()
        
        self.chat_ui = None
        self.zone_name = None
        self.character_name = None
        self.exit_requested = False
        self.message_queue = asyncio.Queue()
    
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
        
        # Find or create a conversation for this zone
        conversation = await display_loading(
            f"Joining zone chat...",
            self.conversation_service.find_or_create_zone_conversation(zone_id, character_id)
        )
        
        if not conversation:
            show_error("Failed to join zone chat")
            return False
        
        # Store conversation and participant IDs in game state
        game_state.current_conversation_id = conversation.get("id")
        
        # Find our participant ID if not already set
        if not game_state.current_participant_id:
            participants = conversation.get("participants", [])
            for participant in participants:
                if (participant.get("user_id") == game_state.current_user_id and 
                    participant.get("character_id") == character_id):
                    game_state.current_participant_id = participant.get("id")
                    break
        
        if not game_state.current_participant_id:
            show_error("Failed to determine participant ID")
            return False
        
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
        
        return True
    
    async def on_message(self, sender: str, content: str, is_self: bool = False, 
                         is_ai: bool = False, is_system: bool = True):
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
        # Get participant information to show who's typing
        pass  # We'll implement this later if needed
    
    async def on_presence(self, active_users: List[Dict[str, Any]]):
        """Handle presence information"""
        user_count = len(active_users)
        participants = []
        
        for user in active_users:
            user_participants = user.get("participants", [])
            participants.extend(user_participants)
        
        await self.on_message(
            "System", 
            f"Active users in zone: {user_count} | Characters: {len(participants)}", 
            False, False, True
        )
    
    async def load_recent_messages(self) -> bool:
        """Load recent messages from the conversation"""
        if not game_state.current_conversation_id:
            return False
            
        messages = await display_loading(
            "Loading recent messages...",
            self.message_service.get_recent_messages(
                game_state.current_conversation_id,
                limit=20
            )
        )
        
        if not messages:
            await self.on_message(
                "System", 
                "No previous messages in this zone", 
                False, False, True
            )
            return True
        
        # Process messages (newest first, so we need to reverse)
        for msg in reversed(messages):
            character_name = msg.get("character_name", "Unknown")
            content = msg.get("content", "")
            is_self = msg.get("user_id") == game_state.current_user_id
            is_ai = msg.get("is_ai", False)
            
            self.chat_ui.add_message(character_name, content, is_self, is_system=False)
        
        return True
    
    async def start_chat(self) -> None:
        """Start the chat interface"""
        self.exit_requested = False
        
        # Display static chat interface
        self.chat_ui.display()
        
        # Load recent messages
        await self.load_recent_messages()
        
        # Connect to WebSocket
        if not game_state.current_conversation_id or not game_state.current_participant_id:
            show_error("Conversation or participant ID not set")
            return
        
        # Start WebSocket connection
        asyncio.create_task(
            chat_manager.start(
                game_state.current_conversation_id,
                game_state.current_participant_id
            )
        )
        
        # Process user input in a loop
        while not self.exit_requested and not chat_manager.shutdown_requested:
            # Clear current line and get input
            # We're manually handling input since we want to keep displaying messages
            # while waiting for input
            user_input = input("> ")
            
            if user_input.strip().lower() == '/exit':
                self.exit_requested = True
                chat_manager.shutdown_requested = True
                break
            
            # Handle other commands
            if user_input.startswith('/'):
                await self.handle_command(user_input)
                continue
            
            # Send regular message
            if user_input.strip():
                # Add as self message
                self.chat_ui.add_message(self.character_name, user_input, True)
    
    async def handle_command(self, command: str) -> None:
        """Handle chat commands"""
        parts = command.split(maxsplit=1)
        cmd = parts[0].lower()
        
        if cmd == '/help':
            await self.on_message(
                "System", 
                "Available commands:\n"
                "/exit - Exit chat\n"
                "/help - Show this help\n"
                "/who - Show users in zone\n"
                "/clear - Clear chat\n"
                "/me <action> - Perform an action",
                False, False, True
            )
        elif cmd == '/who':
            # Request presence information
            await chat_manager.request_presence()
        elif cmd == '/clear':
            # Clear chat history
            self.chat_ui.clear_messages()
            await self.on_message("System", "Chat cleared", False, False, True)
        elif cmd == '/me' and len(parts) > 1:
            # Emote/action
            action = parts[1]
            message = f"*{self.character_name} {action}*"
            self.chat_ui.add_message("", message, True)
            await chat_manager.send_message(message)
        else:
            await self.on_message(
                "System", 
                f"Unknown command: {cmd}. Type /help for available commands.", 
                False, False, True
            )
    
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
        
        # Get agents in zone
        agents = await display_loading(
            "Loading NPCs in zone...",
            self.zone_service.get_zone_agents(game_state.current_zone_id)
        )
        
        show_title(f"Zone: {zone['name']}", "Zone Information")
        
        # Show zone details
        console.print(f"[bold]Description:[/bold] {zone.get('description', 'No description')}")
        console.print(f"[bold]Type:[/bold] {zone.get('zone_type', 'general')}")
        
        # Show characters
        console.print("\n[bold]Characters in this zone:[/bold]")
        if characters:
            for i, char in enumerate(characters, 1):
                owner = "(You)" if char.get("user_id") == game_state.current_user_id else ""
                console.print(f"[cyan]{i}.[/cyan] {char['name']} {owner}")
        else:
            console.print("[yellow]No player characters in this zone[/yellow]")
        
        # Show NPCs
        console.print("\n[bold]NPCs in this zone:[/bold]")
        if agents:
            for i, agent in enumerate(agents, 1):
                console.print(f"[cyan]{i}.[/cyan] {agent['name']}")
        else:
            console.print("[yellow]No NPCs in this zone[/yellow]")
        
        # Wait for user to press enter
        input("\nPress Enter to continue...")
    
    async def show_chat_menu(self) -> Optional[str]:
        """Show chat menu options"""
        options = [
            ("enter", "Enter zone chat"),
            ("info", "View zone information"),
            ("character", "Change character"),
            ("back", "Return to world map")
        ]
        
        subtitle = None
        if game_state.current_zone_id and game_state.current_zone_name:
            subtitle = f"Current Zone: {game_state.current_zone_name}"
            
        if game_state.current_character_id and game_state.current_character_name:
            if subtitle:
                subtitle += f" | Character: {game_state.current_character_name}"
            else:
                subtitle = f"Character: {game_state.current_character_name}"
        
        return create_menu("Zone Chat", options, subtitle)