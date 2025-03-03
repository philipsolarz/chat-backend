#!/usr/bin/env python
# Updated Event service for managing game events
from typing import Dict, Any, Optional, List
from datetime import datetime

from client.api.base_service import BaseService, APIError
from client.game.state import game_state
from client.ui.console import console

class EventService(BaseService):
    """Service for game event-related API operations"""
    
    async def get_zone_events(self, zone_id: str, 
                            character_id: Optional[str] = None,
                            event_types: Optional[List[str]] = None,
                            limit: int = 50,
                            before_timestamp: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Get events that occurred in a zone"""
        try:
            params = {
                "limit": limit
            }
            
            if character_id:
                params["character_id"] = character_id
                
            if event_types:
                params["event_types"] = ",".join(event_types)
                
            if before_timestamp:
                params["before"] = before_timestamp.isoformat()
                
            # Fixed URL construction - zone_id goes in the path, not in params
            return await self.get(f"/events/zone/{zone_id}", params)
        except APIError as e:
            console.print(f"[red]Failed to get zone events: {e.detail}[/red]")
            return []
        except Exception as e:
            console.print(f"[red]Error getting zone events: {str(e)}[/red]")
            return []
    
    async def get_private_events(self, character_id: str,
                               other_character_id: Optional[str] = None,
                               event_types: Optional[List[str]] = None,
                               limit: int = 50,
                               before_timestamp: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Get private events for a character"""
        try:
            params = {
                "character_id": character_id,
                "limit": limit
            }
            
            if other_character_id:
                params["other_character_id"] = other_character_id
                
            if event_types:
                params["event_types"] = ",".join(event_types)
                
            if before_timestamp:
                params["before"] = before_timestamp.isoformat()
                
            return await self.get("/events/private", params)
        except APIError as e:
            console.print(f"[red]Failed to get private events: {e.detail}[/red]")
            return []
        except Exception as e:
            console.print(f"[red]Error getting private events: {str(e)}[/red]")
            return []
    
    async def create_message_event(self, content: str, character_id: str,
                                 zone_id: Optional[str] = None,
                                 world_id: Optional[str] = None,
                                 target_character_id: Optional[str] = None,
                                 scope: str = "public") -> Optional[Dict[str, Any]]:
        """Create a message event"""
        try:
            payload = {
                "content": content,
                "character_id": character_id,
                "scope": scope
            }
            
            if zone_id:
                payload["zone_id"] = zone_id
                
            if world_id:
                payload["world_id"] = world_id
                
            if target_character_id:
                payload["target_character_id"] = target_character_id
                
            return await self.post("/events/message", payload)
        except APIError as e:
            console.print(f"[red]Failed to create message event: {e.detail}[/red]")
            return None
        except Exception as e:
            console.print(f"[red]Error creating message event: {str(e)}[/red]")
            return None
    
    async def mark_event_as_read(self, event_id: str, character_id: str) -> bool:
        """Mark an event as read by a character"""
        try:
            await self.post(f"/events/mark-read/{event_id}", {"character_id": character_id})
            return True
        except APIError as e:
            console.print(f"[red]Failed to mark event as read: {e.detail}[/red]")
            return False
        except Exception as e:
            console.print(f"[red]Error marking event as read: {str(e)}[/red]")
            return False
    
    async def get_unread_event_count(self, character_id: str, other_character_id: Optional[str] = None) -> int:
        """Get the number of unread events for a character"""
        try:
            params = {"character_id": character_id}
            
            if other_character_id:
                params["other_character_id"] = other_character_id
                
            response = await self.get("/events/unread-count", params)
            return response.get("unread_count", 0)
        except APIError as e:
            console.print(f"[red]Failed to get unread count: {e.detail}[/red]")
            return 0
        except Exception as e:
            console.print(f"[red]Error getting unread count: {str(e)}[/red]")
            return 0
    
    async def get_active_conversations(self, character_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get active conversations for a character"""
        try:
            params = {
                "character_id": character_id,
                "limit": limit
            }
            
            return await self.get("/events/active-conversations", params)
        except APIError as e:
            console.print(f"[red]Failed to get active conversations: {e.detail}[/red]")
            return []
        except Exception as e:
            console.print(f"[red]Error getting active conversations: {str(e)}[/red]")
            return []