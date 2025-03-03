# app/services/message_service.py
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
import math

from app.models.message import Message
from app.models.conversation import Conversation, ConversationParticipant
from app.models.character import Character
from app.models.agent import Agent
from app.models.player import Player as User


class MessageService:
    """Service for handling message operations."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_message(
        self, 
        conversation_id: str, 
        participant_id: str, 
        content: str
    ) -> Optional[Message]:
        """
        Create a new message in a conversation.

        Args:
            conversation_id: ID of the conversation.
            participant_id: ID of the conversation participant sending the message.
            content: The message content.
            
        Returns:
            The created Message instance, or None if the participant doesn't exist.
        """
        # Check if participant exists in this conversation.
        participant = self.db.query(ConversationParticipant).filter(
            ConversationParticipant.id == participant_id,
            ConversationParticipant.conversation_id == conversation_id
        ).first()
        
        if not participant:
            return None
        
        # Create and persist the message.
        message = Message(
            content=content,
            conversation_id=conversation_id,
            participant_id=participant_id
        )
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)
        
        # Update conversation's updated_at timestamp.
        conversation = self.db.query(Conversation).filter(
            Conversation.id == conversation_id
        ).first()
        if conversation:
            conversation.updated_at = datetime.utcnow()
            self.db.commit()
        
        return message
    
    def get_message(self, message_id: str) -> Optional[Message]:
        """Retrieve a message by its ID."""
        return self.db.query(Message).filter(Message.id == message_id).first()
    
    def get_messages(
        self, 
        filters: Dict[str, Any] = None, 
        page: int = 1, 
        page_size: int = 20, 
        sort_by: str = "created_at", 
        sort_desc: bool = False,
        before_timestamp: Optional[datetime] = None,
        after_timestamp: Optional[datetime] = None
    ) -> Tuple[List[Message], int, int]:
        """
        Get messages with flexible filtering options.
        
        Args:
            filters: Dictionary of filter conditions.
            page: Page number (starting from 1).
            page_size: Number of records per page.
            sort_by: Field to sort by.
            sort_desc: Whether to sort in descending order.
            before_timestamp: Only return messages created before this time.
            after_timestamp: Only return messages created after this time.
            
        Returns:
            Tuple of (messages, total_count, total_pages).
        """
        query = self.db.query(Message)
        
        if filters:
            if 'conversation_id' in filters:
                query = query.filter(Message.conversation_id == filters['conversation_id'])
            if 'participant_id' in filters:
                query = query.filter(Message.participant_id == filters['participant_id'])
            if 'character_id' in filters:
                query = query.join(
                    ConversationParticipant,
                    Message.participant_id == ConversationParticipant.id
                ).filter(
                    ConversationParticipant.character_id == filters['character_id']
                )
            if 'user_id' in filters:
                query = query.join(
                    ConversationParticipant,
                    Message.participant_id == ConversationParticipant.id
                ).filter(
                    ConversationParticipant.user_id == filters['user_id']
                )
            if 'agent_id' in filters:
                query = query.join(
                    ConversationParticipant,
                    Message.participant_id == ConversationParticipant.id
                ).filter(
                    ConversationParticipant.agent_id == filters['agent_id']
                )
            if 'content' in filters:
                query = query.filter(Message.content.ilike(f"%{filters['content']}%"))
        
        if before_timestamp:
            query = query.filter(Message.created_at < before_timestamp)
        if after_timestamp:
            query = query.filter(Message.created_at > after_timestamp)
        
        total_count = query.count()
        total_pages = math.ceil(total_count / page_size) if total_count > 0 else 1
        
        if hasattr(Message, sort_by):
            sort_field = getattr(Message, sort_by)
            query = query.order_by(sort_field.desc() if sort_desc else sort_field)
        else:
            query = query.order_by(Message.created_at.desc() if sort_desc else Message.created_at)
        
        offset = (page - 1) * page_size if page > 0 else 0
        messages = query.offset(offset).limit(page_size).all()
        
        return messages, total_count, total_pages
    
    def get_conversation_messages(
        self, 
        conversation_id: str, 
        page: int = 1, 
        page_size: int = 20,
        chronological: bool = True,
        before_timestamp: Optional[datetime] = None,
        after_timestamp: Optional[datetime] = None
    ) -> Tuple[List[Message], int, int]:
        """
        Get messages for a conversation with optional filters.
        
        Args:
            conversation_id: The conversation ID.
            page: Page number (starting from 1).
            page_size: Records per page.
            chronological: If True, return oldest first; if False, newest first.
            before_timestamp: Only return messages created before this time.
            after_timestamp: Only return messages created after this time.
            
        Returns:
            Tuple of (messages, total_count, total_pages).
        """
        filters = {'conversation_id': conversation_id}
        sort_desc = not chronological
        
        return self.get_messages(
            filters=filters,
            page=page,
            page_size=page_size,
            sort_by="created_at",
            sort_desc=sort_desc,
            before_timestamp=before_timestamp,
            after_timestamp=after_timestamp
        )
    
    def get_recent_messages(self, conversation_id: str, limit: int = 20) -> List[Message]:
        """
        Get the most recent messages for a conversation.
        Returns messages in reverse chronological order (newest first).
        """
        messages, _, _ = self.get_messages(
            filters={'conversation_id': conversation_id},
            page=1,
            page_size=limit,
            sort_by="created_at",
            sort_desc=True
        )
        return messages
    
    def update_message(self, message_id: str, content: str) -> Optional[Message]:
        """Update the content of a message."""
        message = self.get_message(message_id)
        if not message:
            return None
        
        message.content = content
        message.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(message)
        
        return message
    
    def delete_message(self, message_id: str) -> bool:
        """Delete a message by its ID."""
        message = self.get_message(message_id)
        if not message:
            return False
        
        self.db.delete(message)
        self.db.commit()
        return True
    
    def get_sender_info(self, message: Message) -> Dict[str, Any]:
        """
        Retrieve detailed information about the sender of a message.
        
        Returns a dictionary with participant, character, and, if applicable,
        user or agent details.
        """
        if not message.participant_id:
            return {
                "participant_id": None,
                "character_id": None,
                "character_name": "Unknown",
                "user_id": None,
                "agent_id": None,
                "is_ai": False
            }
        
        participant = self.db.query(ConversationParticipant).filter(
            ConversationParticipant.id == message.participant_id
        ).first()
        
        if not participant:
            return {
                "participant_id": message.participant_id,
                "character_id": None,
                "character_name": "Unknown",
                "user_id": None,
                "agent_id": None,
                "is_ai": False
            }
        
        character = self.db.query(Character).filter(
            Character.id == participant.character_id
        ).first()
        
        result = {
            "participant_id": participant.id,
            "character_id": participant.character_id,
            "character_name": character.name if character else "Unknown",
            "user_id": participant.user_id,
            "agent_id": participant.agent_id,
            "is_ai": participant.agent_id is not None
        }
        
        # Add additional sender info.
        if participant.user_id:
            user = self.db.query(User).filter(User.id == participant.user_id).first()
            if user:
                result["user_name"] = f"{user.first_name or ''} {user.last_name or ''}".strip() or user.email
        elif participant.agent_id:
            agent = self.db.query(Agent).filter(Agent.id == participant.agent_id).first()
            if agent:
                result["agent_name"] = agent.name
        
        return result
    
    def get_conversation_history(self, conversation_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get conversation history with detailed sender information.
        This can be used to provide context to AI agents.
        """
        messages, _, _ = self.get_conversation_messages(
            conversation_id=conversation_id,
            page=1,
            page_size=limit,
            chronological=True  # Oldest first
        )
        
        history = []
        for message in messages:
            sender_info = self.get_sender_info(message)
            history.append({
                "message_id": message.id,
                "participant_id": sender_info["participant_id"],
                "character_id": sender_info["character_id"],
                "character_name": sender_info["character_name"],
                "user_id": sender_info["user_id"],
                "agent_id": sender_info["agent_id"],
                "is_ai": sender_info["is_ai"],
                "content": message.content,
                "created_at": message.created_at.isoformat()
            })
        return history
    
    def search_messages(
        self, 
        conversation_id: str, 
        query: str, 
        page: int = 1, 
        page_size: int = 20
    ) -> Tuple[List[Message], int, int]:
        """Search for messages in a conversation by content."""
        return self.get_messages(
            filters={
                'conversation_id': conversation_id,
                'content': query
            },
            page=page,
            page_size=page_size,
            sort_by="created_at",
            sort_desc=True
        )
    
    def count_messages(self, conversation_id: str) -> int:
        """Return the number of messages in a conversation."""
        return self.db.query(func.count(Message.id)).filter(
            Message.conversation_id == conversation_id
        ).scalar() or 0
    
    def get_user_message_count(self, user_id: str) -> int:
        """
        Return the total number of messages sent by a user across all conversations.
        """
        return self.db.query(func.count(Message.id)).join(
            ConversationParticipant,
            Message.participant_id == ConversationParticipant.id
        ).filter(
            ConversationParticipant.user_id == user_id
        ).scalar() or 0
