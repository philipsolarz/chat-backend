# app/services/payment_service.py
import stripe
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple
import logging

from app.config import get_settings
from app.models.user import User
from app.models.subscription import SubscriptionPlan, UserSubscription, SubscriptionStatus
from app.services.user_service import UserService

logger = logging.getLogger(__name__)
settings = get_settings()

# Configure Stripe API
stripe.api_key = settings.STRIPE_API_KEY


class PaymentService:
    """Service for handling Stripe payments and subscriptions"""
    
    def __init__(self, db: Session):
        self.db = db
        self.user_service = UserService(db)
    
    def get_subscription_plans(self) -> List[SubscriptionPlan]:
        """Get all available subscription plans"""
        return self.db.query(SubscriptionPlan).all()
    
    def get_plan_by_id(self, plan_id: str) -> Optional[SubscriptionPlan]:
        """Get a subscription plan by ID"""
        return self.db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id).first()
    
    def get_plan_by_stripe_id(self, stripe_price_id: str) -> Optional[SubscriptionPlan]:
        """Get a subscription plan by Stripe price ID"""
        return self.db.query(SubscriptionPlan).filter(
            SubscriptionPlan.stripe_price_id == stripe_price_id
        ).first()
    
    def get_user_subscription(self, user_id: str) -> Optional[UserSubscription]:
        """Get a user's current subscription"""
        return self.db.query(UserSubscription).filter(
            UserSubscription.user_id == user_id,
            UserSubscription.is_active == True
        ).first()
    
    def get_subscription_by_stripe_id(self, stripe_subscription_id: str) -> Optional[UserSubscription]:
        """Get a subscription by Stripe subscription ID"""
        return self.db.query(UserSubscription).filter(
            UserSubscription.stripe_subscription_id == stripe_subscription_id
        ).first()
    
    def create_subscription_checkout(self, user_id: str, plan_id: str, success_url: str, cancel_url: str) -> str:
        """
        Create a Stripe checkout session for subscription purchase
        
        Args:
            user_id: User ID
            plan_id: Subscription plan ID
            success_url: URL to redirect after successful payment
            cancel_url: URL to redirect if payment is canceled
            
        Returns:
            Checkout session URL
        """
        # Get user and plan
        user = self.user_service.get_user(user_id)
        if not user:
            raise ValueError("User not found")
        
        plan = self.get_plan_by_id(plan_id)
        if not plan:
            raise ValueError("Subscription plan not found")
        
        try:
            # Check if user already has a Stripe customer ID
            stripe_customer_id = None
            existing_subscription = self.get_user_subscription(user_id)
            
            if existing_subscription and existing_subscription.stripe_customer_id:
                stripe_customer_id = existing_subscription.stripe_customer_id
            
            # Create a new Stripe customer if needed
            if not stripe_customer_id:
                customer = stripe.Customer.create(
                    email=user.email,
                    name=user.display_name,
                    metadata={"user_id": user.id}
                )
                stripe_customer_id = customer.id
            
            # Create checkout session
            checkout_session = stripe.checkout.Session.create(
                customer=stripe_customer_id,
                payment_method_types=["card"],
                line_items=[{
                    "price": plan.stripe_price_id,
                    "quantity": 1
                }],
                mode="subscription",
                success_url=f"{success_url}?session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=cancel_url,
                metadata={
                    "user_id": user.id,
                    "plan_id": plan.id
                }
            )
            
            return checkout_session.url
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error: {str(e)}")
            raise ValueError(f"Payment processing error: {str(e)}")
    
    def handle_subscription_checkout_completed(self, session_id: str) -> Optional[UserSubscription]:
        """
        Handle completed checkout session and create subscription
        
        Args:
            session_id: Stripe checkout session ID
            
        Returns:
            Created UserSubscription object or None if failed
        """
        try:
            # Get checkout session
            session = stripe.checkout.Session.retrieve(session_id)
            
            # Get subscription from session
            subscription = stripe.Subscription.retrieve(session.subscription)
            
            # Get user and plan from metadata
            user_id = session.metadata.get("user_id")
            plan_id = session.metadata.get("plan_id")
            
            user = self.user_service.get_user(user_id)
            plan = self.get_plan_by_id(plan_id)
            
            if not user or not plan:
                logger.error(f"User or plan not found: user_id={user_id}, plan_id={plan_id}")
                return None
            
            # Deactivate existing subscriptions
            existing_subscriptions = self.db.query(UserSubscription).filter(
                UserSubscription.user_id == user_id,
                UserSubscription.is_active == True
            ).all()
            
            for sub in existing_subscriptions:
                sub.is_active = False
                
            # Create new subscription
            new_subscription = UserSubscription(
                user_id=user_id,
                plan_id=plan_id,
                stripe_customer_id=session.customer,
                stripe_subscription_id=subscription.id,
                status=SubscriptionStatus(subscription.status),
                current_period_start=datetime.fromtimestamp(subscription.current_period_start),
                current_period_end=datetime.fromtimestamp(subscription.current_period_end),
                is_active=True
            )
            
            self.db.add(new_subscription)
            
            # Update user premium status
            user.is_premium = True
            user.premium_since = datetime.utcnow()
            
            self.db.commit()
            
            return new_subscription
            
        except stripe.error.StripeError as e:
            self.db.rollback()
            logger.error(f"Stripe error: {str(e)}")
            return None
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error handling checkout completion: {str(e)}")
            return None
    
    def handle_subscription_updated(self, subscription_id: str) -> Optional[UserSubscription]:
        """
        Handle subscription update event from Stripe
        
        Args:
            subscription_id: Stripe subscription ID
            
        Returns:
            Updated UserSubscription object or None if failed
        """
        try:
            # Get Stripe subscription
            stripe_subscription = stripe.Subscription.retrieve(subscription_id)
            
            # Get our subscription record
            subscription = self.get_subscription_by_stripe_id(subscription_id)
            if not subscription:
                logger.error(f"Subscription not found: {subscription_id}")
                return None
            
            # Update subscription details
            subscription.status = SubscriptionStatus(stripe_subscription.status)
            subscription.current_period_start = datetime.fromtimestamp(stripe_subscription.current_period_start)
            subscription.current_period_end = datetime.fromtimestamp(stripe_subscription.current_period_end)
            
            if stripe_subscription.canceled_at:
                subscription.canceled_at = datetime.fromtimestamp(stripe_subscription.canceled_at)
            
            # Update active status based on Stripe status
            if stripe_subscription.status in ["active", "trialing"]:
                subscription.is_active = True
            else:
                subscription.is_active = False
            
            # Update user premium status
            user = self.user_service.get_user(subscription.user_id)
            if user:
                user.is_premium = subscription.is_active
            
            self.db.commit()
            return subscription
            
        except stripe.error.StripeError as e:
            self.db.rollback()
            logger.error(f"Stripe error: {str(e)}")
            return None
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error handling subscription update: {str(e)}")
            return None
    
    def handle_subscription_deleted(self, subscription_id: str) -> bool:
        """
        Handle subscription deletion event from Stripe
        
        Args:
            subscription_id: Stripe subscription ID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Get our subscription record
            subscription = self.get_subscription_by_stripe_id(subscription_id)
            if not subscription:
                logger.error(f"Subscription not found: {subscription_id}")
                return False
            
            # Update subscription status
            subscription.is_active = False
            subscription.status = SubscriptionStatus.CANCELED
            subscription.canceled_at = datetime.utcnow()
            
            # Update user premium status
            user = self.user_service.get_user(subscription.user_id)
            if user:
                # Check if user has any other active subscriptions
                has_active = self.db.query(UserSubscription).filter(
                    UserSubscription.user_id == user.id,
                    UserSubscription.is_active == True,
                    UserSubscription.id != subscription.id
                ).first() is not None
                
                if not has_active:
                    user.is_premium = False
            
            self.db.commit()
            return True
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error handling subscription deletion: {str(e)}")
            return False
    
    def cancel_subscription(self, user_id: str) -> bool:
        """
        Cancel a user's subscription
        
        Args:
            user_id: User ID
            
        Returns:
            True if successful, False otherwise
        """
        subscription = self.get_user_subscription(user_id)
        if not subscription or not subscription.stripe_subscription_id:
            logger.error(f"No active subscription found for user: {user_id}")
            return False
        
        try:
            # Cancel the subscription in Stripe
            stripe.Subscription.delete(subscription.stripe_subscription_id)
            
            # Update our records
            subscription.is_active = False
            subscription.status = SubscriptionStatus.CANCELED
            subscription.canceled_at = datetime.utcnow()
            
            # Update user premium status
            user = self.user_service.get_user(user_id)
            if user:
                user.is_premium = False
            
            self.db.commit()
            return True
            
        except stripe.error.StripeError as e:
            self.db.rollback()
            logger.error(f"Stripe error: {str(e)}")
            return False
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error canceling subscription: {str(e)}")
            return False
    
    def create_billing_portal_session(self, user_id: str, return_url: str) -> Optional[str]:
        """
        Create a Stripe billing portal session for managing subscription
        
        Args:
            user_id: User ID
            return_url: URL to return to after session
            
        Returns:
            Billing portal URL or None if failed
        """
        subscription = self.get_user_subscription(user_id)
        if not subscription or not subscription.stripe_customer_id:
            logger.error(f"No subscription with customer ID found for user: {user_id}")
            return None
        
        try:
            # Create billing portal session
            session = stripe.billing_portal.Session.create(
                customer=subscription.stripe_customer_id,
                return_url=return_url
            )
            
            return session.url
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error: {str(e)}")
            return None
    
    def is_premium(self, user_id: str) -> bool:
        """
        Check if a user has premium status
        
        Args:
            user_id: User ID
            
        Returns:
            True if user has premium, False otherwise
        """
        user = self.user_service.get_user(user_id)
        return user is not None and user.is_premium