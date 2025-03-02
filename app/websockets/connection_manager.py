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
from app.services.event_service import EventService
from app.models.game_event import EventType, EventScope

logger = logging.getLogger(__name__)

class ConnectionManager:
    """Manager for WebSocket game connections"""
    
    def __init__(self):
        # Map of character_id -> WebSocket
        self.character_connections: Dict[str, WebSocket] = {}
        # Map of zone_id -> set of character_ids currently in the zone
        self.zone_characters: Dict[str, Set[str]] = {}
        # Map of WebSocket -> character_id
        self.connection_characters: Dict[WebSocket, str] = {}
        # Map of character_id -> zone_id
        self.character_zones: Dict[str, str] = {}
    
    async def connect(
        self, 
        websocket: WebSocket, 
        character_id: str,
        zone_id: str
    ) -> bool:
        """Register a new WebSocket game connection"""
        try:
            # Store the connection
            self.character_connections[character_id] = websocket
            self.connection_characters[websocket] = character_id
            self.character_zones[character_id] = zone_id
            
            # Track character in zone
            if zone_id not in self.zone_characters:
                self.zone_characters[zone_id] = set()
            self.zone_characters[zone_id].add(character_id)
            
            logger.info(f"Character {character_id} connected in zone {zone_id}")
            return True
        except Exception as e:
            logger.error(f"Error connecting WebSocket for character {character_id}: {str(e)}")
            return False
    
    def disconnect(self, websocket: WebSocket):
        """Unregister a WebSocket connection"""
        character_id = self.connection_characters.get(websocket)
        if character_id:
            # Get zone before removing connections
            zone_id = self.character_zones.get(character_id)
            
            # Remove from character connections
            if character_id in self.character_connections:
                del self.character_connections[character_id]
            
            # Remove from connection characters
            del self.connection_characters[websocket]
            
            # Remove from character zones
            if character_id in self.character_zones:
                del self.character_zones[character_id]
            
            # Remove from zone characters
            if zone_id and zone_id in self.zone_characters:
                if character_id in self.zone_characters[zone_id]:
                    self.zone_characters[zone_id].remove(character_id)
                
                # Notify others in zone about departure
                if len(self.zone_characters[zone_id]) > 0:
                    asyncio.create_task(self._notify_zone_departure(zone_id, character_id))
            
            logger.info(f"Character {character_id} disconnected from zone {zone_id}")
    
    async def broadcast_to_zone(
        self, 
        zone_id: str, 
        event: Dict[str, Any],
        exclude_character_id: Optional[str] = None
    ):
        """Broadcast an event to all characters in a zone"""
        if zone_id not in self.zone_characters:
            return
            
        for character_id in self.zone_characters[zone_id]:
            if character_id == exclude_character_id:
                continue
                
            await self.send_to_character(character_id, event)
    
    async def send_to_character(
        self, 
        character_id: str, 
        event: Dict[str, Any]
    ):
        """Send an event to a specific character"""
        websocket = self.character_connections.get(character_id)
        if websocket:
            try:
                await websocket.send_json(event)
            except Exception as e:
                logger.error(f"Error sending event to character {character_id}: {str(e)}")
                self.disconnect(websocket)
    
    async def _notify_zone_departure(self, zone_id: str, character_id: str):
        """Notify others in zone about a character leaving"""
        await self.broadcast_to_zone(
            zone_id,
            {
                "type": "game_event",
                "event_type": "character_left_zone",
                "character_id": character_id,
                "zone_id": zone_id,
                "timestamp": datetime.now().isoformat()
            },
            exclude_character_id=character_id
        )
    
    def get_characters_in_zone(self, zone_id: str) -> List[str]:
        """Get all character IDs currently in a zone"""
        return list(self.zone_characters.get(zone_id, set()))
    
    def move_character_to_zone(self, character_id: str, from_zone_id: str, to_zone_id: str):
        """Move a character from one zone to another"""
        # Remove from old zone
        if from_zone_id in self.zone_characters and character_id in self.zone_characters[from_zone_id]:
            self.zone_characters[from_zone_id].remove(character_id)
        
        # Add to new zone
        if to_zone_id not in self.zone_characters:
            self.zone_characters[to_zone_id] = set()
        self.zone_characters[to_zone_id].add(character_id)
        
        # Update character's current zone
        self.character_zones[character_id] = to_zone_id
        
        logger.info(f"Character {character_id} moved from zone {from_zone_id} to {to_zone_id}")


# Create singleton instance
connection_manager = ConnectionManager()


async def authenticate_connection(
    websocket: WebSocket,
    token: str,
    character_id: str,
    auth_service: AuthService
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
        
        # Verify the character belongs to the user
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


async def send_initial_zone_data(
    websocket: WebSocket,
    zone_id: str,
    character_id: str
):
    """Send initial zone data when a character connects to a zone"""
    # Get entities in the zone
    from app.services.entity_service import EntityService
    from app.services.character_service import CharacterService
    from app.database import get_db
    
    db = next(get_db())
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


async def handle_game_connection(
    websocket: WebSocket,
    character_id: str,
    zone_id: str,
    token: str,
    db: Session = None
):
    """Handle a WebSocket game connection for a character"""
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
    event_service = EventService(db)
    
    # Authenticate and authorize connection
    user_id = await authenticate_connection(
        websocket, token, character_id, auth_service
    )
    
    if user_id is None:
        return  # Authentication failed
    
    # Register connection
    await connection_manager.connect(websocket, character_id, zone_id)
    
    # Send initial zone data
    await send_initial_zone_data(websocket, zone_id, character_id)
    
    # Announce character entry to zone
    entry_event = event_service.create_event(
        type=EventType.SYSTEM,
        data={
            "message": "entered_zone"
        },
        character_id=character_id,
        zone_id=zone_id,
        scope=EventScope.PUBLIC
    )
    
    # Broadcast entry to zone
    entry_payload = {
        "type": "game_event",
        "event_type": "character_entered",
        "character_id": character_id,
        "zone_id": zone_id,
        "timestamp": entry_event.created_at.isoformat()
    }
    
    await connection_manager.broadcast_to_zone(
        zone_id,
        entry_payload,
        exclude_character_id=character_id
    )
    
    # Import event dispatcher
    from app.websockets.event_dispatcher import event_registry
    
    # Main message loop
    try:
        while True:
            # Wait for message
            data = await websocket.receive_text()
            
            # Parse JSON
            try:
                event_data = json.loads(data)
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "error": "Invalid JSON format",
                    "timestamp": datetime.now().isoformat()
                })
                continue
            
            # Get event type
            event_type = event_data.get("type", "message")
            
            # Dispatch to handler
            await event_registry.dispatcher.dispatch(
                event_type,
                websocket=websocket,
                event_data=event_data,
                character_id=character_id,
                zone_id=zone_id,
                event_service=event_service
            )
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: character {character_id}")
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}")
        await websocket.close(code=1011, reason="Internal server error")
    finally:
        # Create disconnect event
        try:
            event_service.create_event(
                type=EventType.SYSTEM,
                data={
                    "message": "left_zone"
                },
                character_id=character_id,
                zone_id=zone_id,
                scope=EventScope.PUBLIC
            )
        except Exception as e:
            logger.error(f"Error creating disconnect event: {str(e)}")
        
        # Clean up
        connection_manager.disconnect(websocket)
        
        if close_db and db:
            db.close()
            
        logger.info(f"Connection closed for character {character_id}")