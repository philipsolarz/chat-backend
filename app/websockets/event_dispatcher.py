import json
import asyncio
from datetime import datetime
from typing import Dict, Any, Callable, Awaitable

from fastapi import WebSocket
from app.websockets.connection_manager import connection_manager
import logging

logger = logging.getLogger(__name__)

class EventDispatcher:
    """Dispatches WebSocket events to appropriate handlers based on event type."""
    
    def __init__(self):
        self.handlers: Dict[str, Callable[..., Awaitable[None]]] = {}
    
    def register_handler(self, event_type: str, handler: Callable[..., Awaitable[None]]):
        self.handlers[event_type] = handler
    
    async def dispatch(self, websocket: WebSocket, event_data: dict, agent_manager: Any, world_id: str, character_id: str):
        event_type = event_data.get("type")
        handler = self.handlers.get(event_type)
        if handler:
            try:
                await handler(websocket, event_data, agent_manager, world_id, character_id)
            except Exception as e:
                logger.error(f"Error in event handler for {event_type}: {str(e)}")
                await websocket.send_json({
                    "type": "error",
                    "error": f"Error processing {event_type}: {str(e)}",
                    "timestamp": datetime.now().isoformat()
                })
        else:
            logger.warning(f"No handler registered for event type: {event_type}")
            await websocket.send_json({
                "type": "error",
                "error": f"Unknown event type: {event_type}",
                "timestamp": datetime.now().isoformat()
            })

class EventRegistry:
    """Registry for all supported event handlers."""
    
    def __init__(self):
        self.dispatcher = EventDispatcher()
        self._setup_handlers()
    
    def _setup_handlers(self):
        # Register supported event handlers
        self.dispatcher.register_handler("message", self.handle_message)
        self.dispatcher.register_handler("ping", self.handle_ping)
        # Dummy: you could add a "usage" or other event types here.
        # For example, add a "reach" field (e.g., "global", "zone_id", or "private")
        # to outgoing payloads if needed; for now, all messages are global.
    
    async def handle_message(self, websocket: WebSocket, event_data: dict, agent_manager: Any, world_id: str, character_id: str):
        """Handle message events.
        
        All messages coming from the client are processed through the GameMaster.
        If the agent_manager.process_game_master_message returns True, it is interpreted
        as a question and a system event is sent to the client with "This is a question".
        Otherwise, the message is broadcast globally.
        """
        content = event_data.get("content", "").strip()
        if not content:
            await websocket.send_json({
                "type": "error",
                "error": "Message content cannot be empty",
                "timestamp": datetime.now().isoformat()
            })
            return
        
        # Process the message through the GameMaster.
        is_question = await agent_manager.process_game_master_message(content)
        print(is_question)
        if is_question.is_question:
            payload = {
                "type": "system",
                "content": "This is a question",
                "timestamp": datetime.now().isoformat(),
                # "reach": "global"  # Dummy field; all messages are global for now.
            }
            await connection_manager.broadcast_to_world(world_id, payload)
        else:
            payload = {
                "type": "message",
                "character_id": character_id,
                "content": content,
                "timestamp": datetime.now().isoformat(),
                # "reach": "global"  # Dummy field; all messages are global for now.
            }
            # Broadcast the message to all connected clients.
            await connection_manager.broadcast_to_world(world_id, payload)
    
    async def handle_ping(self, websocket: WebSocket, event_data: dict, agent_manager: Any, character_id: str):
        """Respond to ping events with a pong."""
        payload = {
            "type": "pong",
            "timestamp": datetime.now().isoformat(),
            # "reach": "global"  # Dummy field.
        }
        await websocket.send_json(payload)

# Global event registry instance.
event_registry = EventRegistry()



# # app/websockets/event_dispatcher.py
# import logging
# import json
# import asyncio
# from datetime import datetime
# from typing import Dict, Any, Optional, Callable, Awaitable
# from fastapi import WebSocket
# from sqlalchemy.orm import Session
# from app.models.game_event import EventType, EventScope
# from app.services.event_service import EventService
# from app.services.usage_service import UsageService
# from app.websockets.connection_manager import connection_manager

