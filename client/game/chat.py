#!/usr/bin/env python
# Chat and WebSocket handling
import asyncio
import json
import websockets
import threading
import time
from typing import Dict, Any, Optional, List, Callable, Awaitable
from datetime import datetime

from client.utils.config import config
from client.game.state import game_state
from client.ui.console import console


class ChatConnection:
    """Manages WebSocket connection and game event processing"""
    
    def __init__(self):
        self.websocket = None
        self.connected = False
        self.shutdown_requested = False
        self.input_thread = None
        self.message_queue = asyncio.Queue()
        self.user_input_queue = asyncio.Queue()
        self.character_name = None
        
        # Callbacks
        self.on_message = None
        self.on_error = None
        self.on_connect = None
        self.on_disconnect = None
        self.on_typing = None
        self.on_presence = None
        
    async def connect(self, character_id: str, zone_id: str):
        """Connect to the WebSocket server"""
        # Check if we have the required information
        if not game_state.access_token:
            console.print("[red]Not logged in[/red]")
            return False
            
        if not character_id or not zone_id:
            console.print("[red]Character or zone ID missing[/red]")
            return False
            
        try:
            # Build WebSocket URL
            ws_url = f"{config.ws_url}/game/{character_id}"
            ws_url += f"?zone_id={zone_id}&access_token={game_state.access_token}"
            
            if self.on_connect:
                await self.on_connect("Connecting to game server...")
            
            # Connect to WebSocket
            self.websocket = await websockets.connect(
                ws_url, 
                ping_interval=30, 
                ping_timeout=10
            )
            
            self.connected = True
            game_state.connected = True
            
            if self.on_connect:
                await self.on_connect("Connected to game server!")
                
            # Start send/receive tasks
            return True
        
        except websockets.exceptions.ConnectionRefusedError:
            if self.on_error:
                await self.on_error("Could not connect to server. Server may be offline.")
            return False
            
        except Exception as e:
            if self.on_error:
                await self.on_error(f"Connection error: {str(e)}")
            return False
    
    async def disconnect(self):
        """Disconnect from the WebSocket server"""
        self.connected = False
        game_state.connected = False
        
        if self.websocket:
            await self.websocket.close()
            self.websocket = None
            
        if self.on_disconnect:
            await self.on_disconnect("Disconnected from game server")
    
    async def listen(self):
        """Listen for messages from the server"""
        if not self.websocket or not self.connected:
            return
            
        try:
            while self.connected and not self.shutdown_requested:
                try:
                    message = await asyncio.wait_for(self.websocket.recv(), timeout=0.5)
                    await self._process_message(message)
                except asyncio.TimeoutError:
                    # This is normal, just keep checking
                    continue
                except websockets.exceptions.ConnectionClosed:
                    if self.on_disconnect:
                        await self.on_disconnect("Connection closed by server")
                    self.connected = False
                    game_state.connected = False
                    break
        
        except Exception as e:
            if self.on_error:
                await self.on_error(f"Error in WebSocket listener: {str(e)}")
            self.connected = False
            game_state.connected = False
    
    async def _process_message(self, message: str):
        """Process a message received from the server"""
        try:
            data = json.loads(message)
        except json.JSONDecodeError:
            if self.on_error:
                await self.on_error(f"Failed to decode message: {message}")
            return
        
        # Handle different event types
        event_type = data.get("type")
        
        if event_type == "game_event":
            # Game events (message, movement, interaction, etc.)
            await self._handle_game_event(data)
                
        elif event_type == "zone_data":
            # Zone information
            await self._handle_zone_data(data)
                
        elif event_type == "recent_messages":
            # Recent messages in zone
            await self._handle_recent_messages(data)
                
        elif event_type == "error":
            # Error message
            error = data.get("error", "Unknown error")
            
            if self.on_error:
                await self.on_error(error)
                
        elif event_type == "usage_update":
            # Usage information
            await self._handle_usage_update(data)
                
        elif event_type == "pong":
            # Ping response - no action needed
            pass
    
    async def _handle_game_event(self, data: Dict[str, Any]):
        """Handle different types of game events"""
        game_event_type = data.get("event_type")
        
        if game_event_type == "message":
            # Chat message
            character_id = data.get("character_id")
            character_name = data.get("character_name", "Unknown")
            content = data.get("content", "")
            is_from_self = character_id == game_state.current_character_id
            
            if self.on_message:
                await self.on_message(character_name, content, is_from_self, False)
                
        elif game_event_type == "character_entered":
            # Character entered zone
            character_id = data.get("character_id")
            character_name = data.get("character_name", "Unknown")
            
            if self.on_message:
                await self.on_message(
                    "System", 
                    f"{character_name} has entered the zone", 
                    False, False, True
                )
                
        elif game_event_type == "character_left":
        # or game_event_type == "character_left_zone":
            # Character left zone
            character_id = data.get("character_id")
            character_name = data.get("character_name", "Unknown")
            
            if self.on_message:
                await self.on_message(
                    "System", 
                    f"{character_name} has left the zone", 
                    False, False, True
                )
                
        elif game_event_type == "interaction":
            # Interaction with entity
            character_id = data.get("character_id")
            character_name = data.get("character_name", "Unknown")
            target_entity_id = data.get("target_entity_id")
            target_entity_name = data.get("target_entity_name", "Unknown")
            interaction_type = data.get("interaction_type", "interacts with")
            
            if self.on_message:
                await self.on_message(
                    "System", 
                    f"{character_name} {interaction_type} {target_entity_name}", 
                    False, False, True
                )
                
        elif game_event_type == "emote":
            # Character emote
            character_id = data.get("character_id")
            character_name = data.get("character_name", "Unknown")
            emote = data.get("emote", "")
            
            if self.on_message:
                await self.on_message(
                    "", 
                    f"*{character_name} {emote}*", 
                    False, False, False
                )
                
        elif game_event_type == "quest":
            # Quest-related event
            character_id = data.get("character_id")
            character_name = data.get("character_name", "Unknown")
            quest_id = data.get("quest_id", "")
            quest_action = data.get("quest_action", "")
            
            if self.on_message:
                await self.on_message(
                    "System", 
                    f"{character_name} {quest_action} quest {quest_id}", 
                    False, False, True
                )
                
        elif game_event_type == "combat":
            # Combat action
            character_id = data.get("character_id")
            character_name = data.get("character_name", "Unknown")
            target_entity_id = data.get("target_entity_id")
            target_entity_name = data.get("target_entity_name", "Unknown")
            combat_action = data.get("combat_action", "attacks")
            
            if self.on_message:
                await self.on_message(
                    "System", 
                    f"{character_name} {combat_action} {target_entity_name}!", 
                    False, False, True
                )
                
        elif game_event_type == "trade":
            # Trade between characters
            character_id = data.get("character_id")
            character_name = data.get("character_name", "Unknown")
            trade_action = data.get("trade_action", "offers trade to")
            
            if self.on_message:
                await self.on_message(
                    "System", 
                    f"{character_name} {trade_action}", 
                    False, False, True
                )
    
    async def _handle_zone_data(self, data: Dict[str, Any]):
        """Handle zone data information"""
        zone_id = data.get("zone_id")
        characters = data.get("characters", [])
        objects = data.get("objects", [])
        
        # Show characters in zone
        character_names = [c.get("name", "Unknown") for c in characters]
        object_names = [o.get("name", "Unknown") for o in objects]
        
        if self.on_message:
            await self.on_message(
                "System", 
                f"You are in zone {zone_id}", 
                False, False, True
            )
            
            if character_names:
                await self.on_message(
                    "System", 
                    f"Characters in zone: {', '.join(character_names)}", 
                    False, False, True
                )
            else:
                await self.on_message(
                    "System", 
                    "You are alone in this zone", 
                    False, False, True
                )
                
            if object_names:
                await self.on_message(
                    "System", 
                    f"Objects in zone: {', '.join(object_names)}", 
                    False, False, True
                )
    
    async def _handle_recent_messages(self, data: Dict[str, Any]):
        """Handle recent messages"""
        messages = data.get("messages", [])
        
        if self.on_message:
            await self.on_message(
                "System", 
                f"Showing {len(messages)} recent messages", 
                False, False, True
            )
            
        # Process messages in chronological order
        for msg in messages:
            character_id = msg.get("character_id")
            character_name = msg.get("character_name", "Unknown")
            content = msg.get("content", "")
            is_from_self = character_id == game_state.current_character_id
            
            if self.on_message:
                await self.on_message(character_name, content, is_from_self, False)
    
    async def _handle_usage_update(self, data: Dict[str, Any]):
        """Handle usage update information"""
        usage = data.get("usage", {})
        messages_remaining = usage.get("messages_remaining_today", 0)
        is_premium = usage.get("is_premium", False)
        game_state.is_premium = is_premium
        
        # Add as system message
        if self.on_message:
            await self.on_message(
                "System", 
                f"Messages remaining today: {messages_remaining} | Premium: {is_premium}",
                False, False, True
            )
    
    async def send_message(self, content: str):
        """Send a chat message"""
        if not self.websocket or not self.connected:
            if self.on_error:
                await self.on_error("Not connected to game server")
            return False
            
        try:
            message = {
                "type": "message",
                "content": content
            }
            
            await self.websocket.send(json.dumps(message))
            return True
        
        except Exception as e:
            if self.on_error:
                await self.on_error(f"Error sending message: {str(e)}")
            return False
    
    async def send_emote(self, emote_text: str):
        """Send an emote"""
        if not self.websocket or not self.connected:
            if self.on_error:
                await self.on_error("Not connected to game server")
            return False
            
        try:
            emote = {
                "type": "emote",
                "emote": emote_text
            }
            
            await self.websocket.send(json.dumps(emote))
            return True
        
        except Exception as e:
            if self.on_error:
                await self.on_error(f"Error sending emote: {str(e)}")
            return False
    
    async def send_interaction(self, target_entity_id: str, interaction_type: str, details: Dict[str, Any] = None):
        """Send an interaction with an entity"""
        if not self.websocket or not self.connected:
            if self.on_error:
                await self.on_error("Not connected to game server")
            return False
            
        try:
            interaction = {
                "type": "interaction",
                "target_entity_id": target_entity_id,
                "interaction_type": interaction_type
            }
            
            if details:
                interaction["details"] = details
                
            await self.websocket.send(json.dumps(interaction))
            return True
        
        except Exception as e:
            if self.on_error:
                await self.on_error(f"Error sending interaction: {str(e)}")
            return False
    
    async def send_movement(self, to_zone_id: str):
        """Send a movement to another zone"""
        if not self.websocket or not self.connected:
            if self.on_error:
                await self.on_error("Not connected to game server")
            return False
            
        try:
            movement = {
                "type": "movement",
                "to_zone_id": to_zone_id
            }
            
            await self.websocket.send(json.dumps(movement))
            return True
        
        except Exception as e:
            if self.on_error:
                await self.on_error(f"Error sending movement: {str(e)}")
            return False
    
    async def send_typing_notification(self, is_typing: bool = True):
        """Send typing status notification (if supported)"""
        if not self.websocket or not self.connected:
            return False
            
        try:
            typing_data = {
                "type": "typing",
                "is_typing": is_typing
            }
            
            await self.websocket.send(json.dumps(typing_data))
            return True
        
        except Exception as e:
            if self.on_error:
                await self.on_error(f"Error sending typing notification: {str(e)}")
            return False
    
    async def request_presence(self):
        """Request presence information (who is in zone)"""
        if not self.websocket or not self.connected:
            return False
            
        try:
            await self.websocket.send(json.dumps({"type": "who"}))
            return True
        
        except Exception as e:
            if self.on_error:
                await self.on_error(f"Error requesting presence: {str(e)}")
            return False
    
    async def check_usage(self):
        """Request usage information"""
        if not self.websocket or not self.connected:
            return False
            
        try:
            await self.websocket.send(json.dumps({"type": "usage_check"}))
            return True
        
        except Exception as e:
            if self.on_error:
                await self.on_error(f"Error checking usage: {str(e)}")
            return False
    
    async def send_ping(self):
        """Send ping to keep connection alive"""
        if not self.websocket or not self.connected:
            return False
            
        try:
            await self.websocket.send(json.dumps({"type": "ping"}))
            return True
        
        except Exception as e:
            if self.on_error:
                await self.on_error(f"Error sending ping: {str(e)}")
            return False
    
    async def look_around(self):
        """Request information about the current zone"""
        if not self.websocket or not self.connected:
            return False
            
        try:
            await self.websocket.send(json.dumps({"type": "look"}))
            return True
        
        except Exception as e:
            if self.on_error:
                await self.on_error(f"Error looking around: {str(e)}")
            return False
    
    async def start_keep_alive(self):
        """Start periodic ping to keep connection alive"""
        try:
            while self.connected and not self.shutdown_requested:
                await asyncio.sleep(20)  # Send ping every 20 seconds
                if self.connected:
                    await self.send_ping()
        
        except asyncio.CancelledError:
            pass
        
        except Exception as e:
            if self.on_error:
                await self.on_error(f"Keep-alive error: {str(e)}")
    
    async def process_command(self, command: str):
        """Process chat commands"""
        parts = command.split(maxsplit=1)
        cmd = parts[0].lower()
        
        if cmd == '/help':
            if self.on_message:
                await self.on_message(
                    "System", 
                    "Available commands:\n"
                    "/exit - Exit chat\n"
                    "/help - Show this help\n"
                    "/me <action> - Perform an action\n"
                    "/look - Look around the zone\n"
                    "/who - Show characters in zone\n"
                    "/move <zone_id> - Move to another zone\n"
                    "/interact <entity_id> <action> - Interact with an entity\n"
                    "/clear - Clear chat history\n",
                    False, False, True
                )
        elif cmd == '/me' and len(parts) > 1:
            # Emote
            action = parts[1]
            await self.send_emote(action)
        elif cmd == '/look':
            # Look around
            await self.look_around()
        elif cmd == '/who':
            # Who is in zone
            await self.request_presence()
        elif cmd == '/move' and len(parts) > 1:
            # Move to another zone
            zone_id = parts[1]
            await self.send_movement(zone_id)
        elif cmd == '/interact' and len(parts) > 1:
            # Interact with entity
            interact_parts = parts[1].split(maxsplit=1)
            if len(interact_parts) >= 2:
                entity_id = interact_parts[0]
                action = interact_parts[1]
                await self.send_interaction(entity_id, action)
            else:
                if self.on_message:
                    await self.on_message(
                        "System", 
                        "Usage: /interact <entity_id> <action>", 
                        False, False, True
                    )
        elif cmd == '/clear':
            # Just acknowledge - actual clearing is handled by caller
            if self.on_message:
                await self.on_message(
                    "System", 
                    "Chat history cleared", 
                    False, False, True
                )
        else:
            if self.on_message:
                await self.on_message(
                    "System", 
                    f"Unknown command: {cmd}. Type /help for available commands.", 
                    False, False, True
                )
    
    async def start(self, character_id: str, zone_id: str):
        """Start the chat connection and message processing"""
        # Connect to WebSocket
        if not await self.connect(character_id, zone_id):
            return False
            
        # Start the keep-alive task
        keep_alive_task = asyncio.create_task(self.start_keep_alive())
        
        # Start the message listener
        listener_task = asyncio.create_task(self.listen())
        
        # Wait for both tasks to complete
        try:
            # Request usage info
            await self.check_usage()
            
            # Look around to get zone info
            await self.look_around()
            
            # Start input thread if not already running
            if not self.input_thread or not self.input_thread.is_alive():
                self.start_input_thread()
            
            # Process user input
            while self.connected and not self.shutdown_requested:
                # Check if there's user input to send
                try:
                    user_input = await asyncio.wait_for(self.user_input_queue.get(), timeout=0.1)
                    
                    if user_input.lower() == '/exit':
                        self.shutdown_requested = True
                        break
                    
                    # Check if it's a command
                    if user_input.startswith('/'):
                        await self.process_command(user_input)
                    else:
                        # Send as chat message
                        await self.send_message(user_input)
                    
                except asyncio.TimeoutError:
                    # No user input, just continue
                    await asyncio.sleep(0.1)
        
        finally:
            # Clean up
            self.shutdown_requested = True
            keep_alive_task.cancel()
            listener_task.cancel()
            
            try:
                await keep_alive_task
            except asyncio.CancelledError:
                pass
                
            try:
                await listener_task
            except asyncio.CancelledError:
                pass
                
            # Disconnect
            await self.disconnect()
            
            return True
    
    def start_input_thread(self):
        """Start a thread for getting user input without blocking the event loop"""
        def input_worker():
            while not self.shutdown_requested:
                try:
                    user_input = input("> ")
                    
                    if user_input.strip().lower() == '/exit':
                        self.user_input_queue.put_nowait('/exit')
                        break
                        
                    # Put the input in the queue for the main thread to process
                    self.user_input_queue.put_nowait(user_input)
                    
                except Exception as e:
                    print(f"Error getting input: {str(e)}")
                
                # Small pause to prevent CPU overuse
                time.sleep(0.1)
        
        self.input_thread = threading.Thread(target=input_worker, daemon=True)
        self.input_thread.start()
    
    def stop_input_thread(self):
        """Stop the input thread"""
        self.shutdown_requested = True
        
        if self.input_thread and self.input_thread.is_alive():
            self.input_thread.join(timeout=1.0)


# Global chat manager instance
chat_manager = ChatConnection()