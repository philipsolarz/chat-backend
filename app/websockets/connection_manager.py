# app/websockets/connection_manager.py
import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional, Set
from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.events import EventScope, EventType
from app.services.auth_service import AuthService
from app.services.event_service import EventService

logger = logging.getLogger(__name__)

class ConnectionManager:
    """
    ConnectionManager that tracks:
      - Which character is using which WebSocket
      - Which zone/world each character is in
      - Mappings from zones/worlds to sets of character IDs
    """

    def __init__(self):
        # character_id -> WebSocket
        self.character_connections: Dict[str, WebSocket] = {}

        # zone_id -> set of character_ids
        self.zone_characters: Dict[str, Set[str]] = {}
        # world_id -> set of character_ids
        self.world_characters: Dict[str, Set[str]] = {}

        # character_id -> zone_id
        self.character_zones: Dict[str, str] = {}
        # character_id -> world_id
        self.character_worlds: Dict[str, str] = {}

    async def connect(self, websocket: WebSocket, character_id: str, zone_id: str, world_id: str):
        """
        Register a character's connection, and track zone/world membership.
        """
        # Keep the WebSocket
        self.character_connections[character_id] = websocket
        
        # Track zone
        self.character_zones[character_id] = zone_id
        if zone_id not in self.zone_characters:
            self.zone_characters[zone_id] = set()
        self.zone_characters[zone_id].add(character_id)
        
        # Track world
        self.character_worlds[character_id] = world_id
        if world_id not in self.world_characters:
            self.world_characters[world_id] = set()
        self.world_characters[world_id].add(character_id)
        
        logger.info(f"Character {character_id} connected in zone {zone_id}, world {world_id}")

    def disconnect(self, websocket: WebSocket):
        """
        Unregister a WebSocket and remove the character from zone/world sets.
        """
        # Find the character that belongs to this socket
        char_to_remove = None
        for c_id, ws in self.character_connections.items():
            if ws == websocket:
                char_to_remove = c_id
                break
        
        if not char_to_remove:
            return  # Not found; nothing to do
        
        # Remove from the connection map
        del self.character_connections[char_to_remove]

        # Remove from zone set
        zone_id = self.character_zones.get(char_to_remove)
        if zone_id and zone_id in self.zone_characters:
            self.zone_characters[zone_id].discard(char_to_remove)
            if not self.zone_characters[zone_id]:
                del self.zone_characters[zone_id]
        self.character_zones.pop(char_to_remove, None)

        # Remove from world set
        world_id = self.character_worlds.get(char_to_remove)
        if world_id and world_id in self.world_characters:
            self.world_characters[world_id].discard(char_to_remove)
            if not self.world_characters[world_id]:
                del self.world_characters[world_id]
        self.character_worlds.pop(char_to_remove, None)
        
        logger.info(f"Character {char_to_remove} disconnected from zone {zone_id}, world {world_id}")

    async def broadcast_to_zone(self, zone_id: str, event: Dict[str, Any], exclude_character_id: Optional[str] = None):
        """
        Broadcast an event to all characters in the specified zone.
        """
        if zone_id not in self.zone_characters:
            return
        
        for c_id in self.zone_characters[zone_id]:
            if c_id == exclude_character_id:
                continue
            await self.send_to_character(c_id, event)

    async def broadcast_to_world(self, world_id: str, event: Dict[str, Any], exclude_character_id: Optional[str] = None):
        """
        Broadcast an event to all characters in the specified world.
        """
        if world_id not in self.world_characters:
            return
        
        for c_id in self.world_characters[world_id]:
            if c_id == exclude_character_id:
                continue
            await self.send_to_character(c_id, event)

    async def send_to_character(self, character_id: str, event: Dict[str, Any]):
        """
        Send an event to a specific character (if connected).
        """
        ws = self.character_connections.get(character_id)
        if ws:
            try:
                await ws.send_json(event)
            except Exception as e:
                logger.error(f"Error sending event to character {character_id}: {e}")
                self.disconnect(ws)


connection_manager = ConnectionManager()



