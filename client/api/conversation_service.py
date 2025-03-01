#!/usr/bin/env python
# Conversation service for managing conversations
from typing import Dict, Any, Optional, List, Tuple

from client.api.base_service import BaseService, APIError
from client.game.state import game_state


class ConversationService(BaseService):
    """Service for conversation-related API operations"""
    
    async def get_conversations(self) -> List[Dict[str, Any]]:
        """Get list of user's conversations"""
        try:
            response = await self.get("/conversations/")
            return response.get("items", [])
        except APIError as e:
            print(f"Failed to get conversations: {e.detail}")
            return []
        except Exception as e:
            print(f"Error getting conversations: {str(e)}")
            return []
    
    async def get_recent_conversations(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent conversations with latest message info"""
        try:
            return await self.get(f"/conversations/recent?limit={limit}")
        except APIError as e:
            print(f"Failed to get recent conversations: {e.detail}")
            return []
        except Exception as e:
            print(f"Error getting recent conversations: {str(e)}")
            return []
    
    async def create_conversation(self, title: str, character_id: str, 
                                 agent_character_ids: Optional[List[str]] = None,
                                 world_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Create a new conversation"""
        if not game_state.current_user_id:
            print("User not authenticated")
            return None
            
        try:
            payload = {
                "title": title,
                "user_character_ids": [character_id],
                "user_id": game_state.current_user_id
            }
            
            if agent_character_ids:
                payload["agent_character_ids"] = agent_character_ids
                
            # Add world_id if provided
            if world_id:
                payload["world_id"] = world_id
                
            conversation = await self.post("/conversations/", payload)
            
            if conversation:
                game_state.current_conversation_id = conversation.get("id")
                
                # Find our participant ID
                participants = conversation.get("participants", [])
                for participant in participants:
                    # Match on user_id and character_id
                    if (participant.get("user_id") == game_state.current_user_id and 
                        participant.get("character_id") == character_id):
                        game_state.current_participant_id = participant.get("id")
                        break
            
            return conversation
        except APIError as e:
            print(f"Failed to create conversation: {e.detail}")
            return None
        except Exception as e:
            print(f"Error creating conversation: {str(e)}")
            return None
    
    async def get_conversation(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """Get details of a specific conversation"""
        try:
            return await self.get(f"/conversations/{conversation_id}")
        except APIError as e:
            print(f"Failed to get conversation: {e.detail}")
            return None
        except Exception as e:
            print(f"Error getting conversation: {str(e)}")
            return None
            
    async def get_conversation_limits(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """Get message limits for a conversation"""
        try:
            return await self.get(f"/conversations/{conversation_id}/limits")
        except APIError as e:
            print(f"Failed to get conversation limits: {e.detail}")
            return None
        except Exception as e:
            print(f"Error getting conversation limits: {str(e)}")
            return None
    
    async def update_conversation(self, conversation_id: str, 
                                update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update a conversation"""
        try:
            return await self.put(f"/conversations/{conversation_id}", update_data)
        except APIError as e:
            print(f"Failed to update conversation: {e.detail}")
            return None
        except Exception as e:
            print(f"Error updating conversation: {str(e)}")
            return None
    
    async def delete_conversation(self, conversation_id: str) -> bool:
        """Delete a conversation"""
        try:
            await self.delete(f"/conversations/{conversation_id}")
            
            # If this was the current conversation, clear selection
            if conversation_id == game_state.current_conversation_id:
                game_state.clear_conversation()
            
            return True
        except APIError as e:
            print(f"Failed to delete conversation: {e.detail}")
            return False
        except Exception as e:
            print(f"Error deleting conversation: {str(e)}")
            return False
    
    async def add_participant(self, conversation_id: str, character_id: str, 
                             user_id: Optional[str] = None, 
                             agent_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Add a participant to a conversation"""
        try:
            payload = {
                "character_id": character_id
            }
            
            if user_id:
                payload["user_id"] = user_id
            elif agent_id:
                payload["agent_id"] = agent_id
            
            return await self.post(f"/conversations/{conversation_id}/participants", payload)
        except APIError as e:
            print(f"Failed to add participant: {e.detail}")
            return None
        except Exception as e:
            print(f"Error adding participant: {str(e)}")
            return None
    
    async def remove_participant(self, conversation_id: str, participant_id: str) -> bool:
        """Remove a participant from a conversation"""
        try:
            await self.delete(f"/conversations/{conversation_id}/participants/{participant_id}")
            return True
        except APIError as e:
            print(f"Failed to remove participant: {e.detail}")
            return False
        except Exception as e:
            print(f"Error removing participant: {str(e)}")
            return False
            
    async def find_or_create_zone_conversation(self, zone_id: str, character_id: str) -> Optional[Dict[str, Any]]:
        """
        Find an existing zone conversation or create a new one.
        
        This is an extension to the original API - it looks for conversations 
        in the specified zone and joins or creates one for the character.
        """
        try:
            # Get all conversations
            conversations = await self.get_conversations()
            
            # Find conversations for this zone
            zone_conversations = []
            for conv in conversations:
                # Check if linked to this zone
                if conv.get("world_id") and (
                   conv.get("zone_id") == zone_id or 
                   conv.get("title", "").lower().startswith(f"zone:")):
                    zone_conversations.append(conv)
            
            # If found, use the first one
            if zone_conversations:
                conversation = zone_conversations[0]
                conversation_id = conversation.get("id")
                game_state.current_conversation_id = conversation_id
                
                # Get full conversation details
                conversation = await self.get_conversation(conversation_id)
                
                # Check if we're already a participant
                participants = conversation.get("participants", [])
                for participant in participants:
                    if (participant.get("user_id") == game_state.current_user_id and 
                        participant.get("character_id") == character_id):
                        game_state.current_participant_id = participant.get("id")
                        return conversation
                
                # If not a participant, join the conversation
                participant = await self.add_participant(
                    conversation_id=conversation_id,
                    character_id=character_id,
                    user_id=game_state.current_user_id
                )
                
                if participant:
                    game_state.current_participant_id = participant.get("id")
                
                return conversation
            
            # If no existing conversation, create a new one
            # Get zone info to use in title
            from client.api.zone_service import ZoneService
            zone_service = ZoneService()
            zone = await zone_service.get_zone(zone_id)
            zone_name = zone.get("name", "Unknown Zone") if zone else "Zone Chat"
            
            # Create conversation with zone-specific title
            title = f"Zone: {zone_name}"
            conversation = await self.create_conversation(
                title=title, 
                character_id=character_id,
                world_id=zone.get("world_id") if zone else None
            )
            
            return conversation
        except Exception as e:
            print(f"Error finding/creating zone conversation: {str(e)}")
            return None