# logger = logging.getLogger(__name__)

# # Standalone helper function for sending usage updates
# async def send_usage_update(websocket: WebSocket, usage_service: UsageService, user_id: str):
#     """Send updated usage info to the client"""
#     usage_info = {
#         "can_send_messages": usage_service.can_send_message(user_id),
#         "messages_remaining_today": usage_service.get_remaining_daily_messages(user_id),
#         "is_premium": usage_service.payment_service.is_premium(user_id)
#     }
#     payload = {
#         "type": "usage_update",
#         "usage": usage_info,
#         "timestamp": datetime.now().isoformat()
#     }
#     await websocket.send_json(payload)


# class EventDispatcher:
#     """Dispatches WebSocket events to appropriate handlers based on event type"""
    
#     def __init__(self):
#         self.handlers: Dict[str, Callable] = {}
    
#     def register_handler(self, event_type: str, handler: Callable):
#         """Register a handler function for an event type"""
#         self.handlers[event_type] = handler
    
#     async def dispatch(self, event_type: str, **kwargs):
#         """Dispatch an event to its registered handler"""
#         handler = self.handlers.get(event_type)
#         if handler:
#             try:
#                 await handler(**kwargs)
#             except Exception as e:
#                 logger.error(f"Error in event handler for {event_type}: {str(e)}")
#                 websocket = kwargs.get("websocket")
#                 if websocket:
#                     await websocket.send_json({
#                         "type": "error",
#                         "error": f"Error processing {event_type}: {str(e)}",
#                         "timestamp": datetime.now().isoformat()
#                     })
#         else:
#             logger.warning(f"No handler registered for event type: {event_type}")
#             websocket = kwargs.get("websocket")
#             if websocket:
#                 await websocket.send_json({
#                     "type": "error",
#                     "error": f"Unknown event type: {event_type}",
#                     "timestamp": datetime.now().isoformat()
#                 })


# class EventRegistry:
#     """Registry for all supported event handlers"""
    
#     def __init__(self):
#         self.dispatcher = EventDispatcher()
#         self._setup_handlers()
    
#     def _setup_handlers(self):
#         """Register all supported event handlers"""

#         # Core game events
#         self.dispatcher.register_handler("message", self.handle_message_event)
        
#         # System events
#         self.dispatcher.register_handler("ping", self.handle_ping_event)
        
#         # Usage-related events
#         self.dispatcher.register_handler("usage_check", self.handle_usage_check_event)

#         # Core game events
#         # self.dispatcher.register_handler("message", self.handle_message_event)
#         # self.dispatcher.register_handler("movement", self.handle_movement_event)
#         # self.dispatcher.register_handler("interaction", self.handle_interaction_event)
#         # self.dispatcher.register_handler("emote", self.handle_emote_event)
        
#         # # System events
#         # self.dispatcher.register_handler("ping", self.handle_ping_event)
#         # self.dispatcher.register_handler("zone_change", self.handle_zone_change_event)
        
#         # # Usage-related events
#         # self.dispatcher.register_handler("usage_check", self.handle_usage_check_event)
        
#         # # Additional RPG events
#         # self.dispatcher.register_handler("quest", self.handle_quest_event)
#         # self.dispatcher.register_handler("dialog", self.handle_dialog_event)
#         # self.dispatcher.register_handler("trade", self.handle_trade_event)
#         # self.dispatcher.register_handler("combat", self.handle_combat_event)
    
#     async def handle_message_event(
#         self,
#         websocket: WebSocket,
#         event_data: dict,
#         character_id: str,
#         zone_id: str,
#         world_id: str,
#         event_service: EventService,
#         **kwargs
#     ):
#         """Handle a chat message event"""
#         # Get the user ID from the character
#         from app.database import get_db
#         from app.services.character_service import CharacterService
#         from app.services.usage_service import UsageService
#         from app.ai.agent_manager import AgentManager
        
