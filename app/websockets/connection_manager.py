# app/websockets/connection_manager.py
import json
import asyncio
import logging
from datetime import datetime
from typing import Dict, Set, Any, Optional, List
from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.auth_service import AuthService
from app.services.conversation_service import ConversationService
from app.services.message_service import MessageService
from app.services.usage_service import UsageService
from app.ai.agent_manager import AgentManager
from app.websockets.event_dispatcher import event_registry

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
    ) -> bool:
        """Register a new WebSocket connection"""
        try:
            if conversation_id not in self.active_connections:
                self.active_connections[conversation_id] = {}
            self.active_connections[conversation_id][websocket] = {
                "user_id": user_id,
                "participant_id": participant_id,
                "joined_at": datetime.now().isoformat()
            }
            if user_id not in self.user_connections:
                self.user_connections[user_id] = set()
            self.user_connections[user_id].add(websocket)
            
            # Notify others about the new connection
            try:
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
            except Exception as e:
                logger.warning(f"Error broadcasting connection event: {str(e)}")
                
            return True
        except Exception as e:
            logger.error(f"Error connecting WebSocket: {str(e)}")
            return False
    
    def disconnect(self, websocket: WebSocket):
        """Unregister a WebSocket connection"""
        user_id = None
        participant_id = None
        conversation_ids = []
        
        # Find all conversations this websocket is connected to
        for conversation_id, connections in list(self.active_connections.items()):
            if websocket in connections:
                conn_info = connections.get(websocket, {})
                user_id = conn_info.get("user_id")
                participant_id = conn_info.get("participant_id")
                conversation_ids.append(conversation_id)
                
                # Remove from conversation connections
                try:
                    del connections[websocket]
                except KeyError:
                    pass
                    
                # Remove empty conversation entries
                if not connections:
                    try:
                        del self.active_connections[conversation_id]
                    except KeyError:
                        pass
        
        # Remove from user connections
        if user_id and user_id in self.user_connections:
            try:
                self.user_connections[user_id].discard(websocket)
                if not self.user_connections[user_id]:
                    del self.user_connections[user_id]
            except Exception:
                pass
        
        # Notify others about the disconnection
        for conv_id in conversation_ids:
            if user_id and participant_id:
                asyncio.create_task(self._notify_disconnect(conv_id, user_id, participant_id))
    
    async def _notify_disconnect(self, conversation_id, user_id, participant_id):
        """Send disconnect notification to other clients"""
        try:
            await self.broadcast_to_conversation(
                conversation_id,
                {
                    "type": "connection",
                    "event": "disconnected",
                    "user_id": user_id,
                    "participant_id": participant_id,
                    "timestamp": datetime.now().isoformat()
                }
            )
        except Exception as e:
            logger.warning(f"Error broadcasting disconnect event: {str(e)}")
    
    async def broadcast_to_conversation(
        self, 
        conversation_id: str, 
        message: Dict[str, Any],
        exclude: Optional[WebSocket] = None
    ):
        """Broadcast a message to all connections in a conversation"""
        if conversation_id not in self.active_connections:
            return
            
        connections = list(self.active_connections[conversation_id].keys())
        for connection in connections:
            if connection != exclude:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.error(f"Error sending message to client: {str(e)}")
                    self.disconnect(connection)
    
    async def broadcast_to_user(self, user_id: str, message: Dict[str, Any]):
        """Broadcast a message to all connections for a user"""
        if user_id not in self.user_connections:
            return
            
        connections = list(self.user_connections[user_id])
        for connection in connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Error sending message to user: {str(e)}")
                self.disconnect(connection)
    
    def get_active_users_in_conversation(self, conversation_id: str) -> Dict[str, Any]:
        """Get all active users in a conversation"""
        if conversation_id not in self.active_connections:
            return {}
            
        user_info = {}
        for conn_data in self.active_connections[conversation_id].values():
            user_id = conn_data.get("user_id")
            if not user_id:
                continue
                
            if user_id not in user_info:
                user_info[user_id] = {
                    "user_id": user_id,
                    "connection_count": 1,
                    "participants": []
                }
            else:
                user_info[user_id]["connection_count"] += 1
                
            participant_id = conn_data.get("participant_id")
            if participant_id and participant_id not in user_info[user_id]["participants"]:
                user_info[user_id]["participants"].append(participant_id)
                
        return user_info
    
    def get_active_participants_in_conversation(self, conversation_id: str) -> Set[str]:
        """Get all active participants in a conversation"""
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

# Create singleton instance
connection_manager = ConnectionManager()

