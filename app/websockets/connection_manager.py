import json
import asyncio
import logging
from datetime import datetime
from typing import Dict, Set, Any, Optional, List
from pydantic import BaseModel
from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.auth_service import AuthService
from app.services.conversation_service import ConversationService
from app.services.message_service import MessageService
from app.services.usage_service import UsageService
from app.ai.agent_manager import AgentManager

logger = logging.getLogger(__name__)

# -------------------------------
# Pydantic Schemas
# -------------------------------
class BasePayload(BaseModel):
    type: str
    timestamp: str

class ChatMessage(BaseModel):
    id: int
    content: str
    participant_id: Optional[str]
    character_id: Optional[str]
    character_name: Optional[str]
    user_id: str
    is_ai: bool
    conversation_id: str
    created_at: str

class MessagePayload(BasePayload):
    message: ChatMessage

class TypingPayload(BasePayload):
    user_id: str
    participant_id: Optional[str]
    is_typing: bool

class PresencePayload(BasePayload):
    active_users: List[Any]  # Optionally, define a model for active users

class UsageInfo(BaseModel):
    can_send_messages: bool
    messages_remaining_today: int
    is_premium: bool

class UsageUpdate(BasePayload):
    usage: UsageInfo

class ErrorPayload(BasePayload):
    error: str
    is_premium: Optional[bool] = None

# -------------------------------
# Connection Manager
# -------------------------------
class ConnectionManager:
    """Manager for WebSocket connections."""
    def __init__(self):
        self.active_connections: Dict[str, Dict[WebSocket, Dict[str, Any]]] = {}
        self.user_connections: Dict[str, Set[WebSocket]] = {}
    
    async def connect(
        self, websocket: WebSocket, conversation_id: str, user_id: str, participant_id: Optional[str] = None
    ) -> bool:
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
            # Optionally notify others about the new connection
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
        user_id = None
        participant_id = None
        conversation_ids = []
        for conv_id, connections in list(self.active_connections.items()):
            if websocket in connections:
                conn_info = connections.get(websocket, {})
                user_id = conn_info.get("user_id")
                participant_id = conn_info.get("participant_id")
                conversation_ids.append(conv_id)
                try:
                    del connections[websocket]
                except KeyError:
                    pass
                if not connections:
                    try:
                        del self.active_connections[conv_id]
                    except KeyError:
                        pass
        if user_id and user_id in self.user_connections:
            try:
                self.user_connections[user_id].discard(websocket)
                if not self.user_connections[user_id]:
                    del self.user_connections[user_id]
            except Exception:
                pass
        for conv_id in conversation_ids:
            if user_id and participant_id:
                asyncio.create_task(self._notify_disconnect(conv_id, user_id, participant_id))
    
    async def _notify_disconnect(self, conversation_id, user_id, participant_id):
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
        self, conversation_id: str, message: Dict[str, Any], exclude: Optional[WebSocket] = None
    ):
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
        if conversation_id not in self.active_connections:
            return {}
        user_info = {}
        for conn_data in self.active_connections[conversation_id].values():
            user_id = conn_data.get("user_id")
            if not user_id:
                continue
            if user_id not in user_info:
                user_info[user_id] = {"user_id": user_id, "connection_count": 1, "participants": []}
            else:
                user_info[user_id]["connection_count"] += 1
            participant_id = conn_data.get("participant_id")
            if participant_id and participant_id not in user_info[user_id]["participants"]:
                user_info[user_id]["participants"].append(participant_id)
        return user_info
    
    def get_active_participants_in_conversation(self, conversation_id: str) -> Set[str]:
        if conversation_id not in self.active_connections:
            return set()
        participants = set()
        for conn_data in self.active_connections[conversation_id].values():
            participant_id = conn_data.get("participant_id")
            if participant_id:
                participants.add(participant_id)
        return participants
    
    def get_user_connection_count(self, user_id: str) -> int:
        return len(self.user_connections.get(user_id, set()))

connection_manager = ConnectionManager()

# -------------------------------
# Event Dispatcher
# -------------------------------
class EventDispatcher:
    def __init__(self):
        self.handlers: Dict[str, Any] = {}
    
    def register_handler(self, event_type: str, handler):
        self.handlers[event_type] = handler
    
    async def dispatch(self, event_type: str, **kwargs):
        handler = self.handlers.get(event_type)
        if handler:
            await handler(**kwargs)
        else:
            logger.warning(f"No handler registered for event type: {event_type}")

event_dispatcher = EventDispatcher()

# -------------------------------
# Service-Layer Event Handlers
# -------------------------------
async def handle_message_event(
    websocket: WebSocket,
    message_data: dict,
    conversation_id: str,
    user_id: str,
    participant_id: Optional[str],
    message_service: MessageService,
    usage_service: UsageService
):
    # Process chat message event
    if not usage_service.can_send_message(user_id):
        await websocket.send_json(ErrorPayload(
            type="error",
            error="You have reached your daily message limit",
            is_premium=usage_service.payment_service.is_premium(user_id),
            timestamp=datetime.now().isoformat()
        ).dict())
        return

    content = message_data.get("content", "").strip()
    if not content:
        await websocket.send_json(ErrorPayload(
            type="error",
            error="Message content cannot be empty",
            timestamp=datetime.now().isoformat()
        ).dict())
        return

    usage_service.track_message_sent(user_id, is_from_ai=False)
    db_message = message_service.create_message(
        conversation_id=conversation_id,
        participant_id=participant_id,
        content=content
    )
    if db_message:
        sender_info = message_service.get_sender_info(db_message)
        message_payload = {
            "type": "message",
            "message": {
                "id": db_message.id,
                "content": db_message.content,
                "participant_id": participant_id,
                "character_id": sender_info.get("character_id"),
                "character_name": sender_info.get("character_name"),
                "user_id": sender_info.get("user_id"),
                "is_ai": sender_info.get("is_ai"),
                "conversation_id": conversation_id,
                "created_at": db_message.created_at.isoformat()
            },
            "timestamp": datetime.now().isoformat()
        }
        await connection_manager.broadcast_to_conversation(conversation_id, message_payload)
        await send_usage_update(websocket, usage_service, user_id)
    else:
        await websocket.send_json(ErrorPayload(
            type="error",
            error="Failed to create message",
            timestamp=datetime.now().isoformat()
        ).dict())

async def handle_typing_event(
    websocket: WebSocket,
    message_data: dict,
    conversation_id: str,
    user_id: str,
    participant_id: Optional[str]
):
    payload = {
        "type": "typing",
        "user_id": user_id,
        "participant_id": participant_id,
        "is_typing": message_data.get("is_typing", True),
        "timestamp": datetime.now().isoformat()
    }
    await connection_manager.broadcast_to_conversation(conversation_id, payload, exclude=websocket)

async def handle_presence_event(
    websocket: WebSocket,
    conversation_id: str
):
    active_users = connection_manager.get_active_users_in_conversation(conversation_id)
    presence_payload = PresencePayload(
        type="presence",
        active_users=list(active_users.values()),
        timestamp=datetime.now().isoformat()
    )
    await websocket.send_json(presence_payload.dict())

async def handle_usage_check_event(
    websocket: WebSocket,
    usage_service: UsageService,
    user_id: str
):
    await send_usage_update(websocket, usage_service, user_id)

async def handle_ping_event(
    websocket: WebSocket,
    **kwargs
):
    """Respond to a ping with a pong."""
    pong = {
        "type": "pong",
        "timestamp": datetime.now().isoformat()
    }
    await websocket.send_json(pong)

async def handle_read_event(
    websocket: WebSocket,
    message_data: dict,
    conversation_id: str,
    user_id: str,
    **kwargs
):
    """
    Handle read receipt event.
    Expects 'message_id' in message_data.
    """
    message_id = message_data.get("message_id")
    if not message_id:
        await websocket.send_json(ErrorPayload(
            type="error",
            error="Message ID required for read receipt",
            timestamp=datetime.now().isoformat()
        ).dict())
        return

    # Optionally update database here to mark message as read.
    logger.info(f"User {user_id} read message {message_id}")

    receipt_payload = {
        "type": "read_receipt",
        "message_id": message_id,
        "user_id": user_id,
        "timestamp": datetime.now().isoformat()
    }
    await connection_manager.broadcast_to_conversation(conversation_id, receipt_payload)

