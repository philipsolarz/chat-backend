from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime
import enum

class SubscriptionStatus(str, enum.Enum):
    """Status of a subscription"""
    ACTIVE = "active"
    CANCELED = "canceled"
    PAST_DUE = "past_due"
    TRIALING = "trialing"
    UNPAID = "unpaid"
    INCOMPLETE = "incomplete"
    INCOMPLETE_EXPIRED = "incomplete_expired"

class SubscriptionPlanResponse(BaseModel):
    """Response with subscription plan details"""
    id: str
    name: str
    description: Optional[str] = None
    stripe_price_id: str
    price_amount: int
    price_currency: str
    interval: str
    messages_per_day: int
    max_conversations: int
    max_characters: int
    can_make_public_characters: bool

    class Config:
        from_attributes = True

class UserSubscriptionResponse(BaseModel):
    """Response with user subscription details"""
    id: str
    user_id: str
    plan_id: str
    stripe_customer_id: Optional[str] = None
    stripe_subscription_id: Optional[str] = None
    status: SubscriptionStatus
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    canceled_at: Optional[datetime] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    plan: SubscriptionPlanResponse

    class Config:
        from_attributes = True

class CheckoutResponse(BaseModel):
    """Response with checkout URL"""
    checkout_url: str

class PortalResponse(BaseModel):
    """Response with billing portal URL"""
    portal_url: str

class SubscriptionInfoResponse(BaseModel):
    """Response with subscription info"""
    is_premium: bool
    subscription: Optional[UserSubscriptionResponse] = None