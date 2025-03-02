# app/services/event_service.py
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, func, desc
from typing import List, Optional, Dict, Any, Tuple
import math
from datetime import datetime

from app.models.game_event import GameEvent, EventType, EventScope, EventParticipant
from app.models.entity import Entity
from app.models.character import Character


class EventService:
    """Service for handling game events"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_event(self, 
                   type: EventType, 
                   data: Dict[str, Any],
                   character_id: Optional[str] = None,
                   world_id: Optional[str] = None,
                   zone_id: Optional[str] = None,
                   target_entity_id: Optional[str] = None,
                   scope: EventScope = EventScope.PUBLIC,
                   participant_ids: List[str] = None) -> GameEvent:
        """
        Create a new game event
        
        Args:
            type: Type of event
            data: Event data
            character_id: ID of the character who initiated the event
            world_id: ID of the world where the event happened
            zone_id: ID of the zone where the event happened
            target_entity_id: ID of the target entity (if applicable)
            scope: Event visibility scope
            participant_ids: List of character IDs who can see private events
            
        Returns:
            The created game event
        """
        event = GameEvent(
            type=type,
            data=data,
            character_id=character_id,
            world_id=world_id,
            zone_id=zone_id,
            target_entity_id=target_entity_id,
            scope=scope
        )
        
        self.db.add(event)
        self.db.flush()  # Get the ID without committing
        
        # For private events, add participants
        if scope == EventScope.PRIVATE and participant_ids:
            for participant_id in participant_ids:
                participant = EventParticipant(
                    event_id=event.id,
                    character_id=participant_id
                )
                self.db.add(participant)
        
        self.db.commit()
        self.db.refresh(event)
        
        return event
    
    def create_message_event(self,
                          content: str,
                          character_id: str,
                          zone_id: Optional[str] = None,
                          world_id: Optional[str] = None,
                          scope: EventScope = EventScope.PUBLIC,
                          target_character_id: Optional[str] = None,
                          participant_ids: List[str] = None) -> GameEvent:
        """
        Create a new message event (convenience method)
        
        Args:
            content: Message content
            character_id: ID of the character sending the message
            zone_id: ID of the zone where the message was sent
            world_id: ID of the world
            scope: Message visibility scope
            target_character_id: ID of the character being messaged (for private)
            participant_ids: List of character IDs who can see private messages
            
        Returns:
            The created game event
        """
        data = {
            "content": content
        }
        
        # If target character is specified but no participant_ids, create the list
        if scope == EventScope.PRIVATE and target_character_id and not participant_ids:
            participant_ids = [character_id, target_character_id]
        
        return self.create_event(
            type=EventType.MESSAGE,
            data=data,
            character_id=character_id,
            zone_id=zone_id,
            world_id=world_id,
            scope=scope,
            participant_ids=participant_ids
        )
    
    def get_zone_events(self,
                      zone_id: str,
                      character_id: Optional[str] = None,
                      event_types: List[EventType] = None,
                      limit: int = 50,
                      before_timestamp = None) -> List[GameEvent]:
        """
        Get events in a zone that are visible to a character
        
        Args:
            zone_id: ID of the zone
            character_id: ID of the character (for private events)
            event_types: Optional filter for event types
            limit: Maximum number of events to return
            before_timestamp: Get events before this timestamp
            
        Returns:
            List of visible events
        """
        query = self.db.query(GameEvent).filter(
            GameEvent.zone_id == zone_id
        )
        
        # Filter by event types if provided
        if event_types:
            query = query.filter(GameEvent.type.in_(event_types))
        
        # Filter by timestamp if provided
        if before_timestamp:
            query = query.filter(GameEvent.created_at < before_timestamp)
        
        # Filter for visibility - include public events and private events where the character is a participant
        if character_id:
            query = query.filter(
                or_(
                    GameEvent.scope == EventScope.PUBLIC,
                    and_(
                        GameEvent.scope == EventScope.PRIVATE,
                        GameEvent.event_participants.any(
                            EventParticipant.character_id == character_id
                        )
                    )
                )
            )
        else:
            # If no character provided, only return public events
            query = query.filter(GameEvent.scope == EventScope.PUBLIC)
        
        # Order by created_at (newest first) and limit
        return query.order_by(desc(GameEvent.created_at)).limit(limit).all()
    
    def get_private_events(self,
                         character_id: str,
                         other_character_id: Optional[str] = None,
                         event_types: List[EventType] = None,
                         limit: int = 50,
                         before_timestamp = None) -> List[GameEvent]:
        """
        Get private events between characters
        
        Args:
            character_id: ID of the first character
            other_character_id: Optional ID of the second character
            event_types: Optional filter for event types
            limit: Maximum number of events to return
            before_timestamp: Get events before this timestamp
            
        Returns:
            List of private events
        """
        # Get event IDs where the character is a participant
        participant_event_ids = self.db.query(EventParticipant.event_id).filter(
            EventParticipant.character_id == character_id
        ).subquery()
        
        # Query for private events
        query = self.db.query(GameEvent).filter(
            GameEvent.scope == EventScope.PRIVATE,
            GameEvent.id.in_(participant_event_ids)
        )
        
        # If other_character_id provided, filter to events where both are participants
        if other_character_id:
            other_participant_event_ids = self.db.query(EventParticipant.event_id).filter(
                EventParticipant.character_id == other_character_id
            ).subquery()
            
            query = query.filter(GameEvent.id.in_(other_participant_event_ids))
        
        # Filter by event types if provided
        if event_types:
            query = query.filter(GameEvent.type.in_(event_types))
        
        # Filter by timestamp if provided
        if before_timestamp:
            query = query.filter(GameEvent.created_at < before_timestamp)
        
        # Order by created_at (newest first) and limit
        return query.order_by(desc(GameEvent.created_at)).limit(limit).all()
    
    def mark_event_as_read(self, event_id: str, character_id: str) -> bool:
        """
        Mark an event as read by a character
        
        Args:
            event_id: ID of the event to mark as read
            character_id: ID of the character marking the event as read
            
        Returns:
            True if successful, False otherwise
        """
        participant = self.db.query(EventParticipant).filter(
            EventParticipant.event_id == event_id,
            EventParticipant.character_id == character_id
        ).first()
        
        if not participant:
            return False
        
        participant.is_read = True
        self.db.commit()
        
        return True
    
    def get_unread_event_count(self, character_id: str, other_character_id: Optional[str] = None) -> int:
        """
        Get count of unread events for a character
        
        Args:
            character_id: ID of the character
            other_character_id: Optional ID of the other character to filter to
            
        Returns:
            Count of unread events
        """
        query = self.db.query(func.count(EventParticipant.id)).filter(
            EventParticipant.character_id == character_id,
            EventParticipant.is_read == False
        )
        
        if other_character_id:
            # Get events where the other character is also a participant
            other_events = self.db.query(EventParticipant.event_id).filter(
                EventParticipant.character_id == other_character_id
            ).subquery()
            
            query = query.filter(EventParticipant.event_id.in_(other_events))
        
        return query.scalar() or 0
    
    def get_active_conversations(self, character_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get active conversations for a character
        
        Args:
            character_id: ID of the character
            limit: Maximum number of conversations to return
            
        Returns:
            List of conversations with latest message info
        """
        # Get event IDs where the character is a participant
        participations = self.db.query(EventParticipant.event_id).filter(
            EventParticipant.character_id == character_id
        ).subquery()
        
        # Get private message events
        events = self.db.query(GameEvent).filter(
            GameEvent.scope == EventScope.PRIVATE,
            GameEvent.type == EventType.MESSAGE,
            GameEvent.id.in_(participations)
        ).order_by(desc(GameEvent.created_at)).all()
        
        # Group by conversation partner
        conversations = {}
        for event in events:
            # Get the other participant(s)
            other_participants = self.db.query(EventParticipant).filter(
                EventParticipant.event_id == event.id,
                EventParticipant.character_id != character_id
            ).all()
            
            for participant in other_participants:
                other_id = participant.character_id
                
                if other_id not in conversations:
                    # Get the character info
                    other_character = self.db.query(Character).filter(
                        Character.id == other_id
                    ).first()
                    
                    if not other_character:
                        continue
                    
                    # Create conversation entry
                    conversations[other_id] = {
                        "character_id": other_id,
                        "character_name": other_character.name,
                        "latest_message": event.data.get("content", ""),
                        "latest_timestamp": event.created_at.isoformat(),
                        "unread_count": self.get_unread_event_count(character_id, other_id)
                    }
                    break  # Only need one conversation per partner
        
        # Convert to list and sort by latest message time
        result = list(conversations.values())
        result.sort(key=lambda x: x["latest_timestamp"], reverse=True)
        
        return result[:limit]