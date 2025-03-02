# app/api/v1/conversations.py
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path, Body
from sqlalchemy.orm import Session
from typing import Any, Dict, List, Optional

from app.database import get_db
from app.schemas import ConversationBase, ConversationCreate, ConversationDetailResponse, ConversationResponse, ConversationSummary, ConversationSummaryResponse, ConversationUpdate, ConversationList, ParticipantAddRequest, ParticipantDetailResponse, ParticipantResponse
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
    user_with_capacity: User = Depends(check_conversation_limit),  # Check conversation limits
    conversation_service: ConversationService = Depends(get_service(ConversationService)),
    character_service: CharacterService = Depends(get_service(CharacterService)),
    agent_service: AgentService = Depends(get_service(AgentService)),
    usage_service: UsageService = Depends(get_service(UsageService))
):
    """
    Create a new conversation with specified participants
    
    This endpoint checks conversation limits before creating
    Returns the created conversation with participant details
    """
    # Track conversation creation for usage metrics
    usage_service.track_conversation_created(user_with_capacity.id)
    
    # Create the conversation
    conversation = conversation_service.create_conversation(conversation_data.title)
    
    # Validate user character ownership
    user_has_character = False
    
    # Add user characters
    for character_id in conversation_data.user_character_ids:
        character = character_service.get_character(character_id)
        if not character:
            # Clean up and return error
            conversation_service.delete_conversation(conversation.id)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Character with id {character_id} not found"
            )
        
        # Check if character belongs to current user
        if character.user_id != user_with_capacity.id:
            # Check if it's public
            if not character.is_public:
                conversation_service.delete_conversation(conversation.id)
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Character {character_id} doesn't belong to you and isn't public"
                )
        else:
            user_has_character = True
        
        # Add character as user participant
        result = conversation_service.add_participant(
            conversation_id=conversation.id,
            character_id=character_id,
            user_id=user_with_capacity.id
        )
        
        if not result:
            conversation_service.delete_conversation(conversation.id)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to add character {character_id} to conversation"
            )
    
    # Ensure the current user has at least one character in the conversation
    if not user_has_character:
        conversation_service.delete_conversation(conversation.id)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="At least one of your characters must be in the conversation"
        )
    
    # Add agent characters if provided
    if conversation_data.agent_character_ids:
        for character_id in conversation_data.agent_character_ids:
            # Get character and verify it's public
            character = character_service.get_character(character_id)
            if not character or not character.is_public:
                continue  # Skip non-public characters
            
            # Get agent (use first active agent)
            agents, _, _ = agent_service.get_active_agents(page=1, page_size=1)
            if not agents:
                continue  # Skip if no active agents
            
            # Add character as agent participant
            result = conversation_service.add_participant(
                conversation_id=conversation.id,
                character_id=character_id,
                agent_id=agents[0].id
            )
    
    # Get all participants
    participants = conversation_service.get_participants(conversation.id)
    
    # Construct response
    return {
        **conversation.__dict__,
        "participants": participants
    }


@router.get("/", response_model=ConversationList)
async def list_conversations(
    title: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = Query("updated_at"),
    sort_desc: bool = Query(True),
    current_user: User = Depends(get_current_user),
    conversation_service: ConversationService = Depends(get_service(ConversationService))
):
    """
    Get all conversations where the current user is participating
    
    Returns a paginated list of conversations
    """
    conversations, total_count, total_pages = conversation_service.get_user_conversations(
        user_id=current_user.id,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_desc=sort_desc
    )
    
    return {
        "items": conversations,
        "total": total_count,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages
    }


@router.get("/recent", response_model=List[ConversationSummaryResponse])
async def get_recent_conversations(
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    conversation_service: ConversationService = Depends(get_service(ConversationService))
):
    """
    Get recent conversations with latest message info for the current user
    
    Returns conversations in order of latest activity
    """
    return conversation_service.get_recent_conversations(current_user.id, limit)


@router.get("/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation(
    conversation: Conversation = Depends(get_conversation_access)
):
    """
    Get details of a specific conversation
    
    Returns the conversation with participant details
    """
    # Get participants
    conversation_service = ConversationService(next(get_db()))
    participants = conversation_service.get_participants(conversation.id)
    
    return {
        **conversation.__dict__,
        "participants": participants
    }


@router.put("/{conversation_id}", response_model=ConversationResponse)
async def update_conversation(
    conversation_update: ConversationUpdate,
    conversation: Conversation = Depends(get_conversation_access),
    conversation_service: ConversationService = Depends(get_service(ConversationService))
):
    """
    Update a conversation's details
    
    Currently only allows updating the title
    Returns the updated conversation
    """
    update_data = conversation_update.dict(exclude_unset=True)
    
    updated_conversation = conversation_service.update_conversation(conversation.id, update_data)
    if not updated_conversation:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update conversation"
        )
    
    return updated_conversation


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation: Conversation = Depends(get_conversation_access),
    conversation_service: ConversationService = Depends(get_service(ConversationService))
):
    """
    Delete a conversation
    
    Returns no content on success
    """
    success = conversation_service.delete_conversation(conversation.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete conversation"
        )
    
    return None


