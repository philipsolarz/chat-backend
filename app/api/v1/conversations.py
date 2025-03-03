from fastapi import APIRouter, Depends, HTTPException, status, Query, Path, Body
from sqlalchemy.orm import Session
from sqlalchemy import desc, func, or_
from typing import Any, Dict, List, Optional, Tuple
import math

from app.database import get_db
from app.schemas import (
    ConversationBase,
    ConversationCreate,
    ConversationDetailResponse,
    ConversationResponse,
    ConversationSummary,
    ConversationSummaryResponse,
    ConversationUpdate,
    ConversationList,
    ParticipantAddRequest,
    ParticipantDetailResponse,
    ParticipantResponse,
)
from app.api.auth import get_current_user
from app.api.dependencies import get_service, get_conversation_access
from app.api.premium import check_conversation_limit
from app.services.conversation_service import ConversationService
from app.services.character_service import CharacterService
from app.services.agent_service import AgentService
from app.services.usage_service import UsageService
from app.models.player import Player as User
from app.models.conversation import Conversation

router = APIRouter()


@router.post("/", response_model=ConversationDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    conversation_data: ConversationCreate,
    user_with_capacity: User = Depends(check_conversation_limit),
    conversation_service: ConversationService = Depends(get_service(ConversationService)),
    character_service: CharacterService = Depends(get_service(CharacterService)),
    agent_service: AgentService = Depends(get_service(AgentService)),
    usage_service: UsageService = Depends(get_service(UsageService)),
):
    """
    Create a new conversation with specified participants.
    
    Checks conversation limits and usage metrics.
    """
    # Track conversation creation for usage metrics.
    usage_service.track_conversation_created(user_with_capacity.id)
    
    # Create the conversation.
    conversation = conversation_service.create_conversation(conversation_data.title)
    
    # Flag to verify current user has at least one character.
    user_has_character = False
    
    # Add user-controlled characters.
    for character_id in conversation_data.user_character_ids:
        character = character_service.get_character(character_id)
        if not character:
            conversation_service.delete_conversation(conversation.id)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Character with id {character_id} not found",
            )
        # Require that the character is owned by the current user.
        if character.player_id != user_with_capacity.id:
            conversation_service.delete_conversation(conversation.id)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Character {character_id} is not owned by you",
            )
        else:
            user_has_character = True
        
        result = conversation_service.add_participant(
            conversation_id=conversation.id,
            character_id=character_id,
            user_id=user_with_capacity.id,
        )
        if not result:
            conversation_service.delete_conversation(conversation.id)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to add character {character_id} to conversation",
            )
    
    if not user_has_character:
        conversation_service.delete_conversation(conversation.id)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="At least one of your characters must be in the conversation",
        )
    
    # Add agent-controlled characters if provided.
    if conversation_data.agent_character_ids:
        for character_id in conversation_data.agent_character_ids:
            character = character_service.get_character(character_id)
            if not character:
                continue  # Skip if character not found.
            # For agent-controlled characters, require that the character is controlled by an agent.
            agents, _, _ = agent_service.get_active_agents(page=1, page_size=1)
            if not agents:
                continue  # Skip if no active agents.
            result = conversation_service.add_participant(
                conversation_id=conversation.id,
                character_id=character_id,
                agent_id=agents[0].id,
            )
    
    participants = conversation_service.get_participants(conversation.id)
    
    return {
        **conversation.__dict__,
        "participants": participants,
    }


@router.get("/", response_model=ConversationList)
async def list_conversations(
    title: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = Query("updated_at"),
    sort_desc: bool = Query(True),
    current_user: User = Depends(get_current_user),
    conversation_service: ConversationService = Depends(get_service(ConversationService)),
):
    """
    Get all conversations where the current user is participating.
    
    Returns a paginated list.
    """
    conversations, total_count, total_pages = conversation_service.get_user_conversations(
        user_id=current_user.id,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_desc=sort_desc,
    )
    return {
        "items": conversations,
        "total": total_count,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


@router.get("/recent", response_model=List[ConversationSummaryResponse])
async def get_recent_conversations(
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    conversation_service: ConversationService = Depends(get_service(ConversationService)),
):
    """
    Get recent conversations with latest message info for the current user.
    """
    return conversation_service.get_recent_conversations(current_user.id, limit)


@router.get("/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation(
    conversation: Conversation = Depends(get_conversation_access)
):
    """
    Get details of a specific conversation, including participant details.
    """
    conversation_service = ConversationService(next(get_db()))
    participants = conversation_service.get_participants(conversation.id)
    return {
        **conversation.__dict__,
        "participants": participants,
    }


@router.put("/{conversation_id}", response_model=ConversationResponse)
async def update_conversation(
    conversation_update: ConversationUpdate,
    conversation: Conversation = Depends(get_conversation_access),
    conversation_service: ConversationService = Depends(get_service(ConversationService)),
):
    """
    Update a conversation's details (currently only the title).
    """
    update_data = conversation_update.dict(exclude_unset=True)
    updated_conversation = conversation_service.update_conversation(conversation.id, update_data)
    if not updated_conversation:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update conversation",
        )
    return updated_conversation


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation: Conversation = Depends(get_conversation_access),
    conversation_service: ConversationService = Depends(get_service(ConversationService)),
):
    """
    Delete a conversation.
    """
    success = conversation_service.delete_conversation(conversation.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete conversation",
        )
    return None


