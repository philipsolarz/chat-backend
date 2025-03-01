# app/api/dependencies.py
from typing import Dict, Any, Type, Callable
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.player import User
from app.models.character import Character
from app.models.agent import Agent
from app.models.conversation import Conversation, ConversationParticipant
from app.api.auth import get_current_user
from app.services.character_service import CharacterService
from app.services.agent_service import AgentService
from app.services.conversation_service import ConversationService


def get_service(service_class):
    """Factory function to create service dependencies with DB injection"""
    def _get_service(db: Session = Depends(get_db)):
        return service_class(db)
    return _get_service


def get_character_owner(
    character_id: str,
    current_user: User = Depends(get_current_user),
    character_service: CharacterService = Depends(get_service(CharacterService))
) -> Character:
    """
    Dependency to verify a character belongs to the current user
    Returns the character if it exists and belongs to the user
    """
    character = character_service.get_character(character_id)
    
    if not character:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Character not found"
        )
    
    if character.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this character"
        )
    
    return character


def get_conversation_access(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    conversation_service: ConversationService = Depends(get_service(ConversationService))
) -> Conversation:
    """
    Dependency to verify a user has access to a conversation
    
    User has access if they are a participant in the conversation
    Returns the conversation if access is allowed
    """
    # Get the conversation
    conversation = conversation_service.get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
    # Check if user has access
    if not conversation_service.check_user_access(current_user.id, conversation_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this conversation"
        )
    
    return conversation


def get_participant_owner(
    participant_id: str,
    current_user: User = Depends(get_current_user),
    conversation_service: ConversationService = Depends(get_service(ConversationService))
) -> ConversationParticipant:
    """
    Dependency to verify a participant belongs to the current user
    
    Returns the participant if it exists and belongs to the user
    """
    participant = conversation_service.get_participant(participant_id)
    
    if not participant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Participant not found"
        )
    
    if not participant.user_id or participant.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this participant"
        )
    
    return participant