async def handle_reaction_event(
    websocket: WebSocket,
    message_data: dict,
    conversation_id: str,
    user_id: str,
    **kwargs
):
    """
    Handle reaction event.
    Expects 'message_id' and 'reaction' in message_data.
    """
    message_id = message_data.get("message_id")
    reaction = message_data.get("reaction")
    if not message_id or not reaction:
        await websocket.send_json(ErrorPayload(
            type="error",
            error="Message ID and reaction are required for reacting",
            timestamp=datetime.now().isoformat()
        ).dict())
        return

    logger.info(f"User {user_id} reacted to message {message_id} with {reaction}")
    reaction_payload = {
        "type": "reaction",
        "message_id": message_id,
        "reaction": reaction,
        "user_id": user_id,
        "timestamp": datetime.now().isoformat()
    }
    await connection_manager.broadcast_to_conversation(conversation_id, reaction_payload)

async def handle_edit_event(
    websocket: WebSocket,
    message_data: dict,
    conversation_id: str,
    user_id: str,
    message_service: MessageService,
    **kwargs
):
    """
    Handle edit message event.
    Expects 'message_id' and 'new_content' in message_data.
    """
    message_id = message_data.get("message_id")
    new_content = message_data.get("new_content", "").strip()
    if not message_id or not new_content:
        await websocket.send_json(ErrorPayload(
            type="error",
            error="Message ID and new content are required for editing",
            timestamp=datetime.now().isoformat()
        ).dict())
        return

    # Update the message using the service layer.
    updated_message = message_service.edit_message(message_id, user_id, new_content)
    if updated_message:
        updated_payload = {
            "type": "message_edit",
            "message": {
                "id": updated_message.id,
                "content": updated_message.content,
                "updated_at": updated_message.updated_at.isoformat()
            },
            "timestamp": datetime.now().isoformat()
        }
        await connection_manager.broadcast_to_conversation(conversation_id, updated_payload)
    else:
        await websocket.send_json(ErrorPayload(
            type="error",
            error="Failed to edit message",
            timestamp=datetime.now().isoformat()
        ).dict())

async def handle_delete_event(
    websocket: WebSocket,
    message_data: dict,
    conversation_id: str,
    user_id: str,
    message_service: MessageService,
    **kwargs
):
    """
    Handle delete message event.
    Expects 'message_id' in message_data.
    """
    message_id = message_data.get("message_id")
    if not message_id:
        await websocket.send_json(ErrorPayload(
            type="error",
            error="Message ID required for deletion",
            timestamp=datetime.now().isoformat()
        ).dict())
        return

    success = message_service.delete_message(message_id, user_id)
    if success:
        deletion_payload = {
            "type": "message_delete",
            "message_id": message_id,
            "timestamp": datetime.now().isoformat()
        }
        await connection_manager.broadcast_to_conversation(conversation_id, deletion_payload)
    else:
        await websocket.send_json(ErrorPayload(
            type="error",
            error="Failed to delete message",
            timestamp=datetime.now().isoformat()
        ).dict())

# -------------------------------
# Additional RPG Event Handlers
# -------------------------------

async def handle_quest_start_event(
    websocket: WebSocket,
    message_data: dict,
    conversation_id: str,
    user_id: str,
    **kwargs
):
    """
    Initiate a new quest.
    Expects 'quest_id' and optionally 'quest_details' in message_data.
    """
    quest_id = message_data.get("quest_id")
    quest_details = message_data.get("quest_details", {})
    if not quest_id:
        await websocket.send_json(ErrorPayload(
            type="error",
            error="Quest ID is required to start a quest",
            timestamp=datetime.now().isoformat()
        ).dict())
        return

    # Here you might update a quest service, log the quest start, etc.
    logger.info(f"User {user_id} started quest {quest_id} with details {quest_details}")

    quest_start_payload = {
        "type": "quest_start",
        "quest_id": quest_id,
        "quest_details": quest_details,
        "user_id": user_id,
        "timestamp": datetime.now().isoformat()
    }
    # Broadcast the quest start event to others in the conversation.
    await connection_manager.broadcast_to_conversation(conversation_id, quest_start_payload)

async def handle_quest_update_event(
    websocket: WebSocket,
    message_data: dict,
    conversation_id: str,
    user_id: str,
    **kwargs
):
    """
    Update the progress or status of an ongoing quest.
    Expects 'quest_id' and 'progress' (or any other update info) in message_data.
    """
    quest_id = message_data.get("quest_id")
    progress = message_data.get("progress")
    if not quest_id or progress is None:
        await websocket.send_json(ErrorPayload(
            type="error",
            error="Quest ID and progress are required for quest update",
            timestamp=datetime.now().isoformat()
        ).dict())
        return

    logger.info(f"User {user_id} updated quest {quest_id} with progress: {progress}")

    quest_update_payload = {
        "type": "quest_update",
        "quest_id": quest_id,
        "progress": progress,
        "user_id": user_id,
        "timestamp": datetime.now().isoformat()
    }
    await connection_manager.broadcast_to_conversation(conversation_id, quest_update_payload)

async def handle_quest_complete_event(
    websocket: WebSocket,
    message_data: dict,
    conversation_id: str,
    user_id: str,
    **kwargs
):
    """
    Mark a quest as complete.
    Expects 'quest_id' in message_data.
    """
    quest_id = message_data.get("quest_id")
    if not quest_id:
        await websocket.send_json(ErrorPayload(
            type="error",
            error="Quest ID is required to complete a quest",
            timestamp=datetime.now().isoformat()
        ).dict())
        return

    logger.info(f"User {user_id} completed quest {quest_id}")

    quest_complete_payload = {
        "type": "quest_complete",
        "quest_id": quest_id,
        "user_id": user_id,
        "timestamp": datetime.now().isoformat()
    }
    await connection_manager.broadcast_to_conversation(conversation_id, quest_complete_payload)

async def handle_dialog_event(
    websocket: WebSocket,
    message_data: dict,
    conversation_id: str,
    user_id: str,
    **kwargs
):
    """
    Open a dialog between the user and an NPC or another user.
    Expects 'dialog_id' and optionally 'dialog_content' in message_data.
    """
    dialog_id = message_data.get("dialog_id")
    dialog_content = message_data.get("dialog_content", {})
    if not dialog_id:
        await websocket.send_json(ErrorPayload(
            type="error",
            error="Dialog ID is required to open a dialog",
            timestamp=datetime.now().isoformat()
        ).dict())
        return

    logger.info(f"User {user_id} initiated dialog {dialog_id} with content {dialog_content}")

    dialog_payload = {
        "type": "dialog",
        "dialog_id": dialog_id,
        "dialog_content": dialog_content,
        "user_id": user_id,
        "timestamp": datetime.now().isoformat()
    }
    await connection_manager.broadcast_to_conversation(conversation_id, dialog_payload)

async def handle_choice_event(
    websocket: WebSocket,
    message_data: dict,
    conversation_id: str,
    user_id: str,
    **kwargs
):
    """
    Process a player's choice within a dialog or quest.
    Expects 'choice_id' and 'selection' in message_data.
    """
    choice_id = message_data.get("choice_id")
    selection = message_data.get("selection")
    if not choice_id or selection is None:
        await websocket.send_json(ErrorPayload(
            type="error",
            error="Choice ID and selection are required for processing a choice",
            timestamp=datetime.now().isoformat()
        ).dict())
        return

    logger.info(f"User {user_id} made choice {choice_id} with selection: {selection}")

    choice_payload = {
        "type": "choice",
        "choice_id": choice_id,
        "selection": selection,
        "user_id": user_id,
        "timestamp": datetime.now().isoformat()
    }
    await connection_manager.broadcast_to_conversation(conversation_id, choice_payload)

# Register event handlers
event_dispatcher.register_handler("message", handle_message_event)
event_dispatcher.register_handler("typing", handle_typing_event)
event_dispatcher.register_handler("presence", handle_presence_event)
event_dispatcher.register_handler("usage_check", handle_usage_check_event)

event_dispatcher.register_handler("ping", handle_ping_event)
event_dispatcher.register_handler("read", handle_read_event)
event_dispatcher.register_handler("reaction", handle_reaction_event)
event_dispatcher.register_handler("edit", handle_edit_event)
event_dispatcher.register_handler("delete", handle_delete_event)

