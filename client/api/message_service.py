#!/usr/bin/env python
# Message service for managing messages
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime

from client.api.base_service import BaseService, APIError
from client.game.state import game_state


class MessageService(BaseService):
    """Service for message-related API operations"""
    
    async def get_conversation_messages(self, conversation_id: str, 
                                      page: int = 1, page_size: int = 20,
                                      chronological: bool = True) -> List[Dict[str, Any]]:
        """Get messages from a conversation with pagination"""
        try:
            params = {
                "page": page,
                "page_size": page_size,
                "chronological": str(chronological).lower()
            }
            
            response = await self.get(f"/messages/conversations/{conversation_id}", params)
            return response.get("items", [])
        except APIError as e:
            print(f"Failed to get messages: {e.detail}")
            return []
        except Exception as e:
            print(f"Error getting messages: {str(e)}")
            return []
    
    async def get_recent_messages(self, conversation_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Get most recent messages from a conversation"""
        try:
            params = {
                "limit": limit
            }
            
            return await self.get(f"/messages/conversations/{conversation_id}/recent", params)
        except APIError as e:
            print(f"Failed to get recent messages: {e.detail}")
            return []
        except Exception as e:
            print(f"Error getting recent messages: {str(e)}")
            return []
    
    async def send_message(self, conversation_id: str, participant_id: str, 
                          content: str) -> Optional[Dict[str, Any]]:
        """Send a message in a conversation"""
        try:
            payload = {
                "content": content,
                "participant_id": participant_id
            }
            
            return await self.post(f"/messages/conversations/{conversation_id}", payload)
        except APIError as e:
            print(f"Failed to send message: {e.detail}")
            return None
        except Exception as e:
            print(f"Error sending message: {str(e)}")
            return None
    
    async def get_remaining_messages(self) -> Dict[str, Any]:
        """Get information about remaining daily messages"""
        try:
            return await self.get("/messages/remaining")
        except APIError as e:
            print(f"Failed to get remaining messages: {e.detail}")
            return {
                "is_premium": game_state.is_premium,
                "daily_limit": 50 if not game_state.is_premium else 1000,
                "remaining": 0,
                "has_reached_limit": True
            }
        except Exception as e:
            print(f"Error getting remaining messages: {str(e)}")
            return {
                "is_premium": game_state.is_premium,
                "daily_limit": 50 if not game_state.is_premium else 1000,
                "remaining": 0,
                "has_reached_limit": True
            }
    
    async def search_messages(self, conversation_id: str, query: str, 
                            page: int = 1, page_size: int = 20) -> List[Dict[str, Any]]:
        """Search for messages in a conversation by content"""
        try:
            params = {
                "query": query,
                "page": page,
                "page_size": page_size,
                "conversation_id": conversation_id
            }
            
            response = await self.get("/messages/search/", params)
            return response.get("items", [])
        except APIError as e:
            print(f"Failed to search messages: {e.detail}")
            return []
        except Exception as e:
            print(f"Error searching messages: {str(e)}")
            return []