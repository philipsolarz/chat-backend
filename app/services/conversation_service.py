# app/services/conversation_service.py
from sqlalchemy.orm import Session
from sqlalchemy import desc, func, or_, and_, not_
from typing import List, Optional, Dict, Any, Tuple
import math

from app.models.conversation import Conversation, ConversationParticipant
from app.models.character import Character
from app.models.agent import Agent
from app.models.player import User
from app.models.message import Message


class ConversationService:
    """Service for handling conversation operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_conversation(self, title: Optional[str] = None) -> Conversation:
        """Create a new conversation"""
        conversation = Conversation(title=title)
        
        self.db.add(conversation)
        self.db.commit()
        self.db.refresh(conversation)
        
        return conversation
    
    def get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        """Get a conversation by ID"""
        return self.db.query(Conversation).filter(Conversation.id == conversation_id).first()
    
    def get_conversations(self, 
                          filters: Dict[str, Any] = None, 
                          page: int = 1, 
                          page_size: int = 20, 
                          sort_by: str = "updated_at", 
                          sort_desc: bool = True) -> Tuple[List[Conversation], int, int]:
        """
        Get conversations with flexible filtering options
        
        Args:
            filters: Dictionary of filter conditions
            page: Page number (starting from 1)
            page_size: Number of records per page
            sort_by: Field to sort by
            sort_desc: Whether to sort in descending order
            
        Returns:
            Tuple of (conversations, total_count, total_pages)
        """
        query = self.db.query(Conversation)
        
        # Apply filters if provided
        if filters:
            if 'title' in filters:
                query = query.filter(Conversation.title.ilike(f"%{filters['title']}%"))
            
            if 'character_id' in filters:
                # Filter by character participation
                query = query.join(
                    ConversationParticipant,
                    Conversation.id == ConversationParticipant.conversation_id
                ).filter(
                    ConversationParticipant.character_id == filters['character_id']
                )
            
            if 'user_id' in filters:
                # Filter by user participation (directly)
                query = query.join(
                    ConversationParticipant,
                    Conversation.id == ConversationParticipant.conversation_id
                ).filter(
                    ConversationParticipant.user_id == filters['user_id']
                )
            
            if 'agent_id' in filters:
                # Filter by agent participation
                query = query.join(
                    ConversationParticipant,
                    Conversation.id == ConversationParticipant.conversation_id
                ).filter(
                    ConversationParticipant.agent_id == filters['agent_id']
                )
                
            if 'exclude_empty' in filters and filters['exclude_empty']:
                # Filter out conversations with no messages
                query = query.join(
                    Message,
                    Conversation.id == Message.conversation_id,
                    isouter=True
                ).group_by(
                    Conversation.id
                ).having(
                    func.count(Message.id) > 0
                )
                
            if 'search' in filters and filters['search']:
                # Search in conversation titles and messages
                search_term = f"%{filters['search']}%"
                query = query.outerjoin(
                    Message,
                    Conversation.id == Message.conversation_id
                ).filter(
                    or_(
                        Conversation.title.ilike(search_term),
                        Message.content.ilike(search_term)
                    )
                ).distinct()
        
        # Get total count before pagination
        total_count = query.distinct().count()
        total_pages = math.ceil(total_count / page_size) if total_count > 0 else 1
        
        # Apply sorting
        if hasattr(Conversation, sort_by):
            sort_field = getattr(Conversation, sort_by)
            query = query.order_by(sort_field.desc() if sort_desc else sort_field)
        else:
            # Default sorting by updated_at
            query = query.order_by(Conversation.updated_at.desc() if sort_desc else Conversation.updated_at)
        
        # Apply pagination - convert page to offset
        offset = (page - 1) * page_size if page > 0 else 0
        
        # Get paginated results
        conversations = query.distinct().offset(offset).limit(page_size).all()
        
        return conversations, total_count, total_pages
    
    def update_conversation(self, conversation_id: str, update_data: Dict[str, Any]) -> Optional[Conversation]:
        """Update a conversation"""
        conversation = self.get_conversation(conversation_id)
        if not conversation:
            return None
        
        # Update only the fields provided
        for key, value in update_data.items():
            if hasattr(conversation, key):
                setattr(conversation, key, value)
        
        self.db.commit()
        self.db.refresh(conversation)
        
        return conversation
    
    def delete_conversation(self, conversation_id: str) -> bool:
        """Delete a conversation"""
        conversation = self.get_conversation(conversation_id)
        if not conversation:
            return False
        
        self.db.delete(conversation)
        self.db.commit()
        
        return True
    
    def add_participant(self, 
                       conversation_id: str, 
                       character_id: str, 
                       user_id: Optional[str] = None, 
                       agent_id: Optional[str] = None) -> Optional[ConversationParticipant]:
        """
        Add a participant to a conversation
        
        Args:
            conversation_id: ID of the conversation
            character_id: ID of the character to be used
            user_id: ID of the user controlling the character (if user-controlled)
            agent_id: ID of the agent controlling the character (if AI-controlled)
            
        Note: Either user_id or agent_id must be provided, but not both
        """
        # Validate that only one of user_id or agent_id is provided
        if (user_id is not None and agent_id is not None) or (user_id is None and agent_id is None):
            return None
        
        # Check if conversation exists
        conversation = self.get_conversation(conversation_id)
        if not conversation:
            return None
        
        # Check if character exists
        character = self.db.query(Character).filter(Character.id == character_id).first()
        if not character:
            return None
        
        # Check if user or agent exists
        if user_id:
            controller = self.db.query(User).filter(User.id == user_id).first()
            if not controller:
                return None
                
            # Verify user has access to the character
            if character.user_id != user_id and not character.is_public:
                return None
        else:  # agent_id is not None
            controller = self.db.query(Agent).filter(Agent.id == agent_id).first()
            if not controller or not controller.is_active:
                return None
                
            # Verify agent can use this character (must be public)
            if not character.is_public:
                return None
        
        # Check if this exact participation already exists
        existing = self.db.query(ConversationParticipant).filter(
            ConversationParticipant.conversation_id == conversation_id,
            ConversationParticipant.character_id == character_id,
            ConversationParticipant.user_id == user_id if user_id else True,
            ConversationParticipant.agent_id == agent_id if agent_id else True
        ).first()
        
        if existing:
            return existing  # Already participating
        
        # Create new participant
        participant = ConversationParticipant(
            conversation_id=conversation_id,
            character_id=character_id,
            user_id=user_id,
            agent_id=agent_id
        )
        
        self.db.add(participant)
        self.db.commit()
        self.db.refresh(participant)
        
        return participant
    
    def remove_participant(self, participant_id: str) -> bool:
        """
        Remove a participant from a conversation by participant ID
        """
        participant = self.db.query(ConversationParticipant).filter(
            ConversationParticipant.id == participant_id
        ).first()
        
        if not participant:
            return False
        
        self.db.delete(participant)
        self.db.commit()
        
        return True
    
    def get_participant(self, participant_id: str) -> Optional[ConversationParticipant]:
        """Get a conversation participant by ID"""
        return self.db.query(ConversationParticipant).filter(
            ConversationParticipant.id == participant_id
        ).first()
    
    def get_participants(self, conversation_id: str) -> List[Dict[str, Any]]:
        """
        Get all participants in a conversation with detailed information
        
        Returns list of dicts with:
        - participant_id
        - character (obj)
        - user (obj, if user-controlled)
        - agent (obj, if agent-controlled)
        - type ('user' or 'agent')
        """
        participants = self.db.query(ConversationParticipant).filter(
            ConversationParticipant.conversation_id == conversation_id
        ).all()
        
        result = []
        for p in participants:
            participant_info = {
                "id": p.id,
                "conversation_id": p.conversation_id,
                "character_id": p.character_id,
                "created_at": p.created_at,
                "user_id": p.user_id,
                "agent_id": p.agent_id,
                "character": p.character,
                "user": p.user,
                "agent": p.agent,
                "type": "user" if p.user_id else "agent"  # Keep this for additional context
            }
            # participant_info = {
            #     "participant_id": p.id,
            #     "character": p.character,
            #     "user": p.user,
            #     "agent": p.agent,
            #     "type": "user" if p.user_id else "agent"
            # }
            result.append(participant_info)
            
        return result
    
    def get_user_participants(self, conversation_id: str) -> List[Dict[str, Any]]:
        """Get all user-controlled participants in a conversation"""
        participants = self.db.query(ConversationParticipant).filter(
            ConversationParticipant.conversation_id == conversation_id,
            ConversationParticipant.user_id.isnot(None)
        ).all()
        
        result = []
        for p in participants:
            participant_info = {
                "participant_id": p.id,
                "character": p.character,
                "user": p.user,
                "type": "user"
            }
            result.append(participant_info)
            
        return result
    
    def get_agent_participants(self, conversation_id: str) -> List[Dict[str, Any]]:
        """Get all agent-controlled participants in a conversation"""
        participants = self.db.query(ConversationParticipant).filter(
            ConversationParticipant.conversation_id == conversation_id,
            ConversationParticipant.agent_id.isnot(None)
        ).all()
        
        result = []
        for p in participants:
            participant_info = {
                "participant_id": p.id,
                "character": p.character,
                "agent": p.agent,
                "type": "agent"
            }
            result.append(participant_info)
            
        return result
    
    def get_user_conversations(self, 
                              user_id: str, 
                              page: int = 1, 
                              page_size: int = 20, 
                              sort_by: str = "updated_at",
                              sort_desc: bool = True) -> Tuple[List[Conversation], int, int]:
        """Get all conversations where a user is participating"""
        return self.get_conversations(
            filters={'user_id': user_id},
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_desc=sort_desc
        )
    
    def get_recent_conversations(self, user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent conversations for a user with the most recent message
        Returns conversations in order of latest activity
        """
        # Get user's participants
        user_participants = self.db.query(ConversationParticipant).filter(
            ConversationParticipant.user_id == user_id
        ).all()
        
        conversation_ids = [p.conversation_id for p in user_participants]
        
        if not conversation_ids:
            return []
        
        # Get conversations with latest message
        conversations = self.db.query(Conversation).filter(
            Conversation.id.in_(conversation_ids)
        ).all()
        
        result = []
        for conversation in conversations:
            # Get the latest message
            latest_message = self.db.query(Message).filter(
                Message.conversation_id == conversation.id
            ).order_by(desc(Message.created_at)).first()
            
            # Get participants count
            participants_count = self.db.query(ConversationParticipant).filter(
                ConversationParticipant.conversation_id == conversation.id
            ).count()
            
            # Get user participants count
            user_participants_count = self.db.query(ConversationParticipant).filter(
                ConversationParticipant.conversation_id == conversation.id,
                ConversationParticipant.user_id.isnot(None)
            ).count()
            
            # Get agent participants count
            agent_participants_count = self.db.query(ConversationParticipant).filter(
                ConversationParticipant.conversation_id == conversation.id,
                ConversationParticipant.agent_id.isnot(None)
            ).count()
            
            # Get sender info if message exists
            sender_name = None
            if latest_message:
                participant = self.get_participant(latest_message.participant_id)
                if participant:
                    if participant.user_id:
                        sender_name = participant.character.name
                    else:  # agent
                        sender_name = f"{participant.character.name} (AI)"
            
            result.append({
                "id": conversation.id,
                "title": conversation.title,
                "latest_message": latest_message.content if latest_message else None,
                "latest_message_time": latest_message.created_at if latest_message else conversation.created_at,
                "latest_message_sender": sender_name,
                "total_participants": participants_count,
                "user_participants": user_participants_count,
                "agent_participants": agent_participants_count,
                "created_at": conversation.created_at,
                "updated_at": conversation.updated_at
            })
        
        # Sort by latest activity
        result.sort(key=lambda x: x["latest_message_time"], reverse=True)
        return result[:limit]
    
    def search_conversations(self, user_id: str, query: str, limit: int = 10) -> List[Conversation]:
        """Search for conversations by title or message content that the user has access to"""
        # Get user's participants
        user_participants = self.db.query(ConversationParticipant).filter(
            ConversationParticipant.user_id == user_id
        ).all()
        
        conversation_ids = [p.conversation_id for p in user_participants]
        
        if not conversation_ids:
            return []
        
        # Search in conversations
        return self.db.query(Conversation).outerjoin(
            Message,
            Conversation.id == Message.conversation_id
        ).filter(
            Conversation.id.in_(conversation_ids),
            or_(
                Conversation.title.ilike(f"%{query}%"),
                Message.content.ilike(f"%{query}%")
            )
        ).distinct().limit(limit).all()
    
    def check_user_access(self, user_id: str, conversation_id: str) -> bool:
        """Check if a user has access to a conversation"""
        return self.db.query(ConversationParticipant).filter(
            ConversationParticipant.conversation_id == conversation_id,
            ConversationParticipant.user_id == user_id
        ).first() is not None
    
    def get_user_participant(self, user_id: str, conversation_id: str, character_id: str) -> Optional[ConversationParticipant]:
        """Get a user's specific participation in a conversation with a particular character"""
        return self.db.query(ConversationParticipant).filter(
            ConversationParticipant.conversation_id == conversation_id,
            ConversationParticipant.user_id == user_id,
            ConversationParticipant.character_id == character_id
        ).first()