# -------------------------------
# Register RPG Event Handlers
# -------------------------------
event_dispatcher.register_handler("quest_start", handle_quest_start_event)
event_dispatcher.register_handler("quest_update", handle_quest_update_event)
event_dispatcher.register_handler("quest_complete", handle_quest_complete_event)
event_dispatcher.register_handler("dialog", handle_dialog_event)
event_dispatcher.register_handler("choice", handle_choice_event)
# -------------------------------
# Helper: Send Usage Update
# -------------------------------
async def send_usage_update(websocket: WebSocket, usage_service: UsageService, user_id: str):
    usage_info = {
        "can_send_messages": usage_service.can_send_message(user_id),
        "messages_remaining_today": usage_service.get_remaining_daily_messages(user_id),
        "is_premium": usage_service.payment_service.is_premium(user_id)
    }
    payload = UsageUpdate(
        type="usage_update",
        usage=usage_info,
        timestamp=datetime.now().isoformat()
    )
    await websocket.send_json(payload.dict())

# -------------------------------
# Helper: Authentication & Authorization
# -------------------------------
async def authenticate_connection(
    websocket: WebSocket,
    token: str,
    conversation_id: str,
    participant_id: Optional[str],
    auth_service: AuthService,
    conversation_service: ConversationService
) -> Optional[str]:
    try:
        payload = auth_service.verify_token(token)
        user_id = payload.get("sub")
        if not user_id:
            await websocket.send_json(ErrorPayload(
                type="error",
                error="Invalid authentication token",
                timestamp=datetime.now().isoformat()
            ).dict())
            await websocket.close(code=4001, reason="Authentication failed")
            return None
        user = auth_service.get_user_by_id(user_id)
        if not user:
            await websocket.send_json(ErrorPayload(
                type="error",
                error="User not found",
                timestamp=datetime.now().isoformat()
            ).dict())
            await websocket.close(code=4001, reason="User not found")
            return None
        conversation = conversation_service.get_conversation(conversation_id)
        if not conversation:
            await websocket.send_json(ErrorPayload(
                type="error",
                error="Conversation not found",
                timestamp=datetime.now().isoformat()
            ).dict())
            await websocket.close(code=4004, reason="Conversation not found")
            return None
        if not conversation_service.check_user_access(user_id, conversation_id):
            await websocket.send_json(ErrorPayload(
                type="error",
                error="No access to conversation",
                timestamp=datetime.now().isoformat()
            ).dict())
            await websocket.close(code=4003, reason="No access to conversation")
            return None
        if participant_id:
            participant = conversation_service.get_participant(participant_id)
            if not participant or participant.conversation_id != conversation_id:
                await websocket.send_json(ErrorPayload(
                    type="error",
                    error="Participant not found in conversation",
                    timestamp=datetime.now().isoformat()
                ).dict())
                await websocket.close(code=4003, reason="Participant not found")
                return None
            if not participant.user_id or participant.user_id != user_id:
                await websocket.send_json(ErrorPayload(
                    type="error",
                    error="Participant not controlled by user",
                    timestamp=datetime.now().isoformat()
                ).dict())
                await websocket.close(code=4003, reason="Participant not controlled by user")
                return None
        return user_id
    except Exception as e:
        logger.error(f"Authentication error: {str(e)}")
        await websocket.send_json(ErrorPayload(
            type="error",
            error=f"Authentication error: {str(e)}",
            timestamp=datetime.now().isoformat()
        ).dict())
        await websocket.close(code=4001, reason="Authentication failed")
        return None

# -------------------------------
# Helper: Send Initial Info
# -------------------------------
async def send_initial_info(
    websocket: WebSocket,
    conversation_id: str,
    usage_service: UsageService,
    user_id: str
):
    # Send presence info
    await handle_presence_event(websocket, conversation_id)
    # Send usage limits
    usage_info = {
        "can_send_messages": usage_service.can_send_message(user_id),
        "messages_remaining_today": usage_service.get_remaining_daily_messages(user_id),
        "is_premium": usage_service.payment_service.is_premium(user_id)
    }
    usage_payload = UsageUpdate(
        type="usage_limits",
        usage=usage_info,
        timestamp=datetime.now().isoformat()
    )
    await websocket.send_json(usage_payload.dict())

# -------------------------------
# Main WebSocket Handler
# -------------------------------
async def handle_websocket_connection(
    websocket: WebSocket,
    conversation_id: str,
    token: str,
    participant_id: Optional[str] = None,
    db: Session = None
):
    close_db = False
    if db is None:
        db = next(get_db())
        close_db = True

    try:
        await websocket.accept()
    except Exception as e:
        logger.error(f"Failed to accept WebSocket connection: {str(e)}")
        return

    # Initialize services
    auth_service = AuthService(db)
    conversation_service = ConversationService(db)
    message_service = MessageService(db)
    usage_service = UsageService(db)
    agent_manager = AgentManager(db)  # AI manager (not used in these events)

    # Authenticate and authorize connection
    user_id = await authenticate_connection(
        websocket, token, conversation_id, participant_id, auth_service, conversation_service
    )
    if user_id is None:
        return  # Authentication failed

    # Register connection
    await connection_manager.connect(websocket, conversation_id, user_id, participant_id)

    # Send initial presence and usage info
    await send_initial_info(websocket, conversation_id, usage_service, user_id)

    # Main message loop with event dispatching
    try:
        while True:
            data = await websocket.receive_text()
            try:
                message_data = json.loads(data)
            except json.JSONDecodeError:
                await websocket.send_json(ErrorPayload(
                    type="error",
                    error="Invalid JSON format",
                    timestamp=datetime.now().isoformat()
                ).dict())
                continue

            event_type = message_data.get("type", "message")
            await event_dispatcher.dispatch(
                event_type,
                websocket=websocket,
                message_data=message_data,
                conversation_id=conversation_id,
                user_id=user_id,
                participant_id=participant_id,
                message_service=message_service,
                usage_service=usage_service
            )
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: user {user_id}")
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}")
        await websocket.close(code=1011, reason="Internal server error")
    finally:
        connection_manager.disconnect(websocket)
        if close_db and db:
            db.close()
        logger.info("Connection closed")


# import json
# import asyncio
# import logging
# from datetime import datetime
# from typing import Dict, Set, Any, Optional, List
# from pydantic import BaseModel
# from fastapi import WebSocket, WebSocketDisconnect
# from sqlalchemy.orm import Session

# from app.database import get_db
# from app.services.auth_service import AuthService
# from app.services.conversation_service import ConversationService
# from app.services.message_service import MessageService
# from app.services.usage_service import UsageService
# from app.ai.agent_manager import AgentManager

# logger = logging.getLogger(__name__)

# # -------------------------------
# # Pydantic Schemas
# # -------------------------------
# class BasePayload(BaseModel):
#     type: str
#     timestamp: str

# class ChatMessage(BaseModel):
#     id: int
#     content: str
#     participant_id: Optional[str]
#     character_id: Optional[str]
#     character_name: Optional[str]
#     user_id: str
#     is_ai: bool
#     conversation_id: str
#     created_at: str

# class MessagePayload(BasePayload):
#     message: ChatMessage

# class TypingPayload(BasePayload):
#     user_id: str
#     participant_id: Optional[str]
#     is_typing: bool

# class PresencePayload(BasePayload):
#     active_users: List[Any]  # Optionally, create a dedicated model for active users

# class UsageInfo(BaseModel):
#     can_send_messages: bool
#     messages_remaining_today: int
#     is_premium: bool

# class UsageUpdate(BasePayload):
#     usage: UsageInfo

# class ErrorPayload(BasePayload):
#     error: str
#     is_premium: Optional[bool] = None

# # -------------------------------
# # Connection Manager
# # -------------------------------
# class ConnectionManager:
#     """Manager for WebSocket connections"""
    
#     def __init__(self):
#         self.active_connections: Dict[str, Dict[WebSocket, Dict[str, Any]]] = {}
#         self.user_connections: Dict[str, Set[WebSocket]] = {}
    
#     async def connect(
#         self, 
#         websocket: WebSocket, 
#         conversation_id: str,
#         user_id: str,
#         participant_id: Optional[str] = None
#     ) -> bool:
#         try:
#             if conversation_id not in self.active_connections:
#                 self.active_connections[conversation_id] = {}
#             self.active_connections[conversation_id][websocket] = {
#                 "user_id": user_id,
#                 "participant_id": participant_id,
#                 "joined_at": datetime.now().isoformat()
#             }
#             if user_id not in self.user_connections:
#                 self.user_connections[user_id] = set()
#             self.user_connections[user_id].add(websocket)
#             try:
#                 await self.broadcast_to_conversation(
#                     conversation_id,
#                     {
#                         "type": "connection",
#                         "event": "connected",
#                         "user_id": user_id,
#                         "participant_id": participant_id,
#                         "timestamp": datetime.now().isoformat()
#                     },
#                     exclude=websocket
#                 )
#             except Exception as e:
#                 logger.warning(f"Error broadcasting connection event: {str(e)}")
#             return True
#         except Exception as e:
#             logger.error(f"Error connecting WebSocket: {str(e)}")
#             return False
    
