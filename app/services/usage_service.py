# app/services/usage_service.py
import logging
from datetime import date, datetime, timedelta
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session, aliased
from sqlalchemy import func

from app.config import get_settings
from app.models.player import Player as User
from app.models.usage import UserDailyUsage, UserUsageSummary
from app.models.character import Character
from app.models.conversation import Conversation, ConversationParticipant
from app.models.message import Message
from app.services.payment_service import PaymentService

logger = logging.getLogger(__name__)
settings = get_settings()


class UsageService:
    """Service for tracking and managing user usage."""
    
    def __init__(self, db: Session):
        self.db = db
        self.payment_service = PaymentService(db)
    
    def get_daily_usage(self, user_id: str, for_date: date = None) -> Optional[UserDailyUsage]:
        """
        Get a user's daily usage record.
        """
        if for_date is None:
            for_date = date.today()
        return (
            self.db.query(UserDailyUsage)
            .filter(UserDailyUsage.user_id == user_id, UserDailyUsage.date == for_date)
            .first()
        )
    
    def get_or_create_daily_usage(self, user_id: str, for_date: date = None) -> UserDailyUsage:
        """
        Get or create a user's daily usage record.
        """
        if for_date is None:
            for_date = date.today()
        usage = self.get_daily_usage(user_id, for_date)
        if not usage:
            usage = UserDailyUsage(
                user_id=user_id,
                date=for_date,
                message_count=0,
                ai_response_count=0
            )
            self.db.add(usage)
            self.db.commit()
            self.db.refresh(usage)
        return usage
    
    def get_usage_summary(self, user_id: str) -> Optional[UserUsageSummary]:
        """
        Get a user's usage summary.
        """
        return (
            self.db.query(UserUsageSummary)
            .filter(UserUsageSummary.user_id == user_id)
            .first()
        )
    
    def get_or_create_usage_summary(self, user_id: str) -> UserUsageSummary:
        """
        Get or create a user's usage summary.
        """
        summary = self.get_usage_summary(user_id)
        if not summary:
            summary = UserUsageSummary(
                user_id=user_id,
                total_messages=0,
                total_ai_responses=0,
                total_conversations=0,
                total_characters=0,
                active_conversations=0,
                active_characters=0
            )
            self.db.add(summary)
            
            # Calculate initial values from existing data
            character_count = (
                self.db.query(func.count(Character.id))
                .filter(Character.player_id == user_id)
                .scalar()
                or 0
            )
            conversation_count = (
                self.db.query(func.count(func.distinct(ConversationParticipant.conversation_id)))
                .filter(ConversationParticipant.user_id == user_id)
                .scalar()
                or 0
            )
            message_count = (
                self.db.query(func.count(Message.id))
                .join(ConversationParticipant, Message.participant_id == ConversationParticipant.id)
                .filter(ConversationParticipant.user_id == user_id)
                .scalar()
                or 0
            )
            # Alias for joining conversation participant (used for AI responses)
            UserParticipant = aliased(ConversationParticipant)
            ai_response_count = (
                self.db.query(func.count(Message.id))
                .join(ConversationParticipant, Message.participant_id == ConversationParticipant.id)
                .join(Conversation, Message.conversation_id == Conversation.id)
                .join(
                    UserParticipant,
                    (Conversation.id == UserParticipant.conversation_id) &
                    (UserParticipant.user_id == user_id)
                )
                .filter(ConversationParticipant.agent_id.isnot(None))
                .scalar()
                or 0
            )
            
            summary.total_characters = character_count
            summary.active_characters = character_count
            summary.total_conversations = conversation_count
            summary.active_conversations = conversation_count
            summary.total_messages = message_count
            summary.total_ai_responses = ai_response_count
            
            self.db.commit()
            self.db.refresh(summary)
        return summary
    
    def track_message_sent(self, user_id: str, is_from_ai: bool = False) -> bool:
        """
        Track a message being sent.
        """
        # For non-AI messages, check against daily limits
        if not is_from_ai and not self.can_send_message(user_id):
            return False
        
        daily_usage = self.get_or_create_daily_usage(user_id)
        summary = self.get_or_create_usage_summary(user_id)
        
        if is_from_ai:
            daily_usage.ai_response_count += 1
            summary.total_ai_responses += 1
        else:
            daily_usage.message_count += 1
            summary.total_messages += 1
        
        self.db.commit()
        return True
    
    def track_conversation_created(self, user_id: str) -> bool:
        """
        Track a conversation being created.
        """
        if not self.can_create_conversation(user_id):
            return False
        
        summary = self.get_or_create_usage_summary(user_id)
        summary.total_conversations += 1
        summary.active_conversations += 1
        
        self.db.commit()
        return True
    
    def track_character_created(self, user_id: str) -> bool:
        """
        Track a character being created.
        """
        if not self.can_create_character(user_id):
            return False
        
        summary = self.get_or_create_usage_summary(user_id)
        summary.total_characters += 1
        summary.active_characters += 1
        
        self.db.commit()
        return True
    
    def can_send_message(self, user_id: str) -> bool:
        """
        Check if a user can send a message (based on daily limits).
        """
        is_premium = self.payment_service.is_premium(user_id)
        daily_limit = settings.PREMIUM_MESSAGES_PER_DAY if is_premium else settings.FREE_MESSAGES_PER_DAY
        if daily_limit <= 0:
            return True
        usage = self.get_daily_usage(user_id)
        if not usage:
            return True
        return usage.message_count < daily_limit
    
    def can_create_conversation(self, user_id: str) -> bool:
        """
        Check if a user can create a new conversation.
        """
        is_premium = self.payment_service.is_premium(user_id)
        conversation_limit = (
            settings.PREMIUM_CONVERSATIONS_LIMIT if is_premium else settings.FREE_CONVERSATIONS_LIMIT
        )
        if conversation_limit <= 0:
            return True
        summary = self.get_usage_summary(user_id)
        if not summary:
            return True
        return summary.active_conversations < conversation_limit
    
    def can_create_character(self, user_id: str) -> bool:
        """
        Check if a user can create a new character.
        """
        is_premium = self.payment_service.is_premium(user_id)
        character_limit = (
            settings.PREMIUM_CHARACTERS_LIMIT if is_premium else settings.FREE_CHARACTERS_LIMIT
        )
        if character_limit <= 0:
            return True
        summary = self.get_usage_summary(user_id)
        if not summary:
            return True
        return summary.active_characters < character_limit
    
    def can_make_character_public(self, user_id: str) -> bool:
        """
        Check if a user can make a character public (premium feature).
        """
        return self.payment_service.is_premium(user_id)
    
    def get_remaining_daily_messages(self, user_id: str) -> int:
        """
        Get the number of remaining messages a user can send today.
        """
        is_premium = self.payment_service.is_premium(user_id)
        daily_limit = settings.PREMIUM_MESSAGES_PER_DAY if is_premium else settings.FREE_MESSAGES_PER_DAY
        usage = self.get_daily_usage(user_id)
        if not usage:
            return daily_limit
        return max(0, daily_limit - usage.message_count)
    
    def get_usage_stats(self, user_id: str) -> Dict[str, Any]:
        """
        Get comprehensive usage statistics for a user.
        """
        is_premium = self.payment_service.is_premium(user_id)
        daily_usage = self.get_or_create_daily_usage(user_id)
        summary = self.get_or_create_usage_summary(user_id)
        daily_limit = settings.PREMIUM_MESSAGES_PER_DAY if is_premium else settings.FREE_MESSAGES_PER_DAY
        conversation_limit = settings.PREMIUM_CONVERSATIONS_LIMIT if is_premium else settings.FREE_CONVERSATIONS_LIMIT
        character_limit = settings.PREMIUM_CHARACTERS_LIMIT if is_premium else settings.FREE_CHARACTERS_LIMIT
        
        seven_days_ago = date.today() - timedelta(days=7)
        recent_usage = (
            self.db.query(
                UserDailyUsage.date,
                func.sum(UserDailyUsage.message_count).label("message_count"),
                func.sum(UserDailyUsage.ai_response_count).label("ai_response_count")
            )
            .filter(UserDailyUsage.user_id == user_id, UserDailyUsage.date >= seven_days_ago)
            .group_by(UserDailyUsage.date)
            .order_by(UserDailyUsage.date)
            .all()
        )
        
        recent_usage_data = [
            {
                "date": day.date.isoformat(),
                "message_count": day.message_count,
                "ai_response_count": day.ai_response_count,
            }
            for day in recent_usage
        ]
        
        stats = {
            "is_premium": is_premium,
            "today": {
                "date": daily_usage.date.isoformat(),
                "message_count": daily_usage.message_count,
                "ai_response_count": daily_usage.ai_response_count,
                "message_limit": daily_limit,
                "messages_remaining": max(0, daily_limit - daily_usage.message_count),
            },
            "totals": {
                "total_messages": summary.total_messages,
                "total_ai_responses": summary.total_ai_responses,
                "total_conversations": summary.total_conversations,
                "total_characters": summary.total_characters,
            },
            "current": {
                "active_conversations": summary.active_conversations,
                "active_characters": summary.active_characters,
                "conversation_limit": conversation_limit,
                "character_limit": character_limit,
                "conversations_remaining": max(0, conversation_limit - summary.active_conversations),
                "characters_remaining": max(0, character_limit - summary.active_characters),
            },
            "recent_daily": recent_usage_data,
            "features": {
                "can_make_public_characters": is_premium,
            },
        }
        return stats
