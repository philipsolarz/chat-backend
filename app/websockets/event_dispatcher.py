# app/websockets/event_dispatcher.py
import logging
import json
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional, Callable, Awaitable
from fastapi import WebSocket

from app.services.message_service import MessageService
from app.services.usage_service import UsageService
from app.ai.agent_manager import AgentManager

logger = logging.getLogger(__name__)

class EventDispatcher:
    """Dispatches WebSocket events to appropriate handlers based on event type"""
    
    def __init__(self):
        self.handlers: Dict[str, Callable] = {}
    
    def register_handler(self, event_type: str, handler: Callable):
        """Register a handler function for an event type"""
        self.handlers[event_type] = handler
    
    async def dispatch(self, event_type: str, **kwargs):
        """Dispatch an event to its registered handler"""
        handler = self.handlers.get(event_type)
        if handler:
            try:
                await handler(**kwargs)
            except Exception as e:
                logger.error(f"Error in event handler for {event_type}: {str(e)}")
                websocket = kwargs.get("websocket")
                if websocket:
                    await websocket.send_json({
                        "type": "error",
                        "error": f"Error processing {event_type}: {str(e)}",
                        "timestamp": datetime.now().isoformat()
                    })
        else:
            logger.warning(f"No handler registered for event type: {event_type}")
            websocket = kwargs.get("websocket")
            if websocket:
                await websocket.send_json({
                    "type": "error",
                    "error": f"Unknown event type: {event_type}",
                    "timestamp": datetime.now().isoformat()
                })