#     def disconnect(self, websocket: WebSocket):
#         user_id = None
#         participant_id = None
#         conversation_ids = []
#         for conversation_id, connections in list(self.active_connections.items()):
#             if websocket in connections:
#                 conn_info = connections.get(websocket, {})
#                 user_id = conn_info.get("user_id")
#                 participant_id = conn_info.get("participant_id")
#                 conversation_ids.append(conversation_id)
#                 try:
#                     del connections[websocket]
#                 except KeyError:
#                     pass
#                 if not connections:
#                     try:
#                         del self.active_connections[conversation_id]
#                     except KeyError:
#                         pass
#         if user_id and user_id in self.user_connections:
#             try:
#                 self.user_connections[user_id].discard(websocket)
#                 if not self.user_connections[user_id]:
#                     del self.user_connections[user_id]
#             except Exception:
#                 pass
#         for conv_id in conversation_ids:
#             if user_id and participant_id:
#                 asyncio.create_task(self._notify_disconnect(conv_id, user_id, participant_id))
    
#     async def _notify_disconnect(self, conversation_id, user_id, participant_id):
#         try:
#             await self.broadcast_to_conversation(
#                 conversation_id,
#                 {
#                     "type": "connection",
#                     "event": "disconnected",
#                     "user_id": user_id,
#                     "participant_id": participant_id,
#                     "timestamp": datetime.now().isoformat()
#                 }
#             )
#         except Exception as e:
#             logger.warning(f"Error broadcasting disconnect event: {str(e)}")
    
#     async def broadcast_to_conversation(
#         self, 
#         conversation_id: str, 
#         message: Dict[str, Any],
#         exclude: Optional[WebSocket] = None
#     ):
#         if conversation_id not in self.active_connections:
#             return
#         connections = list(self.active_connections[conversation_id].keys())
#         for connection in connections:
#             if connection != exclude:
#                 try:
#                     await connection.send_json(message)
#                 except Exception as e:
#                     logger.error(f"Error sending message to client: {str(e)}")
#                     self.disconnect(connection)
    
#     async def broadcast_to_user(self, user_id: str, message: Dict[str, Any]):
#         if user_id not in self.user_connections:
#             return
#         connections = list(self.user_connections[user_id])
#         for connection in connections:
#             try:
#                 await connection.send_json(message)
#             except Exception as e:
#                 logger.error(f"Error sending message to user: {str(e)}")
#                 self.disconnect(connection)
    
#     def get_active_users_in_conversation(self, conversation_id: str) -> Dict[str, Any]:
#         if conversation_id not in self.active_connections:
#             return {}
#         user_info = {}
#         for conn_data in self.active_connections[conversation_id].values():
#             user_id = conn_data.get("user_id")
#             if not user_id:
#                 continue
#             if user_id not in user_info:
#                 user_info[user_id] = {
#                     "user_id": user_id,
#                     "connection_count": 1,
#                     "participants": []
#                 }
#             else:
#                 user_info[user_id]["connection_count"] += 1
#             participant_id = conn_data.get("participant_id")
#             if participant_id and participant_id not in user_info[user_id]["participants"]:
#                 user_info[user_id]["participants"].append(participant_id)
#         return user_info
    
#     def get_active_participants_in_conversation(self, conversation_id: str) -> Set[str]:
#         if conversation_id not in self.active_connections:
#             return set()
#         participants = set()
#         for conn_data in self.active_connections[conversation_id].values():
#             participant_id = conn_data.get("participant_id")
#             if participant_id:
#                 participants.add(participant_id)
#         return participants
    
#     def get_user_connection_count(self, user_id: str) -> int:
#         return len(self.user_connections.get(user_id, set()))

# connection_manager = ConnectionManager()

# # -------------------------------
# # Event Dispatcher
# # -------------------------------
# class EventDispatcher:
#     def __init__(self):
#         self.handlers: Dict[str, Any] = {}
    
#     def register_handler(self, event_type: str, handler):
#         self.handlers[event_type] = handler
    
#     async def dispatch(self, event_type: str, **kwargs):
#         handler = self.handlers.get(event_type)
#         if handler:
#             await handler(**kwargs)
#         else:
#             logger.warning(f"No handler registered for event type: {event_type}")

# # Instantiate a global event dispatcher and register event handlers
# event_dispatcher = EventDispatcher()

# # -------------------------------
# # Service-Layer Event Handlers
# # -------------------------------
# async def handle_message_event(
#     websocket: WebSocket,
#     message_data: dict,
#     conversation_id: str,
#     user_id: str,
#     participant_id: Optional[str],
#     message_service: MessageService,
#     usage_service: UsageService
# ):
#     if not usage_service.can_send_message(user_id):
#         await websocket.send_json(ErrorPayload(
#             type="error",
#             error="You have reached your daily message limit",
#             is_premium=usage_service.payment_service.is_premium(user_id),
#             timestamp=datetime.now().isoformat()
#         ).dict())
#         return

#     content = message_data.get("content", "").strip()
#     if not content:
#         await websocket.send_json(ErrorPayload(
#             type="error",
#             error="Message content cannot be empty",
#             timestamp=datetime.now().isoformat()
#         ).dict())
#         return

#     usage_service.track_message_sent(user_id, is_from_ai=False)
#     db_message = message_service.create_message(
#         conversation_id=conversation_id,
#         participant_id=participant_id,
#         content=content
#     )
#     if db_message:
#         sender_info = message_service.get_sender_info(db_message)
#         message_payload = {
#             "type": "message",
#             "message": {
#                 "id": db_message.id,
#                 "content": db_message.content,
#                 "participant_id": participant_id,
#                 "character_id": sender_info.get("character_id"),
#                 "character_name": sender_info.get("character_name"),
#                 "user_id": sender_info.get("user_id"),
#                 "is_ai": sender_info.get("is_ai"),
#                 "conversation_id": conversation_id,
#                 "created_at": db_message.created_at.isoformat()
#             },
#             "timestamp": datetime.now().isoformat()
#         }
#         await connection_manager.broadcast_to_conversation(conversation_id, message_payload)
#         await send_usage_update(websocket, usage_service, user_id)
#     else:
#         await websocket.send_json(ErrorPayload(
#             type="error",
#             error="Failed to create message",
#             timestamp=datetime.now().isoformat()
#         ).dict())

# async def handle_typing_event(
#     websocket: WebSocket,
#     message_data: dict,
#     conversation_id: str,
#     user_id: str,
#     participant_id: Optional[str]
# ):
#     payload = {
#         "type": "typing",
#         "user_id": user_id,
#         "participant_id": participant_id,
#         "is_typing": message_data.get("is_typing", True),
#         "timestamp": datetime.now().isoformat()
#     }
#     await connection_manager.broadcast_to_conversation(conversation_id, payload, exclude=websocket)

# async def handle_presence_event(
#     websocket: WebSocket,
#     conversation_id: str
# ):
#     active_users = connection_manager.get_active_users_in_conversation(conversation_id)
#     presence_payload = PresencePayload(
#         type="presence",
#         active_users=list(active_users.values()),
#         timestamp=datetime.now().isoformat()
#     )
#     await websocket.send_json(presence_payload.dict())

# async def handle_usage_check_event(
#     websocket: WebSocket,
#     usage_service: UsageService,
#     user_id: str
# ):
#     await send_usage_update(websocket, usage_service, user_id)

# # Register event handlers with the dispatcher
# event_dispatcher.register_handler("message", handle_message_event)
# event_dispatcher.register_handler("typing", handle_typing_event)
# event_dispatcher.register_handler("presence", handle_presence_event)
# event_dispatcher.register_handler("usage_check", handle_usage_check_event)

# # -------------------------------
# # Helper Function: send_usage_update
# # -------------------------------
# async def send_usage_update(websocket: WebSocket, usage_service: UsageService, user_id: str):
#     usage_info = {
#         "can_send_messages": usage_service.can_send_message(user_id),
#         "messages_remaining_today": usage_service.get_remaining_daily_messages(user_id),
#         "is_premium": usage_service.payment_service.is_premium(user_id)
#     }
#     payload = UsageUpdate(
#         type="usage_update",
#         usage=usage_info,
#         timestamp=datetime.now().isoformat()
#     )
#     await websocket.send_json(payload.dict())

