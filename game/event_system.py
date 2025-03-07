"""
Event system for the Agentique Game Engine.
Implements a publish-subscribe pattern for game events.
"""
import asyncio
import logging
from typing import Dict, List, Callable, Awaitable, Optional, Any, Set
from base_models import Event, EventType

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agentique.events")

# Type for event handlers
EventHandler = Callable[[Event], Awaitable[None]]

class EventBus:
    """
    Centralized event bus for publishing and subscribing to events.
    
    This implements a publish-subscribe pattern where:
    - Components can subscribe to specific event types
    - Components can publish events to the bus
    - The bus delivers events to all subscribers
    """
    
    def __init__(self):
        self._subscribers: Dict[EventType, List[EventHandler]] = {}
        self._global_subscribers: List[EventHandler] = []
        self._event_history: List[Event] = []
        self._max_history = 1000  # Maximum events to keep in history
    
    def subscribe(self, event_type: Optional[EventType], handler: EventHandler) -> None:
        """
        Subscribe a handler to a specific event type, or to all events if None.
        
        Args:
            event_type: The type of event to subscribe to, or None for all events
            handler: Async function that will be called when events occur
        """
        if event_type is None:
            self._global_subscribers.append(handler)
        else:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            self._subscribers[event_type].append(handler)
    
    def unsubscribe(self, event_type: Optional[EventType], handler: EventHandler) -> bool:
        """
        Remove a subscription for a handler.
        
        Args:
            event_type: The event type the handler was subscribed to
            handler: The handler to remove
            
        Returns:
            bool: True if the handler was found and removed, False otherwise
        """
        if event_type is None:
            if handler in self._global_subscribers:
                self._global_subscribers.remove(handler)
                return True
        elif event_type in self._subscribers:
            if handler in self._subscribers[event_type]:
                self._subscribers[event_type].remove(handler)
                return True
        return False
    
    async def publish(self, event: Event) -> None:
        """
        Publish an event to all subscribers.
        
        Args:
            event: The event to publish
        """
        # Add to history
        self._add_to_history(event)
        
        # Call specific subscribers
        tasks = []
        
        # Type-specific subscribers
        if event.type in self._subscribers:
            for handler in self._subscribers[event.type]:
                tasks.append(self._call_handler(handler, event))
        
        # Global subscribers
        for handler in self._global_subscribers:
            tasks.append(self._call_handler(handler, event))
        
        # Wait for all handlers to complete
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _call_handler(self, handler: EventHandler, event: Event) -> None:
        """Call a handler and log any exceptions"""
        try:
            await handler(event)
        except Exception as e:
            logger.error(f"Error in event handler: {str(e)}")
    
    def _add_to_history(self, event: Event) -> None:
        """Add an event to the history, maintaining the maximum size"""
        self._event_history.append(event)
        if len(self._event_history) > self._max_history:
            self._event_history = self._event_history[-self._max_history:]
    
    def get_recent_events(self, limit: int = 10, 
                         event_types: Optional[Set[EventType]] = None,
                         source_id: Optional[str] = None, 
                         target_id: Optional[str] = None) -> List[Event]:
        """
        Get recent events, optionally filtered by type, source, or target.
        
        Args:
            limit: Maximum number of events to return
            event_types: Set of event types to include, or None for all
            source_id: Filter by source ID, or None for all
            target_id: Filter by target ID, or None for all
            
        Returns:
            List of matching events, newest first
        """
        filtered = self._event_history
        
        # Apply filters
        if event_types:
            filtered = [e for e in filtered if e.type in event_types]
        if source_id is not None:
            filtered = [e for e in filtered if e.source_id == source_id]
        if target_id is not None:
            filtered = [e for e in filtered if e.target_id == target_id]
        
        # Return the most recent events up to the limit
        return filtered[-limit:][::-1]