async def authenticate_connection(
    websocket: WebSocket,
    token: str,
    character_id: str,
    auth_service: AuthService
) -> Optional[str]:
    """
    Authenticate a WebSocket connection.
    Returns user_id if successful, None otherwise.
    """
    try:
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
        
        user = auth_service.get_user_by_id(user_id)
        if not user:
            await websocket.send_json({
                "type": "error",
                "error": "User not found",
                "timestamp": datetime.now().isoformat()
            })
            await websocket.close(code=4001, reason="User not found")
            return None
        
        from app.services.character_service import CharacterService
        character_service = CharacterService(auth_service.db)
        character = character_service.get_character(character_id)
        
        if not character:
            await websocket.send_json({
                "type": "error",
                "error": "Character not found",
                "timestamp": datetime.now().isoformat()
            })
            await websocket.close(code=4004, reason="Character not found")
            return None
        
        if character.player_id != user_id:
            await websocket.send_json({
                "type": "error",
                "error": "Not authorized to use this character",
                "timestamp": datetime.now().isoformat()
            })
            await websocket.close(code=4003, reason="Not authorized")
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

async def handle_game_connection(
    websocket: WebSocket,
    world_id: str,
    character_id: str,
    zone_id: str,
    token: str,
    db: Session = None
):
    """Simplified WebSocket game connection handler, supporting only 'message' and 'ping' events."""
    close_db = False
    if db is None:
        db = next(get_db())
        close_db = True
    
    try:
        # Accept the connection
        await websocket.accept()
    except Exception as e:
        logger.error(f"Failed to accept WebSocket connection: {str(e)}")
        return
    
    auth_service = AuthService(db)
    event_service = EventService(db)
    
    # Authenticate
    user_id = await authenticate_connection(websocket, token, character_id, auth_service)
    if user_id is None:
        return  # Authentication failed
    
    # Verify zone/world membership
    from app.services.character_service import CharacterService
    from app.services.zone_service import ZoneService
    from app.services.world_service import WorldService

    character_service = CharacterService(db)
    zone_service = ZoneService(db)
    world_service = WorldService(db)
    
    character = character_service.get_character(character_id)
    if not character or character.player_id != user_id:
        await websocket.send_json({
            "type": "error",
            "error": "You don't own this character or character not found",
            "timestamp": datetime.now().isoformat()
        })
        await websocket.close(code=4003, reason="Not authorized")
        return
    
    zone = zone_service.get_zone(zone_id)
    if not zone or zone.world_id != world_id:
        await websocket.send_json({
            "type": "error",
            "error": "Zone not found or zone not in world",
            "timestamp": datetime.now().isoformat()
        })
        await websocket.close(code=4004, reason="Zone invalid")
        return
    
    # Register with connection manager
    await connection_manager.connect(websocket, character_id, zone_id, world_id)
    
    # Log and broadcast entry
    entry_event = event_service.create_event(
        type=EventType.SYSTEM,
        data={"message": "entered_zone"},
        character_id=character_id,
        zone_id=zone_id,
        scope=EventScope.PUBLIC
    )
    entry_payload = {
        "type": "game_event",
        "event_type": "character_entered",
        "character_id": character_id,
        "zone_id": zone_id,
        "timestamp": entry_event.created_at.isoformat()
    }
    await connection_manager.broadcast_to_zone(
        zone_id, entry_payload, exclude_character_id=character_id
    )
    
    # Use the event dispatcher for 'message' and 'ping'
    from app.websockets.event_dispatcher import event_registry
    # Optionally create an AI agent manager for message interpretation
    from app.ai.agent_manager import AgentManager
    agent_manager = AgentManager(db)
    
    try:
        while True:
            raw_data = await websocket.receive_text()
            try:
                event_data = json.loads(raw_data)
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "error": "Invalid JSON format",
                    "timestamp": datetime.now().isoformat()
                })
                continue
            
            # Dispatch the event
            await event_registry.dispatcher.dispatch(
                websocket=websocket,
                event_data=event_data,
                agent_manager=agent_manager,
                world_id=world_id,
                character_id=character_id
            )
    
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: character {character_id}")
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}")
        await websocket.close(code=1011, reason="Internal server error")
    finally:
        # Log and broadcast departure
        try:
            event_service.create_event(
                type=EventType.SYSTEM,
                data={"message": "left_zone"},
                character_id=character_id,
                zone_id=zone_id,
                scope=EventScope.PUBLIC
            )
            leave_payload = {
                "type": "game_event",
                "event_type": "character_left",
                "character_id": character_id,
                "zone_id": zone_id,
                "timestamp": datetime.now().isoformat()
            }
            await connection_manager.broadcast_to_zone(
                zone_id, leave_payload, exclude_character_id=character_id
            )
        except Exception as e2:
            logger.error(f"Error creating disconnect event: {str(e2)}")

        connection_manager.disconnect(websocket)
        if close_db and db:
            db.close()
        logger.info(f"Connection closed for character {character_id}")

