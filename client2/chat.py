import asyncio
import json
import websockets
from typing import Dict, Any

from client2.config import config
from client2.state import game_state
from client2 import ui

class ChatClient:
    """Simplified WebSocket chat client for RPG Client supporting system, message, error, pong, and usage events."""
    
    def __init__(self, character_id: str, zone_id: str):
        self.character_id = character_id
        self.zone_id = zone_id
        self.websocket = None
        self.connected = False
        self.shutdown_requested = False
    
    async def connect(self) -> bool:
        """Connect to the WebSocket server."""
        if not game_state.access_token:
            ui.show_system_message("error: Not logged in")
            return False
        
        try:
            # Build the WebSocket URL
            ws_url = f"{config.ws_url}/worlds/{game_state.current_world_id}"
            ws_url += f"?character_id={self.character_id}&zone_id={self.zone_id}&access_token={game_state.access_token}"
            
            ui.show_system_message("system: Connecting to game server...")
            self.websocket = await websockets.connect(ws_url, ping_interval=30, ping_timeout=10)
            self.connected = True
            ui.show_system_message("system: Connected to game server!")
            
            # Start listening for events
            asyncio.create_task(self._listen_for_events())
            return True
        
        except websockets.exceptions.ConnectionClosed:
            ui.show_system_message("error: Connection closed by server")
            return False
        except Exception as e:
            ui.show_system_message(f"error: Connection error: {str(e)}")
            return False
    
    async def disconnect(self) -> None:
        """Disconnect from the WebSocket server."""
        self.connected = False
        if self.websocket:
            await self.websocket.close()
            self.websocket = None
        ui.show_system_message("system: Disconnected from game server")
    
    async def _listen_for_events(self) -> None:
        """Listen for events from the server."""
        if not self.websocket:
            return
        
        try:
            while self.connected and not self.shutdown_requested:
                try:
                    event = await asyncio.wait_for(self.websocket.recv(), timeout=0.5)
                    await self._process_event(event)
                except asyncio.TimeoutError:
                    continue
                except websockets.exceptions.ConnectionClosed:
                    ui.show_system_message("error: Connection closed by server")
                    self.connected = False
                    break
        except Exception as e:
            ui.show_system_message(f"error: Error in WebSocket listener: {str(e)}")
            self.connected = False
    
    async def _process_event(self, event: str) -> None:
        """Process a message received from the server."""
        ui.show_system_message(f"{event}")
        try:
            data = json.loads(event)
        except json.JSONDecodeError:
            ui.show_system_message(f"error: Failed to decode event: {event}")
            return
        
        event_type = data.get("type")
        if event_type == "system":
            await self._handle_system(data)
        elif event_type == "message":
            await self._handle_message(data)
        elif event_type == "error":
            await self._handle_error(data)
        elif event_type == "pong":
            await self._handle_pong(data)
        elif event_type == "usage":
            await self._handle_usage(data)
        else:
            ui.show_system_message(f"error: Unknown event type: {event_type}")
    
    async def _handle_system(self, data: Dict[str, Any]) -> None:
        """Handle system events."""
        content = data.get("content", "")
        ui.show_system_message(f"system: {content}")
    
    async def _handle_message(self, data: Dict[str, Any]) -> None:
        """Handle message events."""
        content = data.get("content", "")
        ui.show_system_message(f"message: {content}")
    
    async def _handle_error(self, data: Dict[str, Any]) -> None:
        """Handle error events."""
        error_msg = data.get("error", "Unknown error")
        ui.show_system_message(f"error: {error_msg}")
    
    async def _handle_pong(self, data: Dict[str, Any]) -> None:
        """Handle pong events."""
        content = data.get("content", "pong")
        ui.show_system_message(f"pong: {content}")
    
    async def _handle_usage(self, data: Dict[str, Any]) -> None:
        """Handle usage events."""
        content = data.get("content", "")
        ui.show_system_message(f"usage: {content}")
    
    async def send_message(self, content: str) -> bool:
        """Send a chat message to the server."""
        if not self.websocket or not self.connected:
            ui.show_system_message("error: Not connected to game server")
            return False
        
        try:
            message = {"type": "message", "content": content}
            await self.websocket.send(json.dumps(message))
            return True
        except Exception as e:
            ui.show_system_message(f"error: Error sending message: {str(e)}")
            return False



# # WebSocket chat client for RPG Client
# import asyncio
# import json
# import websockets
# from typing import Dict, Any, List, Optional, Callable, Awaitable

# from client2.config import config
# from client2.state import game_state
# from client2 import ui

# class ChatClient:
#     """Client for zone-based chat using WebSockets"""
    
#     def __init__(self, character_id: str, zone_id: str):
#         self.character_id = character_id
#         self.zone_id = zone_id
#         self.websocket = None
#         self.connected = False
#         self.shutdown_requested = False
    
#     async def connect(self) -> bool:
#         """Connect to the WebSocket server"""
#         if not game_state.access_token:
#             ui.show_error("Not logged in")
#             return False
        
#         try:
#             # Build WebSocket URL with world_id in the path
#             ws_url = f"{config.ws_url}/worlds/{game_state.current_world_id}"
#             ws_url += f"?character_id={self.character_id}&zone_id={self.zone_id}&access_token={game_state.access_token}"
            
#             ui.show_info("Connecting to game server...")
            
