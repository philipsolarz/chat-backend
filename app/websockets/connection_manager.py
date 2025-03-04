# app/websockets/connection_manager.py
import asyncio
from collections import defaultdict
from enum import Enum
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Set
from fastapi import WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.database import get_db
# from app.schemas.events import EventScope, EventType, GameEventBase
from app.services.auth_service import AuthService
from app.services.event_service import EventService
from app.services.character_service import CharacterService
from app.services.player_service import PlayerService
from app.services.zone_service import ZoneService
from app.services.world_service import WorldService
from app.websockets.event_dispatcher import EventRegistry
from app.ai.agent_manager import AgentManager
from datetime import datetime
logger = logging.getLogger(__name__)

class EventType(str, Enum):
    SYSTEM = "system"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    MESSAGE = "message"

class Event(BaseModel):
    type: EventType
    content: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ConnectionManager:
    def __init__(self):
        self.connections: dict[str, WebSocket] = {}
        # self.character_locations: dict[str, tuple[str, str]] = {}
        # self.world_characters: dict[str, set[str]] = defaultdict(set)
        # self.zone_characters: dict[str, set[str]] = defaultdict(set)


    async def connect(
            self, 
            websocket: WebSocket,
            character_id: str
    ):
        self.connections[character_id] = websocket

    async def disconnect(self, websocket: WebSocket):
        for character_id, ws in list(self.connections.items()):
            if ws == websocket:
                await ws.close()
                del self.connections[character_id]
                break

    async def broadcast_to_all(self, event: Event):
        for websocket in self.connections.values():
            print("Broadcasting to all!")
            await websocket.send_json(event.model_dump_json())

    async def send_event(self, websocket: WebSocket, event: Event):
        try:
            await websocket.send_json(event.model_dump_json())
        except WebSocketDisconnect:
            await self.disconnect(websocket)
        except Exception:
            await self.disconnect(websocket)

connection_manager = ConnectionManager()
event_registry = EventRegistry(connection_manager)

async def authenticate(
    websocket: WebSocket,
    access_token: str,
    world_id: str,
    character_id: str,
    auth_service: AuthService,
    player_service: PlayerService,
    character_service: CharacterService
) -> bool:
    try:
        payload = auth_service.verify_token(access_token)
        user_id = payload.get("sub")

        if not user_id:
            await connection_manager.send_event(
                websocket,
                Event(
                    type=EventType.ERROR,
                    content="Invalid token",
                    timestamp=datetime.now()
                )
            )
            await connection_manager.disconnect(websocket)
            return False

        player = player_service.get_player(user_id)

        if not player:
            await connection_manager.send_event(
                websocket,
                Event(
                    type=EventType.ERROR,
                    content="User not found",
                    timestamp=datetime.now()
                )
            )
            await connection_manager.disconnect(websocket)
            return False

        character = character_service.get_character(character_id)

        if not character:
            await connection_manager.send_event(
                websocket,
                Event(
                    type=EventType.ERROR,
                    content="Character not found",
                    timestamp=datetime.now()
                )
            )
            await connection_manager.disconnect(websocket)
            return False

        if character.player_id != player.id:
            await connection_manager.send_event(
                websocket,
                Event(
                    type=EventType.ERROR,
                    content="Not authorized to use this character",
                    timestamp=datetime.now()
                )
            )
            await connection_manager.disconnect(websocket)
            return False
        
        return True 
    
    except Exception as e:
        await connection_manager.send_event(
            websocket,
            Event(
                type=EventType.ERROR,
                content=f"Authentication error: {str(e)}",
                timestamp=datetime.now()
            )
        )
        await connection_manager.disconnect(websocket)
        return False

async def handle_game_connection(
    websocket: WebSocket,
    world_id: str,
    character_id: str,
    access_token: str,
    db: Session = None
):
    try:
        await websocket.accept()
    except Exception as e:
        logger.error(f"Failed to accept WebSocket connection: {str(e)}")
        return
    
    auth_service = AuthService(db)
    player_service = PlayerService(db)
    character_service = CharacterService(db)
    zone_service = ZoneService(db)
    world_service = WorldService(db)
    event_service = EventService(db)
    agent_manager = AgentManager(db)

    if not await authenticate(
        websocket, 
        access_token, 
        world_id, 
        character_id,
        auth_service,
        player_service,
        character_service
        ):
        return
    
    await connection_manager.connect(websocket, character_id)

    try:
        while True:
            data = await websocket.receive_json()
            print(data)
            event = Event(**data)
            await event_registry.dispatcher.dispatch(
                websocket=websocket,
                event=event,
                agent_manager=agent_manager,
                world_id=world_id,
                character_id=character_id
            )
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: character {character_id}")
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}")
        await connection_manager.disconnect(websocket)
    finally:
        await connection_manager.disconnect(websocket)
        logger.info(f"Connection closed for character {character_id}")


# async def handle_game_connection(
#     websocket: WebSocket,
#     world_id: str,
#     character_id: str,
#     token: str,
#     db: Session = None
# ):
#     try:
#         await websocket.accept()
#     except Exception as e:
#         logger.error(f"Failed to accept WebSocket connection: {str(e)}")
#         return
    
#     auth_service = AuthService(db)
#     event_service = EventService(db)
    
#     # Authenticate
#     user_id = await authenticate_connection(websocket, token, character_id, auth_service)

#     if user_id is None:
#         return  # Authentication failed

#     character_service = CharacterService(db)
#     zone_service = ZoneService(db)
#     world_service = WorldService(db)
    
#     character = character_service.get_character(character_id)

#     if not character or character.player_id != user_id:
#         await websocket.send_json({
#             "type": "error",
#             "error": "You don't own this character or character not found",
#             "timestamp": datetime.now().isoformat()
#         })
#         await websocket.close(code=4003, reason="Not authorized")
#         return

#     # Register with connection manager
#     await connection_manager.connect(websocket, world_id, character_id)

#     # Optionally create an AI agent manager for message interpretation
#     agent_manager = AgentManager(db)
    
#     try:
#         while True:
#             raw_data = await websocket.receive_text()
#             try:
#                 event_data = json.loads(raw_data)
#             except json.JSONDecodeError:
#                 await websocket.send_json({
#                     "type": "error",
#                     "error": "Invalid JSON format",
#                     "timestamp": datetime.now().isoformat()
#                 })
#                 continue
            
#             # Dispatch the event
#             await event_registry.dispatcher.dispatch(
#                 websocket=websocket,
#                 event_data=event_data,
#                 agent_manager=agent_manager,
#                 world_id=world_id,
#                 character_id=character_id
#             )
    
#     except WebSocketDisconnect:
#         logger.info(f"WebSocket disconnected: character {character_id}")
#     except Exception as e:
#         logger.error(f"Error processing message: {str(e)}")
#         await websocket.close(code=1011, reason="Internal server error")
#     finally:
#         connection_manager.disconnect(websocket)
#         db.close()
#         logger.info(f"Connection closed for character {character_id}")

