from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy import desc, func, or_, and_

from app.schemas import (
    EventType as SchemaEventType,
    EventScope as SchemaEventScope,
    GameEventResponse,
    UnreadCountResponse,
    ConversationSummary
)
from app.database import get_db
from app.api.auth import get_current_user
from app.api.dependencies import get_service
from app.models.player import Player as User
from app.models.game_event import GameEvent, EventType, EventScope, EventParticipant
from app.services.event_service import EventService
from app.services.character_service import CharacterService

router = APIRouter()

@router.get("/zone/{zone_id}", response_model=List[GameEventResponse])
async def get_zone_events(
    zone_id: str,
    character_id: str = Query(..., description="Character ID viewing events"),
    event_types: Optional[List[EventType]] = Query(None, description="Filter by event types"),
    limit: int = Query(50, le=100, description="Maximum number of events to return"),
    before: Optional[datetime] = Query(None, description="Get events before this timestamp"),
    current_user: User = Depends(get_current_user),
    event_service: EventService = Depends(get_service(EventService)),
    character_service: CharacterService = Depends(get_service(CharacterService))
):
    """
    Get events that occurred in a zone.
    Returns events that are visible to the specified character (public events plus private events where the character is a participant).
    """
    character = character_service.get_character(character_id)
    if not character or character.player_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view events as your own character"
        )
    
    events = event_service.get_zone_events(
        zone_id=zone_id,
        character_id=character_id,
        event_types=event_types,
        limit=limit,
        before_timestamp=before
    )
    
    result = []
    for event in events:
        evt = {
            "id": event.id,
            "type": event.type,
            "data": event.data,
            "character_id": event.character_id,
            "zone_id": event.zone_id,
            "world_id": event.world_id,
            "target_entity_id": event.target_entity_id,
            "scope": event.scope,
            "created_at": event.created_at,
            "participants": [
                {
                    "id": participant.id,
                    "event_id": participant.event_id,
                    "character_id": participant.character_id,
                    "is_read": participant.is_read,
                    "created_at": participant.created_at
                }
                for participant in event.event_participants
            ]
        }
        
        if event.character_id:
            sender = character_service.get_character(event.character_id)
            evt["character_name"] = sender.name if sender else None
        
        if event.target_entity_id:
            from app.services.entity_service import EntityService
            # Instantiate EntityService using the current DB session
            entity_service = EntityService(get_db())
            entity = entity_service.get_entity(event.target_entity_id)
            if entity:
                evt["target_entity_name"] = entity.name
        
        result.append(evt)
    
    return result

@router.get("/private", response_model=List[GameEventResponse])
async def get_private_events(
    character_id: str = Query(..., description="Character ID viewing events"),
    other_character_id: Optional[str] = Query(None, description="Filter to events with this character"),
    event_types: Optional[List[EventType]] = Query(None, description="Filter by event types"),
    limit: int = Query(50, le=100, description="Maximum number of events to return"),
    before: Optional[datetime] = Query(None, description="Get events before this timestamp"),
    current_user: User = Depends(get_current_user),
    event_service: EventService = Depends(get_service(EventService)),
    character_service: CharacterService = Depends(get_service(CharacterService))
):
    """
    Get private events for a character.
    If `other_character_id` is provided, only events where both characters are participants are returned.
    """
    character = character_service.get_character(character_id)
    if not character or character.player_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view events as your own character"
        )
    
    events = event_service.get_private_events(
        character_id=character_id,
        other_character_id=other_character_id,
        event_types=event_types,
        limit=limit,
        before_timestamp=before
    )
    
    result = []
    for event in events:
        evt = {
            "id": event.id,
            "type": event.type,
            "data": event.data,
            "character_id": event.character_id,
            "scope": event.scope,
            "created_at": event.created_at,
            "participants": []
        }
        if event.character_id:
            sender = character_service.get_character(event.character_id)
            evt["character_name"] = sender.name if sender else None
        
        for participant in event.event_participants:
            part = character_service.get_character(participant.character_id)
            if part:
                evt["participants"].append({
                    "id": participant.id,
                    "event_id": participant.event_id,
                    "character_id": part.id,
                    "character_name": part.name,
                    "is_read": participant.is_read,
                    "created_at": participant.created_at
                })
        
        result.append(evt)
    
    return result

@router.get("/active-conversations", response_model=List[ConversationSummary])
async def get_active_conversations(
    character_id: str = Query(..., description="Character ID to get conversations for"),
    limit: int = Query(10, le=50, description="Maximum number of conversations to return"),
    current_user: User = Depends(get_current_user),
    event_service: EventService = Depends(get_service(EventService)),
    character_service: CharacterService = Depends(get_service(CharacterService))
):
    """
    Get active conversations for a character.
    Returns a list of conversation summaries (other characters, latest message, timestamp, unread count).
    """
    character = character_service.get_character(character_id)
    if not character or character.player_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view conversations as your own character"
        )
    
    conversations = event_service.get_active_conversations(
        character_id=character_id,
        limit=limit
    )
    
    return conversations

@router.post("/mark-read/{event_id}", response_model=Dict[str, Any])
async def mark_event_as_read(
    event_id: str,
    character_id: str = Query(..., description="Character ID marking event as read"),
    current_user: User = Depends(get_current_user),
    event_service: EventService = Depends(get_service(EventService)),
    character_service: CharacterService = Depends(get_service(CharacterService))
):
    """
    Mark an event as read by a character.
    """
    character = character_service.get_character(character_id)
    if not character or character.player_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only mark events as read for your own character"
        )
    
    success = event_service.mark_event_as_read(
        event_id=event_id,
        character_id=character_id
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found or character is not a participant"
        )
    
    return {"success": True, "event_id": event_id, "character_id": character_id}

@router.get("/unread-count", response_model=UnreadCountResponse)
async def get_unread_event_count(
    character_id: str = Query(..., description="Character ID to get unread count for"),
    other_character_id: Optional[str] = Query(None, description="Filter to events with this character"),
    current_user: User = Depends(get_current_user),
    event_service: EventService = Depends(get_service(EventService)),
    character_service: CharacterService = Depends(get_service(CharacterService))
):
    """
    Get the number of unread events for a character.
    If `other_character_id` is provided, counts only events where both characters are participants.
    """
    character = character_service.get_character(character_id)
    if not character or character.player_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only get unread counts for your own character"
        )
    
    count = event_service.get_unread_event_count(
        character_id=character_id,
        other_character_id=other_character_id
    )
    
    return {"character_id": character_id, "unread_count": count}