#             # Connect to WebSocket
#             self.websocket = await websockets.connect(
#                 ws_url, 
#                 ping_interval=30, 
#                 ping_timeout=10
#             )
            
#             self.connected = True
#             ui.show_success("Connected to game server!")
            
#             # Start the event listener
#             asyncio.create_task(self._listen_for_events())

#             return True
        
#         except websockets.exceptions.ConnectionClosed:
#             ui.show_error("Connection closed by server")
#             return False
#         except Exception as e:
#             ui.show_error(f"Connection error: {str(e)}")
#             return False
    
#     async def disconnect(self) -> None:
#         """Disconnect from the WebSocket server"""
#         self.connected = False
        
#         if self.websocket:
#             await self.websocket.close()
#             self.websocket = None
            
#         ui.show_info("Disconnected from game server")
    
#     async def _listen_for_events(self) -> None:
#         """Listen for events from the server"""
#         if not self.websocket:
#             return
            
#         try:
#             while self.connected and not self.shutdown_requested:
#                 try:
#                     event = await asyncio.wait_for(self.websocket.recv(), timeout=0.5)
#                     await self._process_event(event)
#                 except asyncio.TimeoutError:
#                     # This is normal, just keep checking
#                     continue
#                 except websockets.exceptions.ConnectionClosed:
#                     ui.show_error("Connection closed by server")
#                     self.connected = False
#                     break
        
#         except Exception as e:
#             ui.show_error(f"Error in WebSocket listener: {str(e)}")
#             self.connected = False
    
#     async def _process_event(self, event: str) -> None:
#         """Process a message received from the server"""
#         try:
#             data = json.loads(event)
#         except json.JSONDecodeError:
#             ui.show_error(f"Failed to decode event: {event}")
#             return
        
#         # Handle different event types
#         event_type = data.get("type")
        
#         if event_type == "game_event":
#             # Game events (message, movement, interaction, etc.)
#             await self._handle_game_event(data)
#         elif event_type == "zone_data":
#             # Zone information
#             await self._handle_zone_data(data)
#         elif event_type == "recent_messages":
#             # Recent messages in zone
#             await self._handle_recent_messages(data)
#         elif event_type == "error":
#             # Error message
#             error = data.get("error", "Unknown error")
#             ui.show_error(error)
#         elif event_type == "usage_update":
#             # Usage information
#             await self._handle_usage_update(data)
#         elif event_type == "pong":
#             # Ping response - no action needed
#             pass
    
#     async def _handle_game_event(self, data: Dict[str, Any]) -> None:
#         """Handle different types of game events"""
#         game_event_type = data.get("event_type")
        
#         if game_event_type == "message":
#             # Chat message
#             character_id = data.get("character_id")
#             character_name = data.get("character_name", "Unknown")
#             content = data.get("content", "")
#             is_from_self = character_id == self.character_id
            
#             ui.show_chat_message(character_name, content, is_from_self)
#         elif game_event_type == "character_entered":
#             # Character entered zone
#             character_name = data.get("character_name", "Unknown")
#             ui.show_system_message(f"{character_name} has entered the zone")
#         elif game_event_type == "character_left":
#             # Character left zone
#             character_name = data.get("character_name", "Unknown")
#             ui.show_system_message(f"{character_name} has left the zone")
#         elif game_event_type == "emote":
#             # Character emote
#             character_name = data.get("character_name", "Unknown")
#             emote = data.get("emote", "")
#             ui.show_emote(f"{character_name} {emote}")
    
#     async def _handle_zone_data(self, data: Dict[str, Any]) -> None:
#         """Handle zone data information"""
#         zone_id = data.get("zone_id")
#         characters = data.get("characters", [])
        
#         # Show characters in zone
#         character_names = [c.get("name", "Unknown") for c in characters]
#         if character_names:
#             ui.show_system_message(f"Characters in zone: {', '.join(character_names)}")
#         else:
#             ui.show_system_message("You are alone in this zone")
    
#     async def _handle_recent_messages(self, data: Dict[str, Any]) -> None:
#         """Handle recent messages"""
#         messages = data.get("messages", [])
        
#         if messages:
#             ui.show_system_message(f"Showing {len(messages)} recent messages")
            
#             # Process messages in chronological order
#             for msg in messages:
#                 character_id = msg.get("character_id")
#                 character_name = msg.get("character_name", "Unknown")
#                 content = msg.get("content", "")
#                 is_from_self = character_id == self.character_id
                
#                 ui.show_chat_message(character_name, content, is_from_self)
    
#     async def _handle_usage_update(self, data: Dict[str, Any]) -> None:
#         """Handle usage update information"""
#         usage = data.get("usage", {})
#         messages_remaining = usage.get("messages_remaining_today", 0)
#         is_premium = usage.get("is_premium", False)
        
#         ui.show_system_message(f"Messages remaining today: {messages_remaining} | Premium: {is_premium}")
    
#     async def send_message(self, content: str) -> bool:
#         """Send a chat message"""
#         if not self.websocket or not self.connected:
#             ui.show_error("Not connected to game server")
#             return False
            
#         try:
#             message = {
#                 "type": "message",
#                 "content": content
#             }
            
#             await self.websocket.send(json.dumps(message))
#             return True
        
#         except Exception as e:
#             ui.show_error(f"Error sending message: {str(e)}")
#             return False