#         db = next(get_db())
#         character_service = CharacterService(db)
#         usage_service = UsageService(db)
#         agent_manager = AgentManager(db)
        
#         character = character_service.get_character(character_id)
#         if not character:
#             await websocket.send_json({
#                 "type": "error",
#                 "error": "Character not found",
#                 "timestamp": datetime.now().isoformat()
#             })
#             return
        
#         user_id = character.player_id
#         if not user_id:
#             await websocket.send_json({
#                 "type": "error",
#                 "error": "Character has no associated user",
#                 "timestamp": datetime.now().isoformat()
#             })
#             return
        
#         # Check message limits
#         if not usage_service.can_send_message(user_id):
#             await websocket.send_json({
#                 "type": "error",
#                 "error": "You have reached your daily message limit",
#                 "is_premium": usage_service.payment_service.is_premium(user_id),
#                 "timestamp": datetime.now().isoformat()
#             })
#             # Send updated usage info
#             await send_usage_update(websocket, usage_service, user_id)
#             return
        
#         content = event_data.get("content", "").strip()
#         if not content:
#             await websocket.send_json({
#                 "type": "error",
#                 "error": "Message content cannot be empty",
#                 "timestamp": datetime.now().isoformat()
#             })
#             return
        
#         # Determine scope of the message (public by default)
#         scope = EventScope.PUBLIC
#         participant_ids = None
#         target_character_id = event_data.get("target_character_id")
        
#         if target_character_id:
#             # Private message to a specific character
#             scope = EventScope.PRIVATE
#             participant_ids = [character_id, target_character_id]
        
#         # Track usage before creating the event
#         usage_service.track_message_sent(user_id, is_from_ai=False)
        
#         # Create the message event
#         event = event_service.create_message_event(
#             content=content,
#             character_id=character_id,
#             zone_id=zone_id if scope == EventScope.PUBLIC else None,
#             scope=scope,
#             target_character_id=target_character_id,
#             participant_ids=participant_ids
#         )
        
#         # Get character info for display
#         character_name = character.name
        
#         # Format the event for broadcasting
#         event_payload = {
#             "type": "game_event",
#             "event_type": "message",
#             "event_id": event.id,
#             "character_id": character_id,
#             "character_name": character_name,
#             "content": content,
#             "zone_id": zone_id if scope == EventScope.PUBLIC else None,
#             "timestamp": event.created_at.isoformat()
#         }
        
#         if scope == EventScope.PUBLIC:
#             # Broadcast to the entire zone
#             await connection_manager.broadcast_to_zone(
#                 zone_id, 
#                 event_payload,
#                 exclude_character_id=character_id
#             )
#         else:
#             # Send to the target character
#             await connection_manager.send_to_character(
#                 target_character_id,
#                 event_payload
#             )
                
#         # Send confirmation to sender
#         await websocket.send_json({
#             "type": "event_confirmation",
#             "event_id": event.id,
#             "event_type": "message",
#             "success": True,
#             "timestamp": datetime.now().isoformat()
#         })
        
#         # Send updated usage info
#         await send_usage_update(websocket, usage_service, user_id)
        
#         # Process message with GameMaster if it's a public message
#         if scope == EventScope.PUBLIC:
#             # Process through the GameMaster agent
#             game_master_response = await agent_manager.process_game_master_message(
#                 content, character_id, zone_id
#             )
            
#             # If the GameMaster determined this is a request, respond with a processed message
#             if game_master_response.get("is_request", False):
#                 response_content = game_master_response.get("response", "I don't understand your request.")
#                 request_type = game_master_response.get("request_type", "general_request")
                
#                 # Create a system response event
#                 system_response_event = event_service.create_event(
#                     type=EventType.MESSAGE,
#                     data={
#                         "content": response_content,
#                         "is_system_response": True,
#                         "request_type": request_type
#                     },
#                     character_id=None,  # System message
#                     zone_id=zone_id,
#                     scope=EventScope.PUBLIC
#                 )
                
