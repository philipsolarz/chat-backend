# app/api/v1/messages.py
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Any, Dict, List, Optional
from datetime import datetime

from app.database import get_db
from app.schemas import MessageBase, MessageCreate, MessageDetailResponse, MessageEventCreate, MessageList, MessageResponse
from app.api.auth import get_current_user
from app.api.dependencies import get_service, get_conversation_access
from app.api.premium import check_message_limit
from app.services.message_service import MessageService
from app.services.conversation_service import ConversationService
from app.services.usage_service import UsageService
from app.ai.agent_manager import AgentManager
from app.models.player import Player as User
from app.models.conversation import Conversation

router = APIRouter()


@router.post(
    "/conversations/{conversation_id}",
    response_model=MessageDetailResponse,
    status_code=status.HTTP_201_CREATED
)
async def create_message(
    conversation_id: str,
    message_data: MessageCreate,
    background_tasks: BackgroundTasks,
    user_with_capacity: User = Depends(check_message_limit),  # Check message limits
    conversation_service: ConversationService = Depends(get_service(ConversationService)),
    message_service: MessageService = Depends(get_service(MessageService)),
    usage_service: UsageService = Depends(get_service(UsageService)),
    agent_manager: AgentManager = Depends(get_service(AgentManager))
):
    """
    Send a message in a conversation as a participant
    
    This endpoint checks daily message limits before creating
    Returns the created message with details
    """
    # Verify the participant exists and is controlled by the user
    participant = conversation_service.get_participant(message_data.participant_id)
    
    if not participant or participant.conversation_id != conversation_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Participant not found in this conversation"
        )
    
    if not participant.user_id or participant.user_id != user_with_capacity.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only send messages as your own participant"
        )
    
    # Track message in usage service
    usage_service.track_message_sent(user_with_capacity.id, is_from_ai=False)
    
    # Create the message
    message = message_service.create_message(
        conversation_id=conversation_id,
        participant_id=message_data.participant_id,
        content=message_data.content
    )
    
    if not message:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to create message"
        )
    
    # Process AI agent responses in the background
    async def process_ai_responses():
        responses = await agent_manager.process_new_message(
            conversation_id=conversation_id,
            participant_id=message_data.participant_id
        )
        
        # Track AI responses in usage
        for _ in responses:
            usage_service.track_message_sent(user_with_capacity.id, is_from_ai=True)
    
    background_tasks.add_task(process_ai_responses)
    
    # Get sender info for the response
    sender_info = message_service.get_sender_info(message)
    
    # Build detailed response
    response = {
        **message.__dict__,
        "character_id": sender_info["character_id"],
        "character_name": sender_info["character_name"],
        "user_id": sender_info["user_id"],
        "agent_id": sender_info["agent_id"],
        "is_ai": sender_info["is_ai"]
    }
    
    return response


@router.get(
    "/conversations/{conversation_id}",
    response_model=MessageList
)
async def list_conversation_messages(
    conversation_id: str,
    before: Optional[datetime] = None,
    after: Optional[datetime] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    chronological: bool = Query(True, description="If true, oldest first; if false, newest first"),
    conversation: Conversation = Depends(get_conversation_access),
    message_service: MessageService = Depends(get_service(MessageService))
):
    """
    Get messages from a conversation with pagination and filtering
    
    Returns a paginated list of messages with sender details
    """
    messages, total_count, total_pages = message_service.get_conversation_messages(
        conversation_id=conversation_id,
        page=page,
        page_size=page_size,
        chronological=chronological,
        before_timestamp=before,
        after_timestamp=after
    )
    
    # Add sender information to each message
    result = []
    for message in messages:
        sender_info = message_service.get_sender_info(message)
        result.append({
            **message.__dict__,
            "character_id": sender_info["character_id"],
            "character_name": sender_info["character_name"],
            "user_id": sender_info["user_id"],
            "agent_id": sender_info["agent_id"],
            "is_ai": sender_info["is_ai"]
        })
    
    return {
        "items": result,
        "total": total_count,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages
    }


@router.get(
    "/conversations/{conversation_id}/recent",
    response_model=List[MessageDetailResponse]
)
async def get_recent_messages(
    conversation_id: str,
    limit: int = Query(20, ge=1, le=100),
    conversation: Conversation = Depends(get_conversation_access),
    message_service: MessageService = Depends(get_service(MessageService))
):
    """
    Get the most recent messages from a conversation
    
    Returns messages in reverse chronological order (newest first)
    This is a convenience endpoint optimized for UI display
    """
    messages = message_service.get_recent_messages(
        conversation_id=conversation_id,
        limit=limit
    )
    
    # Add sender information to each message
    result = []
    for message in messages:
        sender_info = message_service.get_sender_info(message)
        result.append({
            **message.__dict__,
            "character_id": sender_info["character_id"],
            "character_name": sender_info["character_name"],
            "user_id": sender_info["user_id"],
            "agent_id": sender_info["agent_id"],
            "is_ai": sender_info["is_ai"]
        })
    
    return result


@router.get(
    "/search/",
    response_model=MessageList
)
async def search_messages(
    conversation_id: str,
    query: str = Query(..., min_length=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    conversation: Conversation = Depends(get_conversation_access),
    message_service: MessageService = Depends(get_service(MessageService))
):
    """
    Search for messages within a conversation by content
    
    Returns a paginated list of matching messages
    """
    messages, total_count, total_pages = message_service.search_messages(
        conversation_id=conversation_id,
        query=query,
        page=page,
        page_size=page_size
    )
    
    # Add sender information to each message
    result = []
    for message in messages:
        sender_info = message_service.get_sender_info(message)
        result.append({
            **message.__dict__,
            "character_id": sender_info["character_id"],
            "character_name": sender_info["character_name"],
            "user_id": sender_info["user_id"],
            "agent_id": sender_info["agent_id"],
            "is_ai": sender_info["is_ai"]
        })
    
    return {
        "items": result,
        "total": total_count,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages
    }


@router.get(
    "/remaining",
    response_model=Dict[str, Any]
)
async def get_remaining_messages(
    current_user: User = Depends(get_current_user),
    usage_service: UsageService = Depends(get_service(UsageService))
):
    """
    Get the number of messages the user can still send today
    
    Returns message limit information
    """
    # Get premium status
    is_premium = usage_service.payment_service.is_premium(current_user.id)
    
    # Get today's usage and remaining messages
    remaining = usage_service.get_remaining_daily_messages(current_user.id)
    
    # Get daily limit
    from app.config import get_settings
    settings = get_settings()
    daily_limit = settings.PREMIUM_MESSAGES_PER_DAY if is_premium else settings.FREE_MESSAGES_PER_DAY
    
    return {
        "is_premium": is_premium,
        "daily_limit": daily_limit,
        "remaining": remaining,
        "has_reached_limit": remaining <= 0
    }