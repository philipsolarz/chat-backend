# app/websockets/event_dispatcher.py
import logging
import json
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional, Callable, Awaitable
from fastapi import WebSocket
from sqlalchemy.orm import Session
from app.models.game_event import EventType, EventScope
from app.services.event_service import EventService
from app.services.usage_service import UsageService
from app.websockets.connection_manager import connection_manager

logger = logging.getLogger(__name__)

# Standalone helper function for sending usage updates
async def send_usage_update(websocket: WebSocket, usage_service: UsageService, user_id: str):
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


class EventRegistry:
    """Registry for all supported event handlers"""
    
    def __init__(self):
        self.dispatcher = EventDispatcher()
        self._setup_handlers()
    
    def _setup_handlers(self):
        """Register all supported event handlers"""
        # Core game events
        self.dispatcher.register_handler("message", self.handle_message_event)
        self.dispatcher.register_handler("movement", self.handle_movement_event)
        self.dispatcher.register_handler("interaction", self.handle_interaction_event)
        self.dispatcher.register_handler("emote", self.handle_emote_event)
        
        # System events
        self.dispatcher.register_handler("ping", self.handle_ping_event)
        self.dispatcher.register_handler("zone_change", self.handle_zone_change_event)
        
        # Usage-related events
        self.dispatcher.register_handler("usage_check", self.handle_usage_check_event)
        
        # Additional RPG events
        self.dispatcher.register_handler("quest", self.handle_quest_event)
        self.dispatcher.register_handler("dialog", self.handle_dialog_event)
        self.dispatcher.register_handler("trade", self.handle_trade_event)
        self.dispatcher.register_handler("combat", self.handle_combat_event)
    
    async def handle_message_event(
        self,
        websocket: WebSocket,
        event_data: dict,
        character_id: str,
        zone_id: str,
        event_service: EventService,
        **kwargs
    ):
        """Handle a chat message event"""
        # Get the user ID from the character
        from app.database import get_db
        from app.services.character_service import CharacterService
        from app.services.usage_service import UsageService
        
        db = next(get_db())
        character_service = CharacterService(db)
        usage_service = UsageService(db)
        
        character = character_service.get_character(character_id)
        if not character:
            await websocket.send_json({
                "type": "error",
                "error": "Character not found",
                "timestamp": datetime.now().isoformat()
            })
            return
        
        user_id = character.player_id
        if not user_id:
            await websocket.send_json({
                "type": "error",
                "error": "Character has no associated user",
                "timestamp": datetime.now().isoformat()
            })
            return
        
        # Check message limits
        if not usage_service.can_send_message(user_id):
            await websocket.send_json({
                "type": "error",
                "error": "You have reached your daily message limit",
                "is_premium": usage_service.payment_service.is_premium(user_id),
                "timestamp": datetime.now().isoformat()
            })
            # Send updated usage info
            await send_usage_update(websocket, usage_service, user_id)
            return
        
        content = event_data.get("content", "").strip()
        if not content:
            await websocket.send_json({
                "type": "error",
                "error": "Message content cannot be empty",
                "timestamp": datetime.now().isoformat()
            })
            return
        
        # Determine scope of the message
        scope = EventScope.PUBLIC
        participant_ids = None
        target_character_id = event_data.get("target_character_id")
        
        if target_character_id:
            # Private message to a specific character
            scope = EventScope.PRIVATE
            participant_ids = [character_id, target_character_id]
        
        # Track usage before creating the event
        usage_service.track_message_sent(user_id, is_from_ai=False)
        
        # Create the message event
        event = event_service.create_message_event(
            content=content,
            character_id=character_id,
            zone_id=zone_id if scope == EventScope.PUBLIC else None,
            scope=scope,
            target_character_id=target_character_id,
            participant_ids=participant_ids
        )
        
        # Get character info for display
        character_name = character.name
        
        # Format the event for broadcasting
        event_payload = {
            "type": "game_event",
            "event_type": "message",
            "event_id": event.id,
            "character_id": character_id,
            "character_name": character_name,
            "content": content,
            "zone_id": zone_id if scope == EventScope.PUBLIC else None,
            "timestamp": event.created_at.isoformat()
        }
        
        if scope == EventScope.PUBLIC:
            # Broadcast to the entire zone
            await connection_manager.broadcast_to_zone(
                zone_id, 
                event_payload,
                exclude_character_id=character_id
            )
        else:
            # Send to the target character
            await connection_manager.send_to_character(
                target_character_id,
                event_payload
            )
            
        # Send confirmation to sender
        await websocket.send_json({
            "type": "event_confirmation",
            "event_id": event.id,
            "event_type": "message",
            "success": True,
            "timestamp": datetime.now().isoformat()
        })
        
        # Send updated usage info
        await send_usage_update(websocket, usage_service, user_id)
        
        # If this is an AI agent, process AI responses
        if scope == EventScope.PUBLIC:
            # Check for AI agents in the zone that might respond
            from app.ai.agent_manager import AgentManager
            agent_manager = AgentManager(db)
            
            # Process AI responses in the background
            asyncio.create_task(self.process_ai_responses(
                agent_manager=agent_manager,
                event=event,
                user_id=user_id,
                usage_service=usage_service
            ))
    
    async def process_ai_responses(
        self,
        agent_manager,
        event,
        user_id,
        usage_service
    ):
        """Process AI agent responses for an event"""
        try:
            # This would be adapted to work with the new event system
            responses = await agent_manager.process_event(event)
            
            # Track AI responses in usage
            for response in responses:
                usage_service.track_message_sent(user_id, is_from_ai=True)
                
            logger.info(f"Generated {len(responses)} AI responses for event {event.id}")
        except Exception as e:
            logger.error(f"Error processing AI responses: {str(e)}")
    
    async def handle_movement_event(
        self,
        websocket: WebSocket,
        event_data: dict,
        character_id: str,
        zone_id: str,
        event_service: EventService,
        **kwargs
    ):
        """Handle a character movement event between zones"""
        # Extract movement data
        from_zone_id = zone_id  # Current zone
        to_zone_id = event_data.get("to_zone_id")
        
        if not to_zone_id:
            await websocket.send_json({
                "type": "error",
                "error": "Movement requires to_zone_id",
                "timestamp": datetime.now().isoformat()
            })
            return
        
        # Verify the destination zone exists
        from app.services.zone_service import ZoneService
        zone_service = ZoneService(event_service.db)
        
        destination_zone = zone_service.get_zone(to_zone_id)
        if not destination_zone:
            await websocket.send_json({
                "type": "error",
                "error": "Destination zone not found",
                "timestamp": datetime.now().isoformat()
            })
            return
        
        # Check if zones are connected (depends on your game rules)
        # For now we'll assume they are, but you might want to check
        # if the zones are adjacent or if there's a portal
        
        # Create the movement event
        event = event_service.create_event(
            type=EventType.MOVEMENT,
            data={
                "from_zone_id": from_zone_id,
                "to_zone_id": to_zone_id,
                "coordinates": event_data.get("coordinates", {})
            },
            character_id=character_id,
            zone_id=to_zone_id,  # Record the event in the destination zone
            scope=EventScope.PUBLIC
        )
        
        # Get character info for display
        from app.services.character_service import CharacterService
        character_service = CharacterService(event_service.db)
        
        character = character_service.get_character(character_id)
        character_name = character.name if character else "Unknown"
        
        # Update the connection manager
        connection_manager.move_character_to_zone(character_id, from_zone_id, to_zone_id)
        
        # Format the events for broadcasting
        exit_payload = {
            "type": "game_event",
            "event_type": "character_left",
            "event_id": event.id,
            "character_id": character_id,
            "character_name": character_name,
            "from_zone_id": from_zone_id,
            "to_zone_id": to_zone_id,
            "timestamp": event.created_at.isoformat()
        }
        
        entry_payload = {
            "type": "game_event",
            "event_type": "character_entered",
            "event_id": event.id,
            "character_id": character_id,
            "character_name": character_name,
            "from_zone_id": from_zone_id,
            "to_zone_id": to_zone_id,
            "timestamp": event.created_at.isoformat()
        }
        
        # Broadcast departure to old zone
        await connection_manager.broadcast_to_zone(
            from_zone_id,
            exit_payload,
            exclude_character_id=character_id
        )
        
        # Broadcast arrival to new zone
        await connection_manager.broadcast_to_zone(
            to_zone_id,
            entry_payload,
            exclude_character_id=character_id
        )
        
        # Send confirmation to the character
        await websocket.send_json({
            "type": "zone_change_confirmation",
            "event_id": event.id,
            "from_zone_id": from_zone_id,
            "to_zone_id": to_zone_id,
            "success": True,
            "timestamp": datetime.now().isoformat()
        })
        
        # Send new zone data to the character
        await send_zone_data(websocket, to_zone_id, character_id, event_service.db)
    
    async def handle_interaction_event(
        self,
        websocket: WebSocket,
        event_data: dict,
        character_id: str,
        zone_id: str,
        event_service: EventService,
        **kwargs
    ):
        """Handle a character interaction with an entity"""
        target_entity_id = event_data.get("target_entity_id")
        interaction_type = event_data.get("interaction_type")
        
        if not target_entity_id or not interaction_type:
            await websocket.send_json({
                "type": "error",
                "error": "Interaction requires target_entity_id and interaction_type",
                "timestamp": datetime.now().isoformat()
            })
            return
        
        # Verify the target entity exists and is in the same zone
        from app.services.entity_service import EntityService
        entity_service = EntityService(event_service.db)
        
        entity = entity_service.get_entity(target_entity_id)
        if not entity:
            await websocket.send_json({
                "type": "error",
                "error": "Target entity not found",
                "timestamp": datetime.now().isoformat()
            })
            return
        
        if entity.zone_id != zone_id:
            await websocket.send_json({
                "type": "error",
                "error": "Target entity is not in your zone",
                "timestamp": datetime.now().isoformat()
            })
            return
        
        # Create the interaction event
        event = event_service.create_event(
            type=EventType.INTERACTION,
            data={
                "interaction_type": interaction_type,
                "details": event_data.get("details", {})
            },
            character_id=character_id,
            zone_id=zone_id,
            target_entity_id=target_entity_id,
            scope=EventScope.PUBLIC
        )
        
        # Get character info for display
        from app.services.character_service import CharacterService
        character_service = CharacterService(event_service.db)
        
        character = character_service.get_character(character_id)
        character_name = character.name if character else "Unknown"
        
        # Format the event for broadcasting
        interaction_payload = {
            "type": "game_event",
            "event_type": "interaction",
            "event_id": event.id,
            "character_id": character_id,
            "character_name": character_name,
            "target_entity_id": target_entity_id,
            "target_entity_name": entity.name,
            "interaction_type": interaction_type,
            "details": event_data.get("details", {}),
            "timestamp": event.created_at.isoformat()
        }
        
        # Broadcast to the zone
        await connection_manager.broadcast_to_zone(
            zone_id,
            interaction_payload,
            exclude_character_id=character_id
        )
        
        # Send confirmation to the character
        await websocket.send_json({
            "type": "event_confirmation",
            "event_id": event.id,
            "event_type": "interaction",
            "success": True,
            "timestamp": datetime.now().isoformat()
        })
        
        # Process the interaction based on entity type and interaction type
        # For now we'll just acknowledge it, but this could trigger game logic
        interaction_result = {
            "type": "interaction_result",
            "event_id": event.id,
            "interaction_type": interaction_type,
            "target_entity_id": target_entity_id,
            "result": "success",
            "message": f"You interacted with {entity.name}",
            "timestamp": datetime.now().isoformat()
        }
        
        await websocket.send_json(interaction_result)
    
    async def handle_emote_event(
        self,
        websocket: WebSocket,
        event_data: dict,
        character_id: str,
        zone_id: str,
        event_service: EventService,
        **kwargs
    ):
        """Handle a character emote"""
        emote_text = event_data.get("emote", "").strip()
        if not emote_text:
            await websocket.send_json({
                "type": "error",
                "error": "Emote text cannot be empty",
                "timestamp": datetime.now().isoformat()
            })
            return
        
        # Create the emote event
        event = event_service.create_event(
            type=EventType.EMOTE,
            data={
                "emote": emote_text
            },
            character_id=character_id,
            zone_id=zone_id,
            scope=EventScope.PUBLIC
        )
        
        # Get character info for display
        from app.services.character_service import CharacterService
        character_service = CharacterService(event_service.db)
        
        character = character_service.get_character(character_id)
        character_name = character.name if character else "Unknown"
        
        # Format the event for broadcasting
        emote_payload = {
            "type": "game_event",
            "event_type": "emote",
            "event_id": event.id,
            "character_id": character_id,
            "character_name": character_name,
            "emote": emote_text,
            "timestamp": event.created_at.isoformat()
        }
        
        # Broadcast to the zone
        await connection_manager.broadcast_to_zone(
            zone_id,
            emote_payload,
            exclude_character_id=character_id
        )
        
        # Send confirmation to the character
        await websocket.send_json({
            "type": "event_confirmation",
            "event_id": event.id,
            "event_type": "emote",
            "success": True,
            "timestamp": datetime.now().isoformat()
        })
    
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
    
    async def handle_usage_check_event(
        self,
        websocket: WebSocket,
        character_id: str,
        **kwargs
    ):
        """Handle a usage check event"""
        # Get the user ID from the character
        from app.database import get_db
        from app.services.character_service import CharacterService
        from app.services.usage_service import UsageService
        
        db = next(get_db())
        character_service = CharacterService(db)
        usage_service = UsageService(db)
        
        character = character_service.get_character(character_id)
        if character and character.player_id:
            await send_usage_update(websocket, usage_service, character.player_id)
        else:
            await websocket.send_json({
                "type": "error",
                "error": "Could not determine user for usage check",
                "timestamp": datetime.now().isoformat()
            })
    
    async def handle_zone_change_event(
        self,
        websocket: WebSocket,
        event_data: dict,
        character_id: str,
        zone_id: str,
        event_service: EventService,
        **kwargs
    ):
        """Alias for movement - handle zone change"""
        await self.handle_movement_event(
            websocket=websocket,
            event_data=event_data,
            character_id=character_id,
            zone_id=zone_id,
            event_service=event_service,
            **kwargs
        )
    
    async def handle_quest_event(
        self,
        websocket: WebSocket,
        event_data: dict,
        character_id: str,
        zone_id: str,
        event_service: EventService,
        **kwargs
    ):
        """Handle quest-related events"""
        quest_action = event_data.get("quest_action")
        quest_id = event_data.get("quest_id")
        
        if not quest_action or not quest_id:
            await websocket.send_json({
                "type": "error",
                "error": "Quest events require quest_action and quest_id",
                "timestamp": datetime.now().isoformat()
            })
            return
        
        # Create the quest event
        event = event_service.create_event(
            type=EventType.QUEST,
            data={
                "quest_id": quest_id,
                "action": quest_action,
                "details": event_data.get("details", {})
            },
            character_id=character_id,
            zone_id=zone_id,
            scope=EventScope.PUBLIC if quest_action in ["accept", "complete"] else EventScope.PRIVATE,
            participant_ids=[character_id] if quest_action not in ["accept", "complete"] else None
        )
        
        # Get character info for display
        from app.services.character_service import CharacterService
        character_service = CharacterService(event_service.db)
        
        character = character_service.get_character(character_id)
        character_name = character.name if character else "Unknown"
        
        # Format the event 
        quest_payload = {
            "type": "game_event",
            "event_type": "quest",
            "event_id": event.id,
            "character_id": character_id,
            "character_name": character_name,
            "quest_id": quest_id,
            "quest_action": quest_action,
            "details": event_data.get("details", {}),
            "timestamp": event.created_at.isoformat()
        }
        
        # Broadcast public quest events to the zone
        if quest_action in ["accept", "complete"]:
            await connection_manager.broadcast_to_zone(
                zone_id,
                quest_payload,
                exclude_character_id=character_id
            )
        
        # Send confirmation to the character
        await websocket.send_json({
            "type": "event_confirmation",
            "event_id": event.id,
            "event_type": "quest",
            "quest_action": quest_action,
            "success": True,
            "timestamp": datetime.now().isoformat()
        })
    
    async def handle_dialog_event(
        self,
        websocket: WebSocket,
        event_data: dict,
        character_id: str,
        zone_id: str,
        event_service: EventService,
        **kwargs
    ):
        """Handle dialog with NPCs or dialog choices"""
        dialog_id = event_data.get("dialog_id")
        target_entity_id = event_data.get("target_entity_id")
        choice_id = event_data.get("choice_id")
        
        if not dialog_id or not target_entity_id:
            await websocket.send_json({
                "type": "error",
                "error": "Dialog events require dialog_id and target_entity_id",
                "timestamp": datetime.now().isoformat()
            })
            return
        
        # Create the dialog event
        event = event_service.create_event(
            type=EventType.INTERACTION,  # Dialog is a special kind of interaction
            data={
                "dialog_id": dialog_id,
                "choice_id": choice_id,
                "details": event_data.get("details", {})
            },
            character_id=character_id,
            zone_id=zone_id,
            target_entity_id=target_entity_id,
            scope=EventScope.PRIVATE,
            participant_ids=[character_id]
        )
        
        # Send confirmation to the character
        await websocket.send_json({
            "type": "event_confirmation",
            "event_id": event.id,
            "event_type": "dialog",
            "success": True,
            "timestamp": datetime.now().isoformat()
        })
        
        # Here you would process the dialog choice and send back the next dialog options
        # This would typically involve NPC logic which would be specific to your game
        
        # For now, just send a simple acknowledgment
        dialog_response = {
            "type": "dialog_response",
            "event_id": event.id,
            "dialog_id": dialog_id,
            "choice_id": choice_id,
            "response": {
                "text": "This is a placeholder response. Your dialog choice has been recorded.",
                "options": [
                    {"id": "option1", "text": "Tell me more"},
                    {"id": "option2", "text": "Goodbye"}
                ]
            },
            "timestamp": datetime.now().isoformat()
        }
        
        await websocket.send_json(dialog_response)
    
    async def handle_trade_event(
        self,
        websocket: WebSocket,
        event_data: dict,
        character_id: str,
        zone_id: str,
        event_service: EventService,
        **kwargs
    ):
        """Handle trade events between characters"""
        trade_action = event_data.get("trade_action")
        target_character_id = event_data.get("target_character_id")
        
        if not trade_action or not target_character_id:
            await websocket.send_json({
                "type": "error",
                "error": "Trade events require trade_action and target_character_id",
                "timestamp": datetime.now().isoformat()
            })
            return
        
        # Verify the target character is in the same zone
        target_character_zone = connection_manager.character_zones.get(target_character_id)
        if target_character_zone != zone_id:
            await websocket.send_json({
                "type": "error",
                "error": "Target character is not in your zone",
                "timestamp": datetime.now().isoformat()
            })
            return
        
        # Create the trade event
        event = event_service.create_event(
            type=EventType.TRADE,
            data={
                "trade_action": trade_action,
                "items": event_data.get("items", []),
                "gold": event_data.get("gold", 0)
            },
            character_id=character_id,
            zone_id=zone_id,
            scope=EventScope.PRIVATE,
            participant_ids=[character_id, target_character_id]
        )
        
        # Get character info for display
        from app.services.character_service import CharacterService
        character_service = CharacterService(event_service.db)
        
        character = character_service.get_character(character_id)
        character_name = character.name if character else "Unknown"
        
        # Format the event for the target character
        trade_payload = {
            "type": "game_event",
            "event_type": "trade",
            "event_id": event.id,
            "character_id": character_id,
            "character_name": character_name,
            "trade_action": trade_action,
            "items": event_data.get("items", []),
            "gold": event_data.get("gold", 0),
            "timestamp": event.created_at.isoformat()
        }
        
        # Send to the target character
        await connection_manager.send_to_character(
            target_character_id,
            trade_payload
        )
        
        # Send confirmation to the character
        await websocket.send_json({
            "type": "event_confirmation",
            "event_id": event.id,
            "event_type": "trade",
            "success": True,
            "timestamp": datetime.now().isoformat()
        })
    
    async def handle_combat_event(
        self,
        websocket: WebSocket,
        event_data: dict,
        character_id: str,
        zone_id: str,
        event_service: EventService,
        **kwargs
    ):
        """Handle combat actions"""
        combat_action = event_data.get("combat_action")
        target_entity_id = event_data.get("target_entity_id")
        
        if not combat_action or not target_entity_id:
            await websocket.send_json({
                "type": "error",
                "error": "Combat events require combat_action and target_entity_id",
                "timestamp": datetime.now().isoformat()
            })
            return
        
        # Verify target exists and is in the same zone
        from app.services.entity_service import EntityService
        entity_service = EntityService(event_service.db)
        
        entity = entity_service.get_entity(target_entity_id)
        if not entity:
            await websocket.send_json({
                "type": "error",
                "error": "Target entity not found",
                "timestamp": datetime.now().isoformat()
            })
            return
        
        if entity.zone_id != zone_id:
            await websocket.send_json({
                "type": "error",
                "error": "Target entity is not in your zone",
                "timestamp": datetime.now().isoformat()
            })
            return
        
        # Create the combat event
        event = event_service.create_event(
            type=EventType.COMBAT,
            data={
                "combat_action": combat_action,
                "skill_id": event_data.get("skill_id"),
                "weapon_id": event_data.get("weapon_id"),
                "details": event_data.get("details", {})
            },
            character_id=character_id,
            zone_id=zone_id,
            target_entity_id=target_entity_id,
            scope=EventScope.PUBLIC
        )
        
        # Get character info for display
        from app.services.character_service import CharacterService
        character_service = CharacterService(event_service.db)
        
        character = character_service.get_character(character_id)
        character_name = character.name if character else "Unknown"
        
        # Format the event for broadcasting
        combat_payload = {
            "type": "game_event",
            "event_type": "combat",
            "event_id": event.id,
            "character_id": character_id,
            "character_name": character_name,
            "target_entity_id": target_entity_id,
            "target_entity_name": entity.name,
            "combat_action": combat_action,
            "details": event_data.get("details", {}),
            "timestamp": event.created_at.isoformat()
        }
        
        # Broadcast to the zone
        await connection_manager.broadcast_to_zone(
            zone_id,
            combat_payload,
            exclude_character_id=character_id
        )
        
        # Send confirmation to the character
        await websocket.send_json({
            "type": "event_confirmation",
            "event_id": event.id,
            "event_type": "combat",
            "success": True,
            "timestamp": datetime.now().isoformat()
        })
        
        # Process the combat action and send the result
        # This would involve combat calculations based on your game rules
        combat_result = {
            "type": "combat_result",
            "event_id": event.id,
            "combat_action": combat_action,
            "target_entity_id": target_entity_id,
            "result": {
                "hit": True,  # Placeholder - would be based on actual calculations
                "damage": 10,  # Placeholder 
                "critical": False,
                "effects": []
            },
            "timestamp": datetime.now().isoformat()
        }
        
        await websocket.send_json(combat_result)