#                 # Format the response for sending
#                 gm_response_payload = {
#                     "type": "game_event",
#                     "event_type": "message",
#                     "event_id": system_response_event.id,
#                     "character_id": None,
#                     "character_name": "GameMaster",
#                     "content": response_content,
#                     "is_system_response": True,
#                     "request_type": request_type,
#                     "timestamp": system_response_event.created_at.isoformat()
#                 }
                
#                 # Send the system response to the player
#                 await websocket.send_json(gm_response_payload)
                
#                 # Also broadcast to the zone so everyone sees the GameMaster's response
#                 await connection_manager.broadcast_to_zone(
#                     zone_id, 
#                     gm_response_payload,
#                     exclude_character_id=character_id
#                 )
    
#     async def process_ai_responses(
#         self,
#         agent_manager,
#         event,
#         user_id,
#         usage_service
#     ):
#         """Process AI agent responses for an event"""
#         try:
#             # This would be adapted to work with the new event system
#             responses = await agent_manager.process_event(event)
            
#             # Track AI responses in usage
#             for response in responses:
#                 usage_service.track_message_sent(user_id, is_from_ai=True)
                
#             logger.info(f"Generated {len(responses)} AI responses for event {event.id}")
#         except Exception as e:
#             logger.error(f"Error processing AI responses: {str(e)}")


# async def send_zone_data(websocket: WebSocket, zone_id: str, character_id: str, db: Session):
#     """Helper function to send zone data to a character"""
#     # Get entities in the zone
#     from app.services.entity_service import EntityService
#     from app.services.character_service import CharacterService
    
#     entity_service = EntityService(db)
#     character_service = CharacterService(db)
    
#     # Get characters in the zone
#     characters_in_zone = []
#     for char_id in connection_manager.get_characters_in_zone(zone_id):
#         if char_id != character_id:  # Don't include self
#             char = character_service.get_character(char_id)
#             if char:
#                 characters_in_zone.append({
#                     "id": char.id,
#                     "name": char.name,
#                     "type": char.type
#                 })
    
#     # Get objects in the zone
#     entities, _, _ = entity_service.get_entities_in_zone(
#         zone_id=zone_id,
#         entity_type="object",
#         page=1,
#         page_size=100
#     )
    
#     objects_in_zone = [{
#         "id": entity.id,
#         "name": entity.name,
#         "description": entity.description,
#         "type": entity.type
#     } for entity in entities]
    
#     # Send the zone data
#     await websocket.send_json({
#         "type": "zone_data",
#         "zone_id": zone_id,
#         "characters": characters_in_zone,
#         "objects": objects_in_zone,
#         "timestamp": datetime.now().isoformat()
#     })
    
#     # Send recent zone messages/events
#     from app.models.game_event import EventType
#     from app.services.event_service import EventService
#     event_service = EventService(db)
    
#     recent_events = event_service.get_zone_events(
#         zone_id=zone_id,
#         character_id=character_id,
#         event_types=[EventType.MESSAGE],
#         limit=20
#     )
    
#     if recent_events:
#         messages = []
#         for event in recent_events:
#             # Get character information
#             sender = character_service.get_character(event.character_id) if event.character_id else None
            
#             messages.append({
#                 "event_id": event.id,
#                 "content": event.data.get("content", ""),
#                 "character_id": event.character_id,
#                 "character_name": sender.name if sender else "System",
#                 "timestamp": event.created_at.isoformat()
#             })
        
#         # Send the recent messages
#         await websocket.send_json({
#             "type": "recent_messages",
#             "messages": messages,
#             "timestamp": datetime.now().isoformat()
#         })
    
#     # Send usage info to the character
#     try:
#         from app.services.usage_service import UsageService
#         usage_service = UsageService(db)
        
#         character = character_service.get_character(character_id)
#         if character and character.player_id:
#             await send_usage_update(websocket, usage_service, character.player_id)
#     except Exception as e:
#         logger.error(f"Error sending usage info: {str(e)}")


# # Create a global event registry
# event_registry = EventRegistry()