# # -------------------------------
# # Main WebSocket Handler
# # -------------------------------
# async def handle_websocket_connection(
#     websocket: WebSocket,
#     conversation_id: str,
#     token: str,
#     participant_id: Optional[str] = None,
#     db: Session = None
# ):
#     close_db = False
#     if db is None:
#         db = next(get_db())
#         close_db = True

#     try:
#         await websocket.accept()
#     except Exception as e:
#         logger.error(f"Failed to accept WebSocket connection: {str(e)}")
#         return

#     # Initialize services
#     auth_service = AuthService(db)
#     conversation_service = ConversationService(db)
#     message_service = MessageService(db)
#     usage_service = UsageService(db)
#     agent_manager = AgentManager(db)  # AI manager initialized even if not used now

#     # Authentication and access checks
#     try:
#         payload = auth_service.verify_token(token)
#         user_id = payload.get("sub")
#         if not user_id:
#             await websocket.send_json(ErrorPayload(
#                 type="error",
#                 error="Invalid authentication token",
#                 timestamp=datetime.now().isoformat()
#             ).dict())
#             await websocket.close(code=4001, reason="Authentication failed")
#             return
        
#         user = auth_service.get_user_by_id(user_id)
#         if not user:
#             await websocket.send_json(ErrorPayload(
#                 type="error",
#                 error="User not found",
#                 timestamp=datetime.now().isoformat()
#             ).dict())
#             await websocket.close(code=4001, reason="User not found")
#             return
        
#         conversation = conversation_service.get_conversation(conversation_id)
#         if not conversation:
#             await websocket.send_json(ErrorPayload(
#                 type="error",
#                 error="Conversation not found",
#                 timestamp=datetime.now().isoformat()
#             ).dict())
#             await websocket.close(code=4004, reason="Conversation not found")
#             return
        
#         if not conversation_service.check_user_access(user_id, conversation_id):
#             await websocket.send_json(ErrorPayload(
#                 type="error",
#                 error="No access to conversation",
#                 timestamp=datetime.now().isoformat()
#             ).dict())
#             await websocket.close(code=4003, reason="No access to conversation")
#             return
        
#         if participant_id:
#             participant = conversation_service.get_participant(participant_id)
#             if not participant or participant.conversation_id != conversation_id:
#                 await websocket.send_json(ErrorPayload(
#                     type="error",
#                     error="Participant not found in conversation",
#                     timestamp=datetime.now().isoformat()
#                 ).dict())
#                 await websocket.close(code=4003, reason="Participant not found")
#                 return
#             if not participant.user_id or participant.user_id != user_id:
#                 await websocket.send_json(ErrorPayload(
#                     type="error",
#                     error="Participant not controlled by user",
#                     timestamp=datetime.now().isoformat()
#                 ).dict())
#                 await websocket.close(code=4003, reason="Participant not controlled by user")
#                 return

#     except Exception as e:
#         logger.error(f"Authentication error: {str(e)}")
#         await websocket.send_json(ErrorPayload(
#             type="error",
#             error=f"Authentication error: {str(e)}",
#             timestamp=datetime.now().isoformat()
#         ).dict())
#         await websocket.close(code=4001, reason="Authentication failed")
#         return

#     # Register the connection
#     await connection_manager.connect(
#         websocket=websocket,
#         conversation_id=conversation_id,
#         user_id=user_id,
#         participant_id=participant_id
#     )

#     # Send initial presence and usage info
#     await handle_presence_event(websocket, conversation_id)
#     usage_info = {
#         "can_send_messages": usage_service.can_send_message(user_id),
#         "messages_remaining_today": usage_service.get_remaining_daily_messages(user_id),
#         "is_premium": usage_service.payment_service.is_premium(user_id)
#     }
#     usage_payload = UsageUpdate(
#         type="usage_limits",
#         usage=usage_info,
#         timestamp=datetime.now().isoformat()
#     )
#     await websocket.send_json(usage_payload.dict())

#     # Main message loop with event dispatching
#     try:
#         while True:
#             data = await websocket.receive_text()
#             try:
#                 message_data = json.loads(data)
#             except json.JSONDecodeError:
#                 await websocket.send_json(ErrorPayload(
#                     type="error",
#                     error="Invalid JSON format",
#                     timestamp=datetime.now().isoformat()
#                 ).dict())
#                 continue

#             event_type = message_data.get("type", "message")
#             await event_dispatcher.dispatch(
#                 event_type,
#                 websocket=websocket,
#                 message_data=message_data,
#                 conversation_id=conversation_id,
#                 user_id=user_id,
#                 participant_id=participant_id,
#                 message_service=message_service,
#                 usage_service=usage_service
#             )
#     except WebSocketDisconnect:
#         logger.info(f"WebSocket disconnected: user {user_id}")
#     except Exception as e:
#         logger.error(f"Error processing message: {str(e)}")
#         await websocket.close(code=1011, reason="Internal server error")
#     finally:
#         connection_manager.disconnect(websocket)
#         if close_db and db:
#             db.close()
#         logger.info("Connection closed")



# import json
# import asyncio
# import logging
# from datetime import datetime
# from typing import Dict, Set, Any, Optional, List
# from pydantic import BaseModel
# from fastapi import WebSocket, WebSocketDisconnect
# from sqlalchemy.orm import Session

# from app.database import get_db
# from app.services.auth_service import AuthService
# from app.services.conversation_service import ConversationService
# from app.services.message_service import MessageService
# from app.services.usage_service import UsageService
# from app.ai.agent_manager import AgentManager

# logger = logging.getLogger(__name__)

# # -------------------------------
# # Pydantic Schemas
# # -------------------------------
# class BasePayload(BaseModel):
#     type: str
#     timestamp: str

# class ChatMessage(BaseModel):
#     id: int
#     content: str
#     participant_id: Optional[str]
#     character_id: Optional[str]
#     character_name: Optional[str]
#     user_id: str
#     is_ai: bool
#     conversation_id: str
#     created_at: str

# class MessagePayload(BasePayload):
#     message: ChatMessage

# class TypingPayload(BasePayload):
#     user_id: str
#     participant_id: Optional[str]
#     is_typing: bool

# class PresencePayload(BasePayload):
#     active_users: List[Any]  # Optionally, define a model for active users

# class UsageInfo(BaseModel):
#     can_send_messages: bool
#     messages_remaining_today: int
#     is_premium: bool

# class UsageUpdate(BasePayload):
#     usage: UsageInfo

# class ErrorPayload(BasePayload):
#     error: str
#     is_premium: Optional[bool] = None

# # -------------------------------
# # Connection Manager
# # -------------------------------
# class ConnectionManager:
#     """Manager for WebSocket connections"""
    
#     def __init__(self):
#         self.active_connections: Dict[str, Dict[WebSocket, Dict[str, Any]]] = {}
#         self.user_connections: Dict[str, Set[WebSocket]] = {}
    
#     async def connect(
#         self, 
#         websocket: WebSocket, 
#         conversation_id: str,
#         user_id: str,
#         participant_id: Optional[str] = None
#     ) -> bool:
#         try:
#             if conversation_id not in self.active_connections:
#                 self.active_connections[conversation_id] = {}
#             self.active_connections[conversation_id][websocket] = {
#                 "user_id": user_id,
#                 "participant_id": participant_id,
#                 "joined_at": datetime.now().isoformat()
#             }
#             if user_id not in self.user_connections:
#                 self.user_connections[user_id] = set()
#             self.user_connections[user_id].add(websocket)
#             try:
#                 await self.broadcast_to_conversation(
#                     conversation_id,
#                     {
#                         "type": "connection",
#                         "event": "connected",
#                         "user_id": user_id,
#                         "participant_id": participant_id,
#                         "timestamp": datetime.now().isoformat()
#                     },
#                     exclude=websocket
#                 )
#             except Exception as e:
#                 logger.warning(f"Error broadcasting connection event: {str(e)}")
#             return True
#         except Exception as e:
#             logger.error(f"Error connecting WebSocket: {str(e)}")
#             return False
    
#     def disconnect(self, websocket: WebSocket):
#         user_id = None
#         participant_id = None
#         conversation_ids = []
#         for conversation_id, connections in list(self.active_connections.items()):
#             if websocket in connections:
#                 conn_info = connections.get(websocket, {})
#                 user_id = conn_info.get("user_id")
#                 participant_id = conn_info.get("participant_id")
#                 conversation_ids.append(conversation_id)
#                 try:
#                     del connections[websocket]
#                 except KeyError:
#                     pass
#                 if not connections:
#                     try:
#                         del self.active_connections[conversation_id]
#                     except KeyError:
#                         pass
#         if user_id and user_id in self.user_connections:
#             try:
#                 self.user_connections[user_id].discard(websocket)
#                 if not self.user_connections[user_id]:
#                     del self.user_connections[user_id]
#             except Exception:
#                 pass
#         for conv_id in conversation_ids:
#             if user_id and participant_id:
#                 asyncio.create_task(self._notify_disconnect(conv_id, user_id, participant_id))
    