@router.post("/{conversation_id}/participants", response_model=ParticipantDetailResponse)
async def add_participant(
    conversation_id: str,
    participant: ParticipantAddRequest,
    current_user: User = Depends(get_current_user),
    conversation_service: ConversationService = Depends(get_service(ConversationService)),
    character_service: CharacterService = Depends(get_service(CharacterService)),
    agent_service: AgentService = Depends(get_service(AgentService)),
):
    """
    Add a participant to a conversation.
    """
    if not conversation_service.check_user_access(current_user.id, conversation_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this conversation",
        )
    
    character = character_service.get_character(participant.character_id)
    if not character:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Character not found",
        )
    
    if participant.user_id:
        if participant.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only add yourself as a user participant",
            )
        if character.player_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only use your own characters",
            )
        new_participant = conversation_service.add_participant(
            conversation_id=conversation_id,
            character_id=participant.character_id,
            user_id=participant.user_id,
        )
    else:  # agent participant
        agent = agent_service.get_agent(participant.agent_id)
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agent not found",
            )
        # For agent participants, require that the character is controlled by the agent.
        if character.agent_id != participant.agent_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This character is not controlled by the provided agent",
            )
        new_participant = conversation_service.add_participant(
            conversation_id=conversation_id,
            character_id=participant.character_id,
            agent_id=participant.agent_id,
        )
    
    if not new_participant:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to add participant",
        )
    
    participant_details = conversation_service.get_participant(new_participant.id)
    response = {
        **new_participant.__dict__,
        "character": participant_details.character,
        "user": participant_details.user if participant.user_id else None,
        "agent": participant_details.agent if participant.agent_id else None,
    }
    return response


@router.delete("/{conversation_id}/participants/{participant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_participant(
    conversation_id: str,
    participant_id: str,
    current_user: User = Depends(get_current_user),
    conversation_service: ConversationService = Depends(get_service(ConversationService)),
):
    """
    Remove a participant from a conversation.
    """
    if not conversation_service.check_user_access(current_user.id, conversation_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this conversation",
        )
    
    participant = conversation_service.get_participant(participant_id)
    if not participant or participant.conversation_id != conversation_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Participant not found in this conversation",
        )
    
    if participant.user_id and participant.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only remove your own participation",
        )
    
    success = conversation_service.remove_participant(participant_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to remove participant",
        )
    return None


@router.get("/search/", response_model=ConversationList)
async def search_conversations(
    query: str = Query(..., min_length=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    conversation_service: ConversationService = Depends(get_service(ConversationService)),
):
    """
    Search for conversations by title or message content.
    """
    filters = {
        "user_id": current_user.id,
        "search": query,
    }
    conversations, total_count, total_pages = conversation_service.get_conversations(
        filters=filters,
        page=page,
        page_size=page_size,
    )
    return {
        "items": conversations,
        "total": total_count,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


@router.get("/{conversation_id}/limits", response_model=Dict[str, Any])
async def get_conversation_limits(
    conversation_id: str,
    conversation: Conversation = Depends(get_conversation_access),
    current_user: User = Depends(get_current_user),
    usage_service: UsageService = Depends(get_service(UsageService)),
):
    """
    Get message limits information for the current conversation.
    """
    can_send = usage_service.can_send_message(current_user.id)
    remaining = usage_service.get_remaining_daily_messages(current_user.id)
    is_premium = usage_service.payment_service.is_premium(current_user.id)
    return {
        "can_send_messages": can_send,
        "messages_remaining_today": remaining,
        "is_premium": is_premium,
    }
