# app/websockets/connection_manager.py
from fastapi import WebSocket, WebSocketDisconnect, HTTPException, status
from sqlalchemy.orm import Session
from typing import Dict, List, Any, Optional, Set
import json
import logging
import asyncio
from datetime import datetime

from app.database import get_db
from app.services.auth_service import AuthService
from app.services.conversation_service import ConversationService
from app.services.message_service import MessageService
from app.services.usage_service import UsageService
from app.ai.agent_manager import AgentManager

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manager for WebSocket connections"""
    
    def __init__(self):
        # Map of conversation_id -> dict of WebSocket -> participant info
        self.active_connections: Dict[str, Dict[WebSocket, Dict[str, Any]]] = {}
        # Map of user_id -> set of WebSocket connections
        self.user_connections: Dict[str, Set[WebSocket]] = {}
    
    async def connect(
        self, 
        websocket: WebSocket, 
        conversation_id: str,
        user_id: str,
        participant_id: Optional[str] = None
    ):
        """Connect a client to a conversation"""
        await websocket.accept()
        
        # Initialize conversation connections if needed
        if conversation_id not in self.active_connections:
            self.active_connections[conversation_id] = {}
        
        # Store connection with metadata
        self.active_connections[conversation_id][websocket] = {
            "user_id": user_id,
            "participant_id": participant_id,
            "joined_at": datetime.now().isoformat()
        }
        
        # Track user connections
        if user_id not in self.user_connections:
            self.user_connections[user_id] = set()
        self.user_connections[user_id].add(websocket)
        
        # Notify other clients about new connection
        await self.broadcast_to_conversation(
            conversation_id,
            {
                "type": "connection",
                "event": "connected",
                "user_id": user_id,
                "participant_id": participant_id,
                "timestamp": datetime.now().isoformat()
            },
            exclude=websocket
        )
    
    def disconnect(self, websocket: WebSocket):
        """Disconnect a client from all conversations"""
        # Find all connections for this websocket
        for conversation_id, connections in list(self.active_connections.items()):
            if websocket in connections:
                user_id = connections[websocket]["user_id"]
                participant_id = connections[websocket]["participant_id"]
                
                # Remove from conversation
                del connections[websocket]
                
                # Clean up empty conversation entries
                if not connections:
                    del self.active_connections[conversation_id]
                else:
                    # Notify others about disconnection
                    asyncio.create_task(self.broadcast_to_conversation(
                        conversation_id,
                        {
                            "type": "connection",
                            "event": "disconnected",
                            "user_id": user_id,
                            "participant_id": participant_id,
                            "timestamp": datetime.now().isoformat()
                        }
                    ))
                
                # Remove from user connections
                if user_id in self.user_connections:
                    self.user_connections[user_id].discard(websocket)
                    if not self.user_connections[user_id]:
                        del self.user_connections[user_id]
    
    async def broadcast_to_conversation(
        self, 
        conversation_id: str, 
        message: Dict[str, Any],
        exclude: Optional[WebSocket] = None
    ):
        """Broadcast a message to all clients in a conversation"""
        if conversation_id in self.active_connections:
            for connection in list(self.active_connections[conversation_id].keys()):
                if connection != exclude:
                    try:
                        await connection.send_json(message)
                    except Exception as e:
                        logger.error(f"Error sending message to client: {str(e)}")
                        # Connection might be dead, remove it
                        self.disconnect(connection)
    
    async def broadcast_to_user(self, user_id: str, message: Dict[str, Any]):
        """Broadcast a message to all connections for a specific user"""
        if user_id in self.user_connections:
            for connection in list(self.user_connections[user_id]):
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.error(f"Error sending message to user: {str(e)}")
                    # Connection might be dead, remove it
                    self.disconnect(connection)
    
    def get_active_users_in_conversation(self, conversation_id: str) -> Dict[str, Any]:
        """Get details of all active users in a conversation"""
        if conversation_id not in self.active_connections:
            return {}
        
        # Collect user information with connection counts
        user_info = {}
        for conn_data in self.active_connections[conversation_id].values():
            user_id = conn_data["user_id"]
            if user_id not in user_info:
                user_info[user_id] = {
                    "user_id": user_id,
                    "connection_count": 1,
                    "participants": []
                }
            else:
                user_info[user_id]["connection_count"] += 1
            
            # Track unique participants for this user
            participant_id = conn_data.get("participant_id")
            if participant_id and participant_id not in user_info[user_id]["participants"]:
                user_info[user_id]["participants"].append(participant_id)
        
        return user_info
    
    def get_active_participants_in_conversation(self, conversation_id: str) -> Set[str]:
        """Get set of active participant IDs in a conversation"""
        if conversation_id not in self.active_connections:
            return set()
        
        participants = set()
        for conn_data in self.active_connections[conversation_id].values():
            participant_id = conn_data.get("participant_id")
            if participant_id:
                participants.add(participant_id)
        
        return participants
    
    def get_user_connection_count(self, user_id: str) -> int:
        """Get the number of active connections for a user"""
        return len(self.user_connections.get(user_id, set()))


# Singleton connection manager
connection_manager = ConnectionManager()


async def handle_websocket_connection(
    websocket: WebSocket,
    conversation_id: str,
    token: str,
    participant_id: Optional[str] = None,
    db: Session = None
):
    """Handle a WebSocket connection for a conversation"""
    # Create DB session if not provided
    close_db = False
    if db is None:
        db = next(get_db())
        close_db = True
    
    try:
        # Authenticate user
        auth_service = AuthService(db)
        
        try:
            # Verify token
            payload = auth_service.verify_token(token)
            user_id = payload.get("sub")
            
            if not user_id:
                await websocket.close(code=4001, reason="Authentication failed")
                return
            
            # Get user
            user = auth_service.get_user_by_id(user_id)
            if not user:
                await websocket.close(code=4001, reason="User not found")
                return
            
            # Verify conversation exists
            conversation_service = ConversationService(db)
            conversation = conversation_service.get_conversation(conversation_id)
            if not conversation:
                await websocket.close(code=4004, reason="Conversation not found")
                return
            
            # Verify user has access to the conversation
            if not conversation_service.check_user_access(user_id, conversation_id):
                await websocket.close(code=4003, reason="You don't have access to this conversation")
                return
            
            # If participant_id provided, verify ownership
            if participant_id:
                participant = conversation_service.get_participant(participant_id)
                
                if not participant or participant.conversation_id != conversation_id:
                    await websocket.close(code=4003, reason="Participant not found in this conversation")
                    return
                
                if not participant.user_id or participant.user_id != user_id:
                    await websocket.close(code=4003, reason="You don't control this participant")
                    return
            
            # Connect to WebSocket
            await connection_manager.connect(
                websocket=websocket,
                conversation_id=conversation_id,
                user_id=user_id,
                participant_id=participant_id
            )
            
            # Send presence information (who's online)
            active_users = connection_manager.get_active_users_in_conversation(conversation_id)
            await websocket.send_json({
                "type": "presence",
                "active_users": list(active_users.values()),
                "timestamp": datetime.now().isoformat()
            })
            
            # Initialize services
            message_service = MessageService(db)
            agent_manager = AgentManager(db)
            usage_service = UsageService(db)
            
            # Send usage limits info
            await websocket.send_json({
                "type": "usage_limits",
                "limits": {
                    "can_send_messages": usage_service.can_send_message(user_id),
                    "messages_remaining_today": usage_service.get_remaining_daily_messages(user_id),
                    "is_premium": usage_service.payment_service.is_premium(user_id)
                },
                "timestamp": datetime.now().isoformat()
            })
            
            # Listen for messages
            try:
                while True:
                    # Receive message from WebSocket
                    data = await websocket.receive_text()
                    message_data = json.loads(data)
                    
                    # Process message based on type
                    message_type = message_data.get("type", "message")
                    
                    if message_type == "message":
                        # Check message limit before processing
                        if not usage_service.can_send_message(user_id):
                            await websocket.send_json({
                                "type": "error",
                                "error": "You have reached your daily message limit",
                                "is_premium": usage_service.payment_service.is_premium(user_id),
                                "timestamp": datetime.now().isoformat()
                            })
                            continue
                        
                        # Validate the participant_id was provided either at connection or in message
                        participant_id_to_use = message_data.get("participant_id") or participant_id
                        if not participant_id_to_use:
                            await websocket.send_json({
                                "type": "error",
                                "error": "Participant ID required for sending messages",
                                "timestamp": datetime.now().isoformat()
                            })
                            continue
                        
                        # Verify participant ownership again (in case it was provided in the message)
                        if message_data.get("participant_id"):
                            participant = conversation_service.get_participant(participant_id_to_use)
                            if not participant or participant.conversation_id != conversation_id:
                                await websocket.send_json({
                                    "type": "error",
                                    "error": "Participant not found in this conversation",
                                    "timestamp": datetime.now().isoformat()
                                })
                                continue
                            
                            if not participant.user_id or participant.user_id != user_id:
                                await websocket.send_json({
                                    "type": "error",
                                    "error": "You don't control this participant",
                                    "timestamp": datetime.now().isoformat()
                                })
                                continue
                        
                        # Get content
                        content = message_data.get("content", "").strip()
                        if not content:
                            await websocket.send_json({
                                "type": "error",
                                "error": "Message content cannot be empty",
                                "timestamp": datetime.now().isoformat()
                            })
                            continue
                        
                        # Track message in usage service
                        usage_service.track_message_sent(user_id, is_from_ai=False)
                        
                        # Create the message
                        db_message = message_service.create_message(
                            conversation_id=conversation_id,
                            participant_id=participant_id_to_use,
                            content=content
                        )
                        
                        if db_message:
                            # Get sender info
                            sender_info = message_service.get_sender_info(db_message)
                            
                            # Broadcast the message
                            await connection_manager.broadcast_to_conversation(
                                conversation_id,
                                {
                                    "type": "message",
                                    "message": {
                                        "id": db_message.id,
                                        "content": db_message.content,
                                        "participant_id": participant_id_to_use,
                                        "character_id": sender_info["character_id"],
                                        "character_name": sender_info["character_name"],
                                        "user_id": sender_info["user_id"],
                                        "agent_id": sender_info["agent_id"],
                                        "is_ai": sender_info["is_ai"],
                                        "conversation_id": conversation_id,
                                        "created_at": db_message.created_at.isoformat()
                                    },
                                    "timestamp": datetime.now().isoformat()
                                }
                            )
                            
                            # Generate AI responses in the background
                            asyncio.create_task(process_ai_responses(
                                agent_manager=agent_manager,
                                usage_service=usage_service,
                                connection_manager=connection_manager,
                                conversation_id=conversation_id,
                                participant_id=participant_id_to_use,
                                user_id=user_id
                            ))
                            
                            # Update user about remaining messages
                            await websocket.send_json({
                                "type": "usage_update",
                                "usage": {
                                    "messages_remaining_today": usage_service.get_remaining_daily_messages(user_id),
                                    "can_send_messages": usage_service.can_send_message(user_id),
                                    "is_premium": usage_service.payment_service.is_premium(user_id)
                                },
                                "timestamp": datetime.now().isoformat()
                            })
                        else:
                            await websocket.send_json({
                                "type": "error",
                                "error": "Failed to create message",
                                "timestamp": datetime.now().isoformat()
                            })
                    
                    elif message_type == "typing":
                        # Broadcast typing indicator
                        await connection_manager.broadcast_to_conversation(
                            conversation_id,
                            {
                                "type": "typing",
                                "user_id": user_id,
                                "participant_id": message_data.get("participant_id") or participant_id,
                                "is_typing": message_data.get("is_typing", True),
                                "timestamp": datetime.now().isoformat()
                            },
                            exclude=websocket
                        )
                    
                    elif message_type == "presence":
                        # Request for presence information
                        active_users = connection_manager.get_active_users_in_conversation(conversation_id)
                        await websocket.send_json({
                            "type": "presence",
                            "active_users": list(active_users.values()),
                            "timestamp": datetime.now().isoformat()
                        })
                    
                    elif message_type == "usage_check":
                        # Request for current usage limits
                        await websocket.send_json({
                            "type": "usage_limits",
                            "limits": {
                                "can_send_messages": usage_service.can_send_message(user_id),
                                "messages_remaining_today": usage_service.get_remaining_daily_messages(user_id),
                                "is_premium": usage_service.payment_service.is_premium(user_id)
                            },
                            "timestamp": datetime.now().isoformat()
                        })
                    
                    else:
                        # Unknown message type
                        await websocket.send_json({
                            "type": "error",
                            "error": f"Unknown message type: {message_type}",
                            "timestamp": datetime.now().isoformat()
                        })
            
            except WebSocketDisconnect:
                # Handle disconnect
                connection_manager.disconnect(websocket)
            
            except Exception as e:
                # Handle other errors
                logger.error(f"WebSocket error: {str(e)}")
                connection_manager.disconnect(websocket)
                await websocket.close(code=1011, reason="Server error")
        
        except Exception as e:
            # Handle authentication errors
            logger.error(f"WebSocket authentication error: {str(e)}")
            await websocket.close(code=4001, reason="Authentication failed")
    
    finally:
        # Close the DB session if we created it
        if close_db and db:
            db.close()


async def process_ai_responses(
    agent_manager: AgentManager,
    usage_service: UsageService,
    connection_manager: ConnectionManager,
    conversation_id: str,
    participant_id: str,
    user_id: str
):
    """Process AI agent responses to a message"""
    try:
        # Generate responses from AI agents
        responses = await agent_manager.process_new_message(
            conversation_id=conversation_id,
            participant_id=participant_id
        )
        
        # Broadcast each response and track usage
        for response in responses:
            # Track AI responses in usage
            usage_service.track_message_sent(user_id, is_from_ai=True)
            
            # Broadcast the message
            await connection_manager.broadcast_to_conversation(
                conversation_id,
                {
                    "type": "message",
                    "message": {
                        "id": response.get("message_id"),
                        "content": response.get("content"),
                        "participant_id": response.get("participant_id"),
                        "character_id": response.get("character_id"),
                        "character_name": response.get("character_name"),
                        "agent_id": response.get("agent_id"),
                        "agent_name": response.get("agent_name"),
                        "is_ai": True,
                        "conversation_id": conversation_id,
                        "created_at": response.get("created_at")
                    },
                    "timestamp": datetime.now().isoformat()
                }
            )
    
    except Exception as e:
        logger.error(f"Error processing AI responses: {str(e)}")