#     async def _notify_disconnect(self, conversation_id, user_id, participant_id):
#         try:
#             await self.broadcast_to_conversation(
#                 conversation_id,
#                 {
#                     "type": "connection",
#                     "event": "disconnected",
#                     "user_id": user_id,
#                     "participant_id": participant_id,
#                     "timestamp": datetime.now().isoformat()
#                 }
#             )
#         except Exception as e:
#             logger.warning(f"Error broadcasting disconnect event: {str(e)}")
    
#     async def broadcast_to_conversation(
#         self, 
#         conversation_id: str, 
#         message: Dict[str, Any],
#         exclude: Optional[WebSocket] = None
#     ):
#         if conversation_id not in self.active_connections:
#             return
#         connections = list(self.active_connections[conversation_id].keys())
#         for connection in connections:
#             if connection != exclude:
#                 try:
#                     await connection.send_json(message)
#                 except Exception as e:
#                     logger.error(f"Error sending message to client: {str(e)}")
#                     self.disconnect(connection)
    
#     async def broadcast_to_user(self, user_id: str, message: Dict[str, Any]):
#         if user_id not in self.user_connections:
#             return
#         connections = list(self.user_connections[user_id])
#         for connection in connections:
#             try:
#                 await connection.send_json(message)
#             except Exception as e:
#                 logger.error(f"Error sending message to user: {str(e)}")
#                 self.disconnect(connection)
    
#     def get_active_users_in_conversation(self, conversation_id: str) -> Dict[str, Any]:
#         if conversation_id not in self.active_connections:
#             return {}
#         user_info = {}
#         for conn_data in self.active_connections[conversation_id].values():
#             user_id = conn_data.get("user_id")
#             if not user_id:
#                 continue
#             if user_id not in user_info:
#                 user_info[user_id] = {
#                     "user_id": user_id,
#                     "connection_count": 1,
#                     "participants": []
#                 }
#             else:
#                 user_info[user_id]["connection_count"] += 1
#             participant_id = conn_data.get("participant_id")
#             if participant_id and participant_id not in user_info[user_id]["participants"]:
#                 user_info[user_id]["participants"].append(participant_id)
#         return user_info
    
#     def get_active_participants_in_conversation(self, conversation_id: str) -> Set[str]:
#         if conversation_id not in self.active_connections:
#             return set()
#         participants = set()
#         for conn_data in self.active_connections[conversation_id].values():
#             participant_id = conn_data.get("participant_id")
#             if participant_id:
#                 participants.add(participant_id)
#         return participants
    
#     def get_user_connection_count(self, user_id: str) -> int:
#         return len(self.user_connections.get(user_id, set()))

# connection_manager = ConnectionManager()

# # -------------------------------
# # Helper Functions for Message Types
# # -------------------------------
# async def send_usage_update(websocket: WebSocket, usage_service, user_id: str):
#     usage_info = {
#         "can_send_messages": usage_service.can_send_message(user_id),
#         "messages_remaining_today": usage_service.get_remaining_daily_messages(user_id),
#         "is_premium": usage_service.payment_service.is_premium(user_id)
#     }
#     payload = UsageUpdate(
#         type="usage_update",
#         usage=usage_info,
#         timestamp=datetime.now().isoformat()
#     )
#     await websocket.send_json(payload.dict())

# async def handle_chat_message(
#     websocket: WebSocket,
#     message_data: dict,
#     conversation_id: str,
#     user_id: str,
#     participant_id: Optional[str],
#     message_service: MessageService,
#     usage_service: UsageService
# ):
#     # Check if user can send messages
#     if not usage_service.can_send_message(user_id):
#         await websocket.send_json(ErrorPayload(
#             type="error",
#             error="You have reached your daily message limit",
#             is_premium=usage_service.payment_service.is_premium(user_id),
#             timestamp=datetime.now().isoformat()
#         ).dict())
#         return

#     content = message_data.get("content", "").strip()
#     if not content:
#         await websocket.send_json(ErrorPayload(
#             type="error",
#             error="Message content cannot be empty",
#             timestamp=datetime.now().isoformat()
#         ).dict())
#         return

#     # Decrement usage and persist the message
#     usage_service.track_message_sent(user_id, is_from_ai=False)
#     db_message = message_service.create_message(
#         conversation_id=conversation_id,
#         participant_id=participant_id,
#         content=content
#     )
#     if db_message:
#         sender_info = message_service.get_sender_info(db_message)
#         message_payload = {
#             "type": "message",
#             "message": {
#                 "id": db_message.id,
#                 "content": db_message.content,
#                 "participant_id": participant_id,
#                 "character_id": sender_info.get("character_id"),
#                 "character_name": sender_info.get("character_name"),
#                 "user_id": sender_info.get("user_id"),
#                 "is_ai": sender_info.get("is_ai"),
#                 "conversation_id": conversation_id,
#                 "created_at": db_message.created_at.isoformat()
#             },
#             "timestamp": datetime.now().isoformat()
#         }
#         await connection_manager.broadcast_to_conversation(conversation_id, message_payload)
#         await send_usage_update(websocket, usage_service, user_id)
#     else:
#         await websocket.send_json(ErrorPayload(
#             type="error",
#             error="Failed to create message",
#             timestamp=datetime.now().isoformat()
#         ).dict())

# async def handle_typing_message(
#     websocket: WebSocket,
#     message_data: dict,
#     conversation_id: str,
#     user_id: str,
#     participant_id: Optional[str]
# ):
#     payload = {
#         "type": "typing",
#         "user_id": user_id,
#         "participant_id": participant_id,
#         "is_typing": message_data.get("is_typing", True),
#         "timestamp": datetime.now().isoformat()
#     }
#     await connection_manager.broadcast_to_conversation(conversation_id, payload, exclude=websocket)

# async def handle_presence_request(
#     websocket: WebSocket,
#     conversation_id: str
# ):
#     active_users = connection_manager.get_active_users_in_conversation(conversation_id)
#     presence = PresencePayload(
#         type="presence",
#         active_users=list(active_users.values()),
#         timestamp=datetime.now().isoformat()
#     )
#     await websocket.send_json(presence.dict())

# async def handle_usage_check(
#     websocket: WebSocket,
#     usage_service,
#     user_id: str
# ):
#     await send_usage_update(websocket, usage_service, user_id)

# # -------------------------------
# # Main WebSocket Handler
# # -------------------------------
# async def handle_websocket_connection(
#     websocket: WebSocket,
#     conversation_id: str,
#     token: str,
#     participant_id: Optional[str] = None,
#     db: Session = None
# ):
#     close_db = False
#     if db is None:
#         db = next(get_db())
#         close_db = True

#     try:
#         await websocket.accept()
#     except Exception as e:
#         logger.error(f"Failed to accept WebSocket connection: {str(e)}")
#         return

#     # Initialize services
#     auth_service = AuthService(db)
#     conversation_service = ConversationService(db)
#     message_service = MessageService(db)
#     usage_service = UsageService(db)
#     agent_manager = AgentManager(db)  # AI manager initialized though not used here

#     # Authentication and access checks
#     try:
#         payload = auth_service.verify_token(token)
#         user_id = payload.get("sub")
#         if not user_id:
#             await websocket.send_json(ErrorPayload(
#                 type="error",
#                 error="Invalid authentication token",
#                 timestamp=datetime.now().isoformat()
#             ).dict())
#             await websocket.close(code=4001, reason="Authentication failed")
#             return
        
#         user = auth_service.get_user_by_id(user_id)
#         if not user:
#             await websocket.send_json(ErrorPayload(
#                 type="error",
#                 error="User not found",
#                 timestamp=datetime.now().isoformat()
#             ).dict())
#             await websocket.close(code=4001, reason="User not found")
#             return
        
#         conversation = conversation_service.get_conversation(conversation_id)
#         if not conversation:
#             await websocket.send_json(ErrorPayload(
#                 type="error",
#                 error="Conversation not found",
#                 timestamp=datetime.now().isoformat()
#             ).dict())
#             await websocket.close(code=4004, reason="Conversation not found")
#             return
        
