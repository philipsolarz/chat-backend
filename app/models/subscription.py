# app/models/subscription.py
from sqlalchemy import Column, String, Boolean, Integer, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
import enum
from datetime import datetime

from app.database import Base
from app.models.mixins import TimestampMixin, generate_uuid


class SubscriptionStatus(str, enum.Enum):
    ACTIVE = "active"
    CANCELED = "canceled"
    PAST_DUE = "past_due"
    TRIALING = "trialing"
    UNPAID = "unpaid"
    INCOMPLETE = "incomplete"
    INCOMPLETE_EXPIRED = "incomplete_expired"


class SubscriptionPlan(Base, TimestampMixin):
    """Model representing available subscription plans"""
    __tablename__ = "subscription_plans"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(100), nullable=False)
    description = Column(String(500), nullable=True)
    stripe_price_id = Column(String(100), nullable=False, unique=True)
    price_amount = Column(Integer, nullable=False)  # In cents
    price_currency = Column(String(3), default="usd", nullable=False)
    interval = Column(String(20), default="month", nullable=False)  # month, year, etc.
    
    # Limits and features
    messages_per_day = Column(Integer, default=1000)
    max_conversations = Column(Integer, default=100)
    max_characters = Column(Integer, default=20)
    can_make_public_characters = Column(Boolean, default=True)
    
    # Relationships
    subscriptions = relationship("UserSubscription", back_populates="plan")
    
    def __repr__(self):
        return f"<SubscriptionPlan {self.name}>"


class UserSubscription(Base, TimestampMixin):
    """Model representing a user's subscription"""
    __tablename__ = "user_subscriptions"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("players.id"), nullable=False, index=True)
    plan_id = Column(String(36), ForeignKey("subscription_plans.id"), nullable=False)
    
    # Stripe information
    stripe_customer_id = Column(String(100), nullable=True)
    stripe_subscription_id = Column(String(100), nullable=True, unique=True)
    
    # Subscription status
    status = Column(Enum(SubscriptionStatus), default=SubscriptionStatus.ACTIVE, nullable=False)
    
    # Dates
    current_period_start = Column(DateTime, nullable=True)
    current_period_end = Column(DateTime, nullable=True)
    canceled_at = Column(DateTime, nullable=True)
    
    # Access management
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Relationships
    player = relationship("Player", back_populates="subscriptions")
    plan = relationship("SubscriptionPlan", back_populates="subscriptions")
    
    def __repr__(self):
        return f"<UserSubscription {self.id} - Player: {self.user_id} - Plan: {self.plan.name if self.plan else None}>"
    
    @property
    def is_valid(self):
        """Check if subscription is currently valid"""
        if not self.is_active:
            return False
        
        if self.status not in [SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING]:
            return False
            
        # Check if subscription is expired
        current_time = datetime.utcnow()
        if self.current_period_end and current_time > self.current_period_end:
            return False
            
        return True