# Authentication helpers
async def authenticate_connection(
    websocket: WebSocket,
    token: str,
    conversation_id: str,
    participant_id: Optional[str],
    auth_service: AuthService,
    conversation_service: ConversationService
) -> Optional[str]:
    """
    Authenticate a WebSocket connection
    
    Returns user_id if successful, None otherwise
    """
    try:
        # Verify token
        payload = auth_service.verify_token(token)
        user_id = payload.get("sub")
        
        if not user_id:
            await websocket.send_json({
                "type": "error",
                "error": "Invalid authentication token",
                "timestamp": datetime.now().isoformat()
            })
            await websocket.close(code=4001, reason="Authentication failed")
            return None
        
        # Get user
        user = auth_service.get_user_by_id(user_id)
        if not user:
            await websocket.send_json({
                "type": "error",
                "error": "User not found",
                "timestamp": datetime.now().isoformat()
            })
            await websocket.close(code=4001, reason="User not found")
            return None
        
        # Get conversation
        conversation = conversation_service.get_conversation(conversation_id)
        if not conversation:
            await websocket.send_json({
                "type": "error",
                "error": "Conversation not found",
                "timestamp": datetime.now().isoformat()
            })
            await websocket.close(code=4004, reason="Conversation not found")
            return None
        
        # Check access permissions
        if not conversation_service.check_user_access(user_id, conversation_id):
            await websocket.send_json({
                "type": "error",
                "error": "No access to conversation",
                "timestamp": datetime.now().isoformat()
            })
            await websocket.close(code=4003, reason="No access to conversation")
            return None
        
        # Check participant if provided
        if participant_id:
            participant = conversation_service.get_participant(participant_id)
            if not participant or participant.conversation_id != conversation_id:
                await websocket.send_json({
                    "type": "error",
                    "error": "Participant not found in conversation",
                    "timestamp": datetime.now().isoformat()
                })
                await websocket.close(code=4003, reason="Participant not found")
                return None
                
            if not participant.user_id or participant.user_id != user_id:
                await websocket.send_json({
                    "type": "error",
                    "error": "Participant not controlled by user",
                    "timestamp": datetime.now().isoformat()
                })
                await websocket.close(code=4003, reason="Participant not controlled by user")
                return None
        
        return user_id
    
    except Exception as e:
        logger.error(f"Authentication error: {str(e)}")
        await websocket.send_json({
            "type": "error",
            "error": f"Authentication error: {str(e)}",
            "timestamp": datetime.now().isoformat()
        })
        await websocket.close(code=4001, reason="Authentication failed")
        return None

async def send_initial_info(
    websocket: WebSocket,
    conversation_id: str,
    usage_service: UsageService,
    user_id: str
):
    """Send initial information to a new connection"""
    # Send presence information
    active_users = connection_manager.get_active_users_in_conversation(conversation_id)
    presence_payload = {
        "type": "presence",
        "active_users": list(active_users.values()),
        "timestamp": datetime.now().isoformat()
    }
    await websocket.send_json(presence_payload)
    
    # Send usage limits
    usage_info = {
        "can_send_messages": usage_service.can_send_message(user_id),
        "messages_remaining_today": usage_service.get_remaining_daily_messages(user_id),
        "is_premium": usage_service.payment_service.is_premium(user_id)
    }
    usage_payload = {
        "type": "usage_limits",
        "usage": usage_info,
        "timestamp": datetime.now().isoformat()
    }
    await websocket.send_json(usage_payload)

# Main WebSocket handler
async def handle_websocket_connection(
    websocket: WebSocket,
    conversation_id: str,
    token: str,
    participant_id: Optional[str] = None,
    db: Session = None
):
    """Handle a WebSocket connection"""
    # Create DB session if not provided
    close_db = False
    if db is None:
        db = next(get_db())
        close_db = True
    
    try:
        # Accept WebSocket connection
        await websocket.accept()
    except Exception as e:
        logger.error(f"Failed to accept WebSocket connection: {str(e)}")
        return
    
    # Initialize services
    auth_service = AuthService(db)
    conversation_service = ConversationService(db)
    message_service = MessageService(db)
    usage_service = UsageService(db)
    agent_manager = AgentManager(db)
    
    # Authenticate and authorize connection
    user_id = await authenticate_connection(
        websocket, token, conversation_id, participant_id,
        auth_service, conversation_service
    )
    
    if user_id is None:
        return  # Authentication failed
    
    # Register connection
    await connection_manager.connect(websocket, conversation_id, user_id, participant_id)
    
    # Send initial presence and usage info
    await send_initial_info(websocket, conversation_id, usage_service, user_id)
    
    # Main message loop
    try:
        while True:
            # Wait for message
            data = await websocket.receive_text()
            
            # Parse JSON
            try:
                message_data = json.loads(data)
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "error": "Invalid JSON format",
                    "timestamp": datetime.now().isoformat()
                })
                continue
            
            # Get event type
            event_type = message_data.get("type", "message")
            
            # Dispatch to handler
            await event_registry.dispatcher.dispatch(
                event_type,
                websocket=websocket,
                message_data=message_data,
                conversation_id=conversation_id,
                user_id=user_id,
                participant_id=participant_id,
                message_service=message_service,
                usage_service=usage_service,
                agent_manager=agent_manager
            )
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: user {user_id}")
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}")
        await websocket.close(code=1011, reason="Internal server error")
    finally:
        # Clean up
        connection_manager.disconnect(websocket)
        if close_db and db:
            db.close()
        logger.info("Connection closed")