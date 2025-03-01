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
    """Manages WebSocket connection and chat message processing"""
    
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
        
    async def connect(self, conversation_id: str, participant_id: str):
        """Connect to the WebSocket server"""
        # Check if we have the required information
        if not game_state.access_token:
            console.print("[red]Not logged in[/red]")
            return False
            
        if not conversation_id or not participant_id:
            console.print("[red]Conversation or participant ID missing[/red]")
            return False
            
        try:
            # Build WebSocket URL
            ws_url = f"{config.ws_url}/conversations/{conversation_id}"
            ws_url += f"?participant_id={participant_id}&access_token={game_state.access_token}"
            
            if self.on_connect:
                await self.on_connect("Connecting to chat server...")
            
            # Connect to WebSocket
            self.websocket = await websockets.connect(
                ws_url, 
                ping_interval=30, 
                ping_timeout=10
            )
            
            self.connected = True
            game_state.connected = True
            
            if self.on_connect:
                await self.on_connect("Connected to chat server!")
                
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
            await self.on_disconnect("Disconnected from chat server")
    
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
        
        if event_type == "message":
            # Chat message
            msg = data.get("message", {})
            sender_name = msg.get("character_name", "Unknown")
            content = msg.get("content", "")
            is_from_self = msg.get("user_id") == game_state.current_user_id
            is_ai = msg.get("is_ai", False)
            
            if self.on_message:
                await self.on_message(sender_name, content, is_from_self, is_ai)
                
        elif event_type == "error":
            # Error message
            error = data.get("error", "Unknown error")
            
            if self.on_error:
                await self.on_error(error)
                
        elif event_type == "typing":
            # Typing notification
            user_id = data.get("user_id")
            participant_id = data.get("participant_id")
            is_typing = data.get("is_typing", True)
            
            if self.on_typing and user_id != game_state.current_user_id:
                await self.on_typing(user_id, participant_id, is_typing)
                
        elif event_type == "presence":
            # Presence information
            active_users = data.get("active_users", [])
            
            if self.on_presence:
                await self.on_presence(active_users)
                
        elif event_type == "usage_update" or event_type == "usage_limits":
            # Update usage info
            usage = data.get("usage", {})
            messages_remaining = usage.get("messages_remaining_today", 0)
            is_premium = usage.get("is_premium", False)
            game_state.is_premium = is_premium
            
            # Add as system message
            if self.on_message:
                await self.on_message(
                    "System", 
                    f"Messages remaining today: {messages_remaining} | Premium: {is_premium}",
                    False, 
                    False, 
                    True  # is_system
                )
    
    async def send_message(self, content: str):
        """Send a chat message"""
        if not self.websocket or not self.connected:
            if self.on_error:
                await self.on_error("Not connected to chat server")
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
    
    async def send_typing_notification(self, is_typing: bool = True):
        """Send typing status notification"""
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
        """Request presence information"""
        if not self.websocket or not self.connected:
            return False
            
        try:
            await self.websocket.send(json.dumps({"type": "presence"}))
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
    
    async def start(self, conversation_id: str, participant_id: str):
        """Start the chat connection and message processing"""
        # Connect to WebSocket
        if not await self.connect(conversation_id, participant_id):
            return False
            
        # Start the keep-alive task
        keep_alive_task = asyncio.create_task(self.start_keep_alive())
        
        # Start the message listener
        listener_task = asyncio.create_task(self.listen())
        
        # Wait for both tasks to complete
        try:
            # Request initial presence and usage info
            await self.request_presence()
            await self.check_usage()
            
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
                    
                    # Send typing notification
                    await self.send_typing_notification(True)
                    
                    # Send the message
                    await self.send_message(user_input)
                    
                    # Stop typing
                    await self.send_typing_notification(False)
                    
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