# Create EventHandler registry 
class EventRegistry:
    """Registry for all supported event handlers"""
    
    def __init__(self):
        self.dispatcher = EventDispatcher()
        self._setup_handlers()
    
    def _setup_handlers(self):
        """Register all supported event handlers"""
        # Core chat events
        self.dispatcher.register_handler("message", self.handle_message_event)
        self.dispatcher.register_handler("typing", self.handle_typing_event)
        self.dispatcher.register_handler("presence", self.handle_presence_event)
        self.dispatcher.register_handler("usage_check", self.handle_usage_check_event)
        self.dispatcher.register_handler("ping", self.handle_ping_event)
        
        # Message interaction events
        self.dispatcher.register_handler("read", self.handle_read_event)
        self.dispatcher.register_handler("reaction", self.handle_reaction_event)
        self.dispatcher.register_handler("edit", self.handle_edit_event)
        self.dispatcher.register_handler("delete", self.handle_delete_event)
        
        # RPG-style events
        self.dispatcher.register_handler("quest_start", self.handle_quest_start_event)
        self.dispatcher.register_handler("quest_update", self.handle_quest_update_event)
        self.dispatcher.register_handler("quest_complete", self.handle_quest_complete_event)
        self.dispatcher.register_handler("dialog", self.handle_dialog_event)
        self.dispatcher.register_handler("choice", self.handle_choice_event)
    
    async def handle_message_event(
        self,
        websocket: WebSocket,
        message_data: dict,
        conversation_id: str,
        user_id: str,
        participant_id: Optional[str],
        message_service: MessageService,
        usage_service: UsageService,
        agent_manager: Optional[AgentManager] = None
    ):
        """Handle a chat message event"""
        # First check if user can send messages
        if not usage_service.can_send_message(user_id):
            await websocket.send_json({
                "type": "error",
                "error": "You have reached your daily message limit",
                "is_premium": usage_service.payment_service.is_premium(user_id),
                "timestamp": datetime.now().isoformat()
            })
            return

        content = message_data.get("content", "").strip()
        if not content:
            await websocket.send_json({
                "type": "error",
                "error": "Message content cannot be empty",
                "timestamp": datetime.now().isoformat()
            })
            return
            
        # Transform message based on character if agent_manager is available
        transformed_content = content
        if agent_manager and participant_id:
            from app.services.conversation_service import ConversationService
            from app.database import get_db
            
            # Get the participant to find the character
            conversation_service = ConversationService(next(get_db()))
            participant = conversation_service.get_participant(participant_id)
            
            if participant and participant.character_id:
                try:
                    transformed_content = await agent_manager.transform_message(
                        content, participant.character_id
                    )
                    if not transformed_content:
                        transformed_content = content  # Fallback
                except Exception as e:
                    logger.error(f"Error transforming message: {str(e)}")
                    # Continue with original content

        # Track message in usage
        usage_service.track_message_sent(user_id, is_from_ai=False)
        
        # Create the message
        db_message = message_service.create_message(
            conversation_id=conversation_id,
            participant_id=participant_id,
            content=transformed_content
        )
        
        if db_message:
            # Get sender info
            sender_info = message_service.get_sender_info(db_message)
            
            # Broadcast the message
            from app.websockets.connection_manager import connection_manager
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
            
            # Update usage info
            await self.send_usage_update(websocket, usage_service, user_id)
            
            # Process AI responses if agent_manager is available
            if agent_manager:
                asyncio.create_task(self.process_ai_responses(
                    agent_manager=agent_manager,
                    conversation_id=conversation_id,
                    participant_id=participant_id,
                    user_id=user_id,
                    usage_service=usage_service
                ))
        else:
            await websocket.send_json({
                "type": "error",
                "error": "Failed to create message",
                "timestamp": datetime.now().isoformat()
            })
    
    async def process_ai_responses(
        self,
        agent_manager: AgentManager,
        conversation_id: str,
        participant_id: str,
        user_id: str,
        usage_service: UsageService
    ):
        """Process AI agent responses in the background"""
        try:
            # Get responses from AI agents
            responses = await agent_manager.process_new_message(
                conversation_id=conversation_id,
                participant_id=participant_id
            )
            
            # Track AI responses in usage
            for _ in responses:
                usage_service.track_message_sent(user_id, is_from_ai=True)
        except Exception as e:
            logger.error(f"Error processing AI responses: {str(e)}")
    
    async def handle_typing_event(
        self,
        websocket: WebSocket,
        message_data: dict,
        conversation_id: str,
        user_id: str,
        participant_id: Optional[str],
        **kwargs
    ):
        """Handle a typing notification event"""
        from app.websockets.connection_manager import connection_manager
        
        payload = {
            "type": "typing",
            "user_id": user_id,
            "participant_id": participant_id,
            "is_typing": message_data.get("is_typing", True),
            "timestamp": datetime.now().isoformat()
        }
        await connection_manager.broadcast_to_conversation(
            conversation_id, payload, exclude=websocket
        )
    
    async def handle_presence_event(
        self,
        websocket: WebSocket,
        conversation_id: str,
        **kwargs
    ):
        """Handle a presence request event"""
        from app.websockets.connection_manager import connection_manager
        
        active_users = connection_manager.get_active_users_in_conversation(conversation_id)
        presence_payload = {
            "type": "presence",
            "active_users": list(active_users.values()),
            "timestamp": datetime.now().isoformat()
        }
        await websocket.send_json(presence_payload)
    
    async def handle_usage_check_event(
        self,
        websocket: WebSocket,
        usage_service: UsageService,
        user_id: str,
        **kwargs
    ):
        """Handle a usage check event"""
        await self.send_usage_update(websocket, usage_service, user_id)
    
    async def handle_ping_event(
        self,
        websocket: WebSocket,
        **kwargs
    ):
        """Handle a ping event"""
        await websocket.send_json({
            "type": "pong",
            "timestamp": datetime.now().isoformat()
        })
    
    async def send_usage_update(
        self, 
        websocket: WebSocket, 
        usage_service: UsageService, 
        user_id: str
    ):
        """Send updated usage info to the client"""
        usage_info = {
            "can_send_messages": usage_service.can_send_message(user_id),
            "messages_remaining_today": usage_service.get_remaining_daily_messages(user_id),
            "is_premium": usage_service.payment_service.is_premium(user_id)
        }
        payload = {
            "type": "usage_update",
            "usage": usage_info,
            "timestamp": datetime.now().isoformat()
        }
        await websocket.send_json(payload)
    
    async def handle_read_event(
        self,
        websocket: WebSocket,
        message_data: dict,
        conversation_id: str,
        user_id: str,
        **kwargs
    ):
        """Handle a read receipt event"""
        message_id = message_data.get("message_id")
        if not message_id:
            await websocket.send_json({
                "type": "error",
                "error": "Message ID required for read receipt",
                "timestamp": datetime.now().isoformat()
            })
            return
            
        # Log the read receipt (optional: store in database)
        logger.info(f"User {user_id} read message {message_id}")
        
        # Broadcast the read receipt
        from app.websockets.connection_manager import connection_manager
        
        receipt_payload = {
            "type": "read_receipt",
            "message_id": message_id,
            "user_id": user_id,
            "timestamp": datetime.now().isoformat()
        }
        await connection_manager.broadcast_to_conversation(conversation_id, receipt_payload)
    
    async def handle_reaction_event(
        self,
        websocket: WebSocket,
        message_data: dict,
        conversation_id: str,
        user_id: str,
        **kwargs
    ):
        """Handle a message reaction event"""
        message_id = message_data.get("message_id")
        reaction = message_data.get("reaction")
        
        if not message_id or not reaction:
            await websocket.send_json({
                "type": "error",
                "error": "Message ID and reaction are required",
                "timestamp": datetime.now().isoformat()
            })
            return
            
        # Log the reaction (optional: store in database)
        logger.info(f"User {user_id} reacted to message {message_id} with {reaction}")
        
        # Broadcast the reaction
        from app.websockets.connection_manager import connection_manager
        
        reaction_payload = {
            "type": "reaction",
            "message_id": message_id,
            "reaction": reaction,
            "user_id": user_id,
            "timestamp": datetime.now().isoformat()
        }
        await connection_manager.broadcast_to_conversation(conversation_id, reaction_payload)
    
    async def handle_edit_event(
        self,
        websocket: WebSocket,
        message_data: dict,
        conversation_id: str,
        user_id: str,
        message_service: MessageService,
        **kwargs
    ):
        """Handle a message edit event"""
        message_id = message_data.get("message_id")
        new_content = message_data.get("content", "").strip()
        
        if not message_id or not new_content:
            await websocket.send_json({
                "type": "error",
                "error": "Message ID and new content are required",
                "timestamp": datetime.now().isoformat()
            })
            return
            
        # Update the message
        message = message_service.get_message(message_id)
        if not message:
            await websocket.send_json({
                "type": "error",
                "error": "Message not found",
                "timestamp": datetime.now().isoformat()
            })
            return
            
        # Check ownership (only the sender can edit)
        sender_info = message_service.get_sender_info(message)
        if sender_info.get("user_id") != user_id:
            await websocket.send_json({
                "type": "error",
                "error": "You can only edit your own messages",
                "timestamp": datetime.now().isoformat()
            })
            return
            
        # Update the message
        updated_message = message_service.update_message(message_id, new_content)
        if not updated_message:
            await websocket.send_json({
                "type": "error",
                "error": "Failed to update message",
                "timestamp": datetime.now().isoformat()
            })
            return
            
        # Broadcast the edit
        from app.websockets.connection_manager import connection_manager
        
        edit_payload = {
            "type": "message_edit",
            "message_id": message_id,
            "content": new_content,
            "user_id": user_id,
            "timestamp": datetime.now().isoformat()
        }
        await connection_manager.broadcast_to_conversation(conversation_id, edit_payload)
    
    async def handle_delete_event(
        self,
        websocket: WebSocket,
        message_data: dict,
        conversation_id: str,
        user_id: str,
        message_service: MessageService,
        **kwargs
    ):
        """Handle a message delete event"""
        message_id = message_data.get("message_id")
        
        if not message_id:
            await websocket.send_json({
                "type": "error",
                "error": "Message ID required for deletion",
                "timestamp": datetime.now().isoformat()
            })
            return
            
        # Get the message
        message = message_service.get_message(message_id)
        if not message:
            await websocket.send_json({
                "type": "error",
                "error": "Message not found",
                "timestamp": datetime.now().isoformat()
            })
            return
            
        # Check ownership (only the sender can delete)
        sender_info = message_service.get_sender_info(message)
        if sender_info.get("user_id") != user_id:
            await websocket.send_json({
                "type": "error",
                "error": "You can only delete your own messages",
                "timestamp": datetime.now().isoformat()
            })
            return
            
        # Delete the message
        success = message_service.delete_message(message_id)
        if not success:
            await websocket.send_json({
                "type": "error",
                "error": "Failed to delete message",
                "timestamp": datetime.now().isoformat()
            })
            return
            
        # Broadcast the deletion
        from app.websockets.connection_manager import connection_manager
        
        delete_payload = {
            "type": "message_delete",
            "message_id": message_id,
            "user_id": user_id,
            "timestamp": datetime.now().isoformat()
        }
        await connection_manager.broadcast_to_conversation(conversation_id, delete_payload)
    
    # RPG-style events
    
    async def handle_quest_start_event(
        self,
        websocket: WebSocket,
        message_data: dict,
        conversation_id: str,
        user_id: str,
        **kwargs
    ):
        """Handle a quest start event"""
        quest_id = message_data.get("quest_id")
        quest_details = message_data.get("quest_details", {})
        
        if not quest_id:
            await websocket.send_json({
                "type": "error",
                "error": "Quest ID is required",
                "timestamp": datetime.now().isoformat()
            })
            return
            
        # Log the quest start (optional: store in database)
        logger.info(f"User {user_id} started quest {quest_id} with details {quest_details}")
        
        # Broadcast the quest start
        from app.websockets.connection_manager import connection_manager
        
        quest_payload = {
            "type": "quest_start",
            "quest_id": quest_id,
            "quest_details": quest_details,
            "user_id": user_id,
            "timestamp": datetime.now().isoformat()
        }
        await connection_manager.broadcast_to_conversation(conversation_id, quest_payload)
    
    async def handle_quest_update_event(
        self,
        websocket: WebSocket,
        message_data: dict,
        conversation_id: str,
        user_id: str,
        **kwargs
    ):
        """Handle a quest update event"""
        quest_id = message_data.get("quest_id")
        progress = message_data.get("progress")
        
        if not quest_id or progress is None:
            await websocket.send_json({
                "type": "error",
                "error": "Quest ID and progress are required",
                "timestamp": datetime.now().isoformat()
            })
            return
            
        # Log the quest update (optional: store in database)
        logger.info(f"User {user_id} updated quest {quest_id} with progress {progress}")
        
        # Broadcast the quest update
        from app.websockets.connection_manager import connection_manager
        
        update_payload = {
            "type": "quest_update",
            "quest_id": quest_id,
            "progress": progress,
            "user_id": user_id,
            "timestamp": datetime.now().isoformat()
        }
        await connection_manager.broadcast_to_conversation(conversation_id, update_payload)
    
    async def handle_quest_complete_event(
        self,
        websocket: WebSocket,
        message_data: dict,
        conversation_id: str,
        user_id: str,
        **kwargs
    ):
        """Handle a quest complete event"""
        quest_id = message_data.get("quest_id")
        
        if not quest_id:
            await websocket.send_json({
                "type": "error",
                "error": "Quest ID is required",
                "timestamp": datetime.now().isoformat()
            })
            return
            
        # Log the quest completion (optional: store in database)
        logger.info(f"User {user_id} completed quest {quest_id}")
        
        # Broadcast the quest completion
        from app.websockets.connection_manager import connection_manager
        
        complete_payload = {
            "type": "quest_complete",
            "quest_id": quest_id,
            "user_id": user_id,
            "timestamp": datetime.now().isoformat()
        }
        await connection_manager.broadcast_to_conversation(conversation_id, complete_payload)
    
    async def handle_dialog_event(
        self,
        websocket: WebSocket,
        message_data: dict,
        conversation_id: str,
        user_id: str,
        **kwargs
    ):
        """Handle a dialog event"""
        dialog_id = message_data.get("dialog_id")
        dialog_content = message_data.get("dialog_content", {})
        
        if not dialog_id:
            await websocket.send_json({
                "type": "error",
                "error": "Dialog ID is required",
                "timestamp": datetime.now().isoformat()
            })
            return
            
        # Log the dialog (optional: store in database)
        logger.info(f"User {user_id} initiated dialog {dialog_id} with content {dialog_content}")
        
        # Broadcast the dialog
        from app.websockets.connection_manager import connection_manager
        
        dialog_payload = {
            "type": "dialog",
            "dialog_id": dialog_id,
            "dialog_content": dialog_content,
            "user_id": user_id,
            "timestamp": datetime.now().isoformat()
        }
        await connection_manager.broadcast_to_conversation(conversation_id, dialog_payload)
    
    async def handle_choice_event(
        self,
        websocket: WebSocket,
        message_data: dict,
        conversation_id: str,
        user_id: str,
        **kwargs
    ):
        """Handle a choice event"""
        choice_id = message_data.get("choice_id")
        selection = message_data.get("selection")
        
        if not choice_id or selection is None:
            await websocket.send_json({
                "type": "error",
                "error": "Choice ID and selection are required",
                "timestamp": datetime.now().isoformat()
            })
            return
            
        # Log the choice (optional: store in database)
        logger.info(f"User {user_id} made choice {choice_id} with selection {selection}")
        
        # Broadcast the choice
        from app.websockets.connection_manager import connection_manager
        
        choice_payload = {
            "type": "choice",
            "choice_id": choice_id,
            "selection": selection,
            "user_id": user_id,
            "timestamp": datetime.now().isoformat()
        }
        await connection_manager.broadcast_to_conversation(conversation_id, choice_payload)

# Create a global event registry
event_registry = EventRegistry()