@router.post("/{conversation_id}/participants", response_model=ParticipantDetailResponse)
async def add_participant(
    conversation_id: str,
    participant: ParticipantAddRequest,
    current_user: User = Depends(get_current_user),
    conversation_service: ConversationService = Depends(get_service(ConversationService)),
    character_service: CharacterService = Depends(get_service(CharacterService)),
    agent_service: AgentService = Depends(get_service(AgentService))
):
    """
    Add a participant to a conversation
    
    Returns the created participant
    """
    # Verify user has access to the conversation
    if not conversation_service.check_user_access(current_user.id, conversation_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this conversation"
        )
    
    # Verify the character exists
    character = character_service.get_character(participant.character_id)
    if not character:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Character not found"
        )
    
    # Check participant type and permissions
    if participant.user_id:
        # User participant - must be the current user or character must be public
        if participant.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only add yourself as a user participant"
            )
        
        # If character belongs to another user, it must be public
        if character.user_id != current_user.id and not character.is_public:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only use your own characters or public ones"
            )
        
        # Add user participant
        new_participant = conversation_service.add_participant(
            conversation_id=conversation_id,
            character_id=participant.character_id,
            user_id=participant.user_id
        )
    else:  # agent participant
        # Verify agent exists and is active
        agent = agent_service.get_agent(participant.agent_id)
        if not agent or not agent.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agent not found or not active"
            )
        
        # Character must be public for agent use
        if not character.is_public:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only public characters can be used by agents"
            )
        
        # Add agent participant
        new_participant = conversation_service.add_participant(
            conversation_id=conversation_id,
            character_id=participant.character_id,
            agent_id=participant.agent_id
        )
    
    if not new_participant:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to add participant"
        )
    
    # Get full participant details
    participant_details = conversation_service.get_participant(new_participant.id)
    
    # Transform to expected response format
    response = {
        **new_participant.__dict__,
        "character": participant_details.character,
        "user": participant_details.user if participant.user_id else None,
        "agent": participant_details.agent if participant.agent_id else None
    }
    
    return response


@router.delete("/{conversation_id}/participants/{participant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_participant(
    conversation_id: str,
    participant_id: str,
    current_user: User = Depends(get_current_user),
    conversation_service: ConversationService = Depends(get_service(ConversationService))
):
    """
    Remove a participant from a conversation
    
    Returns no content on success
    """
    # Verify user has access to the conversation
    if not conversation_service.check_user_access(current_user.id, conversation_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this conversation"
        )
    
    # Verify the participant exists and is in this conversation
    participant = conversation_service.get_participant(participant_id)
    if not participant or participant.conversation_id != conversation_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Participant not found in this conversation"
        )
    
    # If it's a user participant, only the user themselves or a conversation admin could remove
    if participant.user_id and participant.user_id != current_user.id:
        # TODO: Add conversation admin check if implementing that feature
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only remove your own participation"
        )
    
    # Remove the participant
    success = conversation_service.remove_participant(participant_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to remove participant"
        )
    
    return None


@router.get("/search/", response_model=ConversationList)
async def search_conversations(
    query: str = Query(..., min_length=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    conversation_service: ConversationService = Depends(get_service(ConversationService))
):
    """
    Search for conversations by title or message content
    
    Returns a paginated list of matching conversations
    """
    # Use the search filter
    filters = {
        'user_id': current_user.id,
        'search': query
    }
    
    conversations, total_count, total_pages = conversation_service.get_conversations(
        filters=filters,
        page=page,
        page_size=page_size
    )
    
    return {
        "items": conversations,
        "total": total_count,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages
    }


@router.get(
    "/{conversation_id}/limits",
    response_model=Dict[str, Any]
)
async def get_conversation_limits(
    conversation_id: str,
    conversation: Conversation = Depends(get_conversation_access),
    current_user: User = Depends(get_current_user),
    usage_service: UsageService = Depends(get_service(UsageService))
):
    """
    Get message limits information for the current conversation
    
    Returns information about remaining daily messages
    """
    # Check if the user can send more messages
    can_send = usage_service.can_send_message(current_user.id)
    
    # Get remaining messages
    remaining = usage_service.get_remaining_daily_messages(current_user.id)
    
    # Get premium status
    is_premium = usage_service.payment_service.is_premium(current_user.id)
    
    return {
        "can_send_messages": can_send,
        "messages_remaining_today": remaining,
        "is_premium": is_premium
    }