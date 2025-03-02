# app/api/v1/events.py
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime

from app.database import get_db
from app.api.auth import get_current_user
from app.api.dependencies import get_service
from app.models.player import Player as User
from app.models.game_event import EventType, EventScope
from app.services.event_service import EventService
from app.services.character_service import CharacterService

router = APIRouter()


@router.get("/zone/{zone_id}", response_model=List[Dict[str, Any]])
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
    Get events that occurred in a zone
    
    Returns events that are visible to the specified character:
    - All public events in the zone
    - Private events where the character is a participant
    """
    # Check if user can access this character
    character = character_service.get_character(character_id)
    if not character or character.player_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view events as your own character"
        )
    
    # Get the events
    events = event_service.get_zone_events(
        zone_id=zone_id,
        character_id=character_id,
        event_types=event_types,
        limit=limit,
        before_timestamp=before
    )
    
    # Format the events for the response
    result = []
    for event in events:
        # Get character info
        character = character_service.get_character(event.character_id) if event.character_id else None
        
        # Format based on event type
        event_data = {
            "id": event.id,
            "type": event.type,
            "character_id": event.character_id,
            "character_name": character.name if character else None,
            "zone_id": event.zone_id,
            "timestamp": event.created_at.isoformat(),
            "data": event.data
        }
        
        # Add target entity info if applicable
        if event.target_entity_id:
            from app.services.entity_service import EntityService
            entity_service = EntityService(event_service.db)
            entity = entity_service.get_entity(event.target_entity_id)
            if entity:
                event_data["target_entity"] = {
                    "id": entity.id,
                    "name": entity.name,
                    "type": entity.type
                }
        
        result.append(event_data)
    
    return result


@router.get("/private", response_model=List[Dict[str, Any]])
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
    Get private events for a character
    
    Returns private events where the character is a participant:
    - If other_character_id is provided, only returns events where both characters are participants
    - Otherwise returns all private events for the character
    """
    # Check if user can access this character
    character = character_service.get_character(character_id)
    if not character or character.player_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view events as your own character"
        )
    
    # Get the events
    events = event_service.get_private_events(
        character_id=character_id,
        other_character_id=other_character_id,
        event_types=event_types,
        limit=limit,
        before_timestamp=before
    )
    
    # Format the events for the response
    result = []
    for event in events:
        # Get character info
        character = character_service.get_character(event.character_id) if event.character_id else None
        
        # Format based on event type
        event_data = {
            "id": event.id,
            "type": event.type,
            "character_id": event.character_id,
            "character_name": character.name if character else None,
            "timestamp": event.created_at.isoformat(),
            "data": event.data
        }
        
        # Add other participants info
        event_data["participants"] = []
        for participant in event.event_participants:
            part_character = character_service.get_character(participant.character_id)
            if part_character:
                event_data["participants"].append({
                    "character_id": part_character.id,
                    "character_name": part_character.name,
                    "is_read": participant.is_read
                })
        
        result.append(event_data)
    
    return result


@router.get("/active-conversations", response_model=List[Dict[str, Any]])
async def get_active_conversations(
    character_id: str = Query(..., description="Character ID to get conversations for"),
    limit: int = Query(10, le=50, description="Maximum number of conversations to return"),
    current_user: User = Depends(get_current_user),
    event_service: EventService = Depends(get_service(EventService)),
    character_service: CharacterService = Depends(get_service(CharacterService))
):
    """
    Get active conversations for a character
    
    Returns a list of other characters the specified character has exchanged private messages with,
    along with the latest message in each conversation
    """
    # Check if user can access this character
    character = character_service.get_character(character_id)
    if not character or character.player_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view conversations as your own character"
        )
    
    # Get the conversations
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
    Mark an event as read by a character
    
    This is used for tracking read status of private events
    """
    # Check if user can access this character
    character = character_service.get_character(character_id)
    if not character or character.player_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only mark events as read for your own characters"
        )
    
    # Mark the event as read
    success = event_service.mark_event_as_read(
        event_id=event_id,
        character_id=character_id
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found or character is not a participant"
        )
    
    return {
        "success": True,
        "event_id": event_id,
        "character_id": character_id
    }


@router.get("/unread-count", response_model=Dict[str, int])
async def get_unread_event_count(
    character_id: str = Query(..., description="Character ID to get unread count for"),
    other_character_id: Optional[str] = Query(None, description="Filter to events with this character"),
    current_user: User = Depends(get_current_user),
    event_service: EventService = Depends(get_service(EventService)),
    character_service: CharacterService = Depends(get_service(CharacterService))
):
    """
    Get the number of unread events for a character
    
    If other_character_id is provided, only counts events where both characters are participants
    """
    # Check if user can access this character
    character = character_service.get_character(character_id)
    if not character or character.player_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only get unread counts for your own characters"
        )
    
    # Get unread counts
    count = event_service.get_unread_event_count(
        character_id=character_id,
        other_character_id=other_character_id
    )
    
    return {
        "character_id": character_id,
        "unread_count": count
    }