async def send_zone_data(websocket: WebSocket, zone_id: str, character_id: str, db: Session):
    """Helper function to send zone data to a character"""
    # Get entities in the zone
    from app.services.entity_service import EntityService
    from app.services.character_service import CharacterService
    
    entity_service = EntityService(db)
    character_service = CharacterService(db)
    
    # Get characters in the zone
    characters_in_zone = []
    for char_id in connection_manager.get_characters_in_zone(zone_id):
        if char_id != character_id:  # Don't include self
            char = character_service.get_character(char_id)
            if char:
                characters_in_zone.append({
                    "id": char.id,
                    "name": char.name,
                    "type": char.type
                })
    
    # Get objects in the zone
    entities, _, _ = entity_service.get_entities_in_zone(
        zone_id=zone_id,
        entity_type="object",
        page=1,
        page_size=100
    )
    
    objects_in_zone = [{
        "id": entity.id,
        "name": entity.name,
        "description": entity.description,
        "type": entity.type
    } for entity in entities]
    
    # Send the zone data
    await websocket.send_json({
        "type": "zone_data",
        "zone_id": zone_id,
        "characters": characters_in_zone,
        "objects": objects_in_zone,
        "timestamp": datetime.now().isoformat()
    })
    
    # Send recent zone messages/events
    from app.models.game_event import EventType
    from app.services.event_service import EventService
    event_service = EventService(db)
    
    recent_events = event_service.get_zone_events(
        zone_id=zone_id,
        character_id=character_id,
        event_types=[EventType.MESSAGE],
        limit=20
    )
    
    if recent_events:
        messages = []
        for event in recent_events:
            # Get character information
            sender = character_service.get_character(event.character_id) if event.character_id else None
            
            messages.append({
                "event_id": event.id,
                "content": event.data.get("content", ""),
                "character_id": event.character_id,
                "character_name": sender.name if sender else "System",
                "timestamp": event.created_at.isoformat()
            })
        
        # Send the recent messages
        await websocket.send_json({
            "type": "recent_messages",
            "messages": messages,
            "timestamp": datetime.now().isoformat()
        })
    
    # Send usage info to the character
    try:
        from app.services.usage_service import UsageService
        usage_service = UsageService(db)
        
        character = character_service.get_character(character_id)
        if character and character.player_id:
            await send_usage_update(websocket, usage_service, character.player_id)
    except Exception as e:
        logger.error(f"Error sending usage info: {str(e)}")


# Create a global event registry
event_registry = EventRegistry()