#         if not conversation_service.check_user_access(user_id, conversation_id):
#             await websocket.send_json(ErrorPayload(
#                 type="error",
#                 error="No access to conversation",
#                 timestamp=datetime.now().isoformat()
#             ).dict())
#             await websocket.close(code=4003, reason="No access to conversation")
#             return
        
#         if participant_id:
#             participant = conversation_service.get_participant(participant_id)
#             if not participant or participant.conversation_id != conversation_id:
#                 await websocket.send_json(ErrorPayload(
#                     type="error",
#                     error="Participant not found in conversation",
#                     timestamp=datetime.now().isoformat()
#                 ).dict())
#                 await websocket.close(code=4003, reason="Participant not found")
#                 return
#             if not participant.user_id or participant.user_id != user_id:
#                 await websocket.send_json(ErrorPayload(
#                     type="error",
#                     error="Participant not controlled by user",
#                     timestamp=datetime.now().isoformat()
#                 ).dict())
#                 await websocket.close(code=4003, reason="Participant not controlled by user")
#                 return

#     except Exception as e:
#         logger.error(f"Authentication error: {str(e)}")
#         await websocket.send_json(ErrorPayload(
#             type="error",
#             error=f"Authentication error: {str(e)}",
#             timestamp=datetime.now().isoformat()
#         ).dict())
#         await websocket.close(code=4001, reason="Authentication failed")
#         return

#     # Register the connection
#     await connection_manager.connect(
#         websocket=websocket,
#         conversation_id=conversation_id,
#         user_id=user_id,
#         participant_id=participant_id
#     )

#     # Send initial presence info and usage limits
#     await handle_presence_request(websocket, conversation_id)
#     usage_info = {
#         "can_send_messages": usage_service.can_send_message(user_id),
#         "messages_remaining_today": usage_service.get_remaining_daily_messages(user_id),
#         "is_premium": usage_service.payment_service.is_premium(user_id)
#     }
#     usage_payload = UsageUpdate(
#         type="usage_limits",
#         usage=usage_info,
#         timestamp=datetime.now().isoformat()
#     )
#     await websocket.send_json(usage_payload.dict())

#     # Message loop
#     try:
#         while True:
#             data = await websocket.receive_text()
#             try:
#                 message_data = json.loads(data)
#             except json.JSONDecodeError:
#                 await websocket.send_json(ErrorPayload(
#                     type="error",
#                     error="Invalid JSON format",
#                     timestamp=datetime.now().isoformat()
#                 ).dict())
#                 continue

#             message_type = message_data.get("type", "message")

#             if message_type == "message":
#                 await handle_chat_message(
#                     websocket=websocket,
#                     message_data=message_data,
#                     conversation_id=conversation_id,
#                     user_id=user_id,
#                     participant_id=participant_id,
#                     message_service=message_service,
#                     usage_service=usage_service
#                 )
#             elif message_type == "typing":
#                 await handle_typing_message(
#                     websocket=websocket,
#                     message_data=message_data,
#                     conversation_id=conversation_id,
#                     user_id=user_id,
#                     participant_id=participant_id
#                 )
#             elif message_type == "presence":
#                 await handle_presence_request(websocket, conversation_id)
#             elif message_type == "usage_check":
#                 await handle_usage_check(websocket, usage_service, user_id)
#             else:
#                 await websocket.send_json(ErrorPayload(
#                     type="error",
#                     error=f"Unknown message type: {message_type}",
#                     timestamp=datetime.now().isoformat()
#                 ).dict())
#     except WebSocketDisconnect:
#         logger.info(f"WebSocket disconnected: user {user_id}")
#     except Exception as e:
#         logger.error(f"Error processing message: {str(e)}")
#         await websocket.close(code=1011, reason="Internal server error")
#     finally:
#         connection_manager.disconnect(websocket)
#         if close_db and db:
#             db.close()
#         logger.info("Connection closed")


# import json
# from fastapi import WebSocket, WebSocketDisconnect
# from sqlalchemy.orm import Session
# from typing import Dict, Set, Any, Optional
# import logging
# import asyncio
# from datetime import datetime

# from app.ai.agent_manager import AgentManager
# from app.database import get_db
# from app.services.auth_service import AuthService
# from app.services.conversation_service import ConversationService
# from app.services.message_service import MessageService
# from app.services.usage_service import UsageService

# logger = logging.getLogger(__name__)

# # ConnectionManager remains unchanged
# class ConnectionManager:
#     """Manager for WebSocket connections"""
    
#     def __init__(self):
#         # Map of conversation_id -> dict of WebSocket -> participant info
#         self.active_connections: Dict[str, Dict[WebSocket, Dict[str, Any]]] = {}
#         # Map of user_id -> set of WebSocket connections
#         self.user_connections: Dict[str, Set[WebSocket]] = {}
    
#     async def connect(
#         self, 
#         websocket: WebSocket, 
#         conversation_id: str,
#         user_id: str,
#         participant_id: Optional[str] = None
#     ) -> bool:
#         try:
#             if conversation_id not in self.active_connections:
#                 self.active_connections[conversation_id] = {}
#             self.active_connections[conversation_id][websocket] = {
#                 "user_id": user_id,
#                 "participant_id": participant_id,
#                 "joined_at": datetime.now().isoformat()
#             }
#             if user_id not in self.user_connections:
#                 self.user_connections[user_id] = set()
#             self.user_connections[user_id].add(websocket)
#             # Notify other clients about new connection (if needed)
#             try:
#                 await self.broadcast_to_conversation(
#                     conversation_id,
#                     {
#                         "type": "connection",
#                         "event": "connected",
#                         "user_id": user_id,
#                         "participant_id": participant_id,
#                         "timestamp": datetime.now().isoformat()
#                     },
#                     exclude=websocket
#                 )
#             except Exception as e:
#                 logger.warning(f"Error broadcasting connection event: {str(e)}")
#             return True
#         except Exception as e:
#             logger.error(f"Error connecting WebSocket: {str(e)}")
#             return False
    
#     def disconnect(self, websocket: WebSocket):
#         user_id = None
#         participant_id = None
#         conversation_ids = []
#         for conversation_id, connections in list(self.active_connections.items()):
#             if websocket in connections:
#                 conn_info = connections.get(websocket, {})
#                 user_id = conn_info.get("user_id")
#                 participant_id = conn_info.get("participant_id")
#                 conversation_ids.append(conversation_id)
#                 try:
#                     del connections[websocket]
#                 except KeyError:
#                     pass
#                 if not connections:
#                     try:
#                         del self.active_connections[conversation_id]
#                     except KeyError:
#                         pass
#         if user_id and user_id in self.user_connections:
#             try:
#                 self.user_connections[user_id].discard(websocket)
#                 if not self.user_connections[user_id]:
#                     del self.user_connections[user_id]
#             except Exception:
#                 pass
#         for conv_id in conversation_ids:
#             if user_id and participant_id:
#                 asyncio.create_task(self._notify_disconnect(conv_id, user_id, participant_id))
    
#     async def _notify_disconnect(self, conversation_id, user_id, participant_id):
#         try:
#             await self.broadcast_to_conversation(
#                 conversation_id,
#                 {
#                     "type": "connection",
#                     "event": "disconnected",
#                     "user_id": user_id,
#                     "participant_id": participant_id,
#                     "timestamp": datetime.now().isoformat()
#                 }
#             )
#         except Exception as e:
#             logger.warning(f"Error broadcasting disconnect event: {str(e)}")
    
#     async def broadcast_to_conversation(
#         self, 
#         conversation_id: str, 
#         message: Dict[str, Any],
#         exclude: Optional[WebSocket] = None
#     ):
#         if conversation_id not in self.active_connections:
#             return
#         connections = list(self.active_connections[conversation_id].keys())
#         for connection in connections:
#             if connection != exclude:
#                 try:
#                     await connection.send_json(message)
#                 except Exception as e:
#                     logger.error(f"Error sending message to client: {str(e)}")
#                     self.disconnect(connection)
    
#     async def broadcast_to_user(self, user_id: str, message: Dict[str, Any]):
#         if user_id not in self.user_connections:
#             return
#         connections = list(self.user_connections[user_id])
#         for connection in connections:
#             try:
#                 await connection.send_json(message)
#             except Exception as e:
#                 logger.error(f"Error sending message to user: {str(e)}")
#                 self.disconnect(connection)
    
#     def get_active_users_in_conversation(self, conversation_id: str) -> Dict[str, Any]:
#         if conversation_id not in self.active_connections:
#             return {}
#         user_info = {}
#         for conn_data in self.active_connections[conversation_id].values():
#             user_id = conn_data.get("user_id")
#             if not user_id:
#                 continue
#             if user_id not in user_info:
#                 user_info[user_id] = {
#                     "user_id": user_id,
#                     "connection_count": 1,
#                     "participants": []
#                 }
#             else:
#                 user_info[user_id]["connection_count"] += 1
#             participant_id = conn_data.get("participant_id")
#             if participant_id and participant_id not in user_info[user_id]["participants"]:
#                 user_info[user_id]["participants"].append(participant_id)
#         return user_info
    
#     def get_active_participants_in_conversation(self, conversation_id: str) -> Set[str]:
#         if conversation_id not in self.active_connections:
#             return set()
#         participants = set()
#         for conn_data in self.active_connections[conversation_id].values():
#             participant_id = conn_data.get("participant_id")
#             if participant_id:
#                 participants.add(participant_id)
#         return participants
    
#     def get_user_connection_count(self, user_id: str) -> int:
#         return len(self.user_connections.get(user_id, set()))

# # Singleton connection manager
# connection_manager = ConnectionManager()


# # Minimal WebSocket handler for a basic chat app
# async def handle_websocket_connection(
#     websocket: WebSocket,
#     conversation_id: str,
#     token: str,
#     participant_id: Optional[str] = None,
#     db: Session = None
# ):
#     # Create DB session if not provided
#     close_db = False
#     if db is None:
#         db = next(get_db())
#         close_db = True

#     try:
#         await websocket.accept()
#     except Exception as e:
#         logger.error(f"Failed to accept WebSocket connection: {str(e)}")
#         return

#     # Perform initial authentication and conversation checks
#     auth_service = AuthService(db)
#     conversation_service = ConversationService(db)
#     message_service = MessageService(db)
#     usage_service = UsageService(db)
#     agent_manager = AgentManager(db)
    
#     user_id = None
#     try:
#         payload = auth_service.verify_token(token)
#         user_id = payload.get("sub")
#         if not user_id:
#             await websocket.send_json({"type": "error", "error": "Invalid authentication token"})
#             await websocket.close(code=4001, reason="Authentication failed")
#             return
        
#         user = auth_service.get_user_by_id(user_id)
#         if not user:
#             await websocket.send_json({"type": "error", "error": "User not found"})
#             await websocket.close(code=4001, reason="User not found")
#             return
        
#         conversation = conversation_service.get_conversation(conversation_id)
#         if not conversation:
#             await websocket.send_json({"type": "error", "error": "Conversation not found"})
#             await websocket.close(code=4004, reason="Conversation not found")
#             return
        
#         if not conversation_service.check_user_access(user_id, conversation_id):
#             await websocket.send_json({"type": "error", "error": "No access to conversation"})
#             await websocket.close(code=4003, reason="No access to conversation")
#             return
        
#         if participant_id:
#             participant = conversation_service.get_participant(participant_id)
#             if not participant or participant.conversation_id != conversation_id:
#                 await websocket.send_json({"type": "error", "error": "Participant not found in conversation"})
#                 await websocket.close(code=4003, reason="Participant not found")
#                 return
#             if not participant.user_id or participant.user_id != user_id:
#                 await websocket.send_json({"type": "error", "error": "Participant not controlled by user"})
#                 await websocket.close(code=4003, reason="Participant not controlled by user")
#                 return
#     except Exception as e:
#         logger.error(f"Authentication error: {str(e)}")
#         await websocket.send_json({"type": "error", "error": f"Authentication error: {str(e)}"})
#         await websocket.close(code=4001, reason="Authentication failed")
#         return

#     # Register the connection with the ConnectionManager
#     await connection_manager.connect(
#         websocket=websocket,
#         conversation_id=conversation_id,
#         user_id=user_id,
#         participant_id=participant_id
#     )

#     active_users = connection_manager.get_active_users_in_conversation(conversation_id)
#     await websocket.send_json({
#         "type": "presence",
#         "active_users": list(active_users.values()),
#         "timestamp": datetime.now().isoformat()
#     })

#     usage_info = {
#     "can_send_messages": usage_service.can_send_message(user_id),
#     "messages_remaining_today": usage_service.get_remaining_daily_messages(user_id),
#     "is_premium": usage_service.payment_service.is_premium(user_id)
#     }
#     await websocket.send_json({
#         "type": "usage_limits",
#         "limits": usage_info,
#         "timestamp": datetime.now().isoformat()
#     })

#     # Basic message loop: receive text and broadcast to all in the conversation
#     try:
#         while True:
#             data = await websocket.receive_text()
#             try:
#                 message_data = json.loads(data)
#             except json.JSONDecodeError:
#                 await websocket.send_json({
#                     "type": "error",
#                     "error": "Invalid JSON format",
#                     "timestamp": datetime.now().isoformat()
#                 })
#                 continue

#             message_type = message_data.get("type", "message")

#             if message_type == "message":
#                 if not usage_service.can_send_message(user_id):
#                     await websocket.send_json({
#                         "type": "error",
#                         "error": "You have reached your daily message limit",
#                         "is_premium": usage_service.payment_service.is_premium(user_id),
#                         "timestamp": datetime.now().isoformat()
#                     })
#                     continue

#                 content = message_data.get("content", "").strip()
#                 if not content:
#                     await websocket.send_json({
#                         "type": "error",
#                         "error": "Message content cannot be empty",
#                         "timestamp": datetime.now().isoformat()
#                     })
#                     continue

#                 usage_service.track_message_sent(user_id, is_from_ai=False)

#                 db_message = message_service.create_message(
#                     conversation_id=conversation_id,
#                     participant_id=participant_id,
#                     content=content
#                 )
#                 if db_message:
#                     # Get sender information from the database message
#                     sender_info = message_service.get_sender_info(db_message)
                    
#                     # Format the message payload for broadcasting
#                     message_payload = {
#                         "type": "message",
#                         "message": {
#                             "id": db_message.id,
#                             "content": db_message.content,
#                             "participant_id": participant_id,
#                             "character_id": sender_info.get("character_id"),
#                             "character_name": sender_info.get("character_name"),
#                             "user_id": sender_info.get("user_id"),
#                             "is_ai": sender_info.get("is_ai"),
#                             "conversation_id": conversation_id,
#                             "created_at": db_message.created_at.isoformat()
#                         },
#                         "timestamp": datetime.now().isoformat()
#                     }
#                 await connection_manager.broadcast_to_conversation(conversation_id, message_payload)

#                 updated_usage = {
#                     "can_send_messages": usage_service.can_send_message(user_id),
#                     "messages_remaining_today": usage_service.get_remaining_daily_messages(user_id),
#                     "is_premium": usage_service.payment_service.is_premium(user_id)
#                 }
#                 await websocket.send_json({
#                     "type": "usage_update",
#                     "usage": updated_usage,
#                     "timestamp": datetime.now().isoformat()
#                 })

#             elif message_type == "typing":
#                 await connection_manager.broadcast_to_conversation(
#                     conversation_id,
#                     {
#                         "type": "typing",
#                         "user_id": user_id,
#                         "participant_id": participant_id,
#                         "is_typing": message_data.get("is_typing", True),
#                         "timestamp": datetime.now().isoformat()
#                     },
#                     exclude=websocket
#                 )
#             elif message_type == "presence":
#                 # Client requests current presence info
#                 active_users = connection_manager.get_active_users_in_conversation(conversation_id)
#                 await websocket.send_json({
#                     "type": "presence",
#                     "active_users": list(active_users.values()),
#                     "timestamp": datetime.now().isoformat()
#                 })

#             elif message_type == "usage_check":
#                 # Client requests updated usage info
#                 usage_info = {
#                     "can_send_messages": usage_service.can_send_message(user_id),
#                     "messages_remaining_today": usage_service.get_remaining_daily_messages(user_id),
#                     "is_premium": usage_service.payment_service.is_premium(user_id)
#                 }
#                 await websocket.send_json({
#                     "type": "usage_limits",
#                     "limits": usage_info,
#                     "timestamp": datetime.now().isoformat()
#                 })
#             else:
#                 await websocket.send_json({
#                     "type": "error",
#                     "error": f"Unknown message type: {message_type}",
#                     "timestamp": datetime.now().isoformat()
#                 })

#     except WebSocketDisconnect:
#         logger.info(f"WebSocket disconnected: user {user_id}")
#     except Exception as e:
#         logger.error(f"Error processing message: {str(e)}")
#         await websocket.close(code=1011, reason="Internal server error")
#     finally:
#         connection_manager.disconnect(websocket)
#         if close_db and db:
#             db.close()
#         logger.info("Connection closed")
