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
    
    def create_premium_world_checkout(self, 
                                    user_id: str, 
                                    world_data: Dict[str, Any],
                                    success_url: str, 
                                    cancel_url: str,
                                    price: float = 249.99) -> str:
        """
        Create a Stripe checkout session for premium world purchase
        
        Args:
            user_id: User ID
            world_data: Data about the world to be created after payment
            success_url: URL to redirect after successful payment
            cancel_url: URL to redirect if payment is canceled
            price: Price in USD (defaults to $249.99)
                
        Returns:
            Checkout session URL
        """
        # Get user
        user = self.user_service.get_user(user_id)
        if not user:
            raise ValueError("User not found")
        
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
            
            # Create price object for one-time purchase
            price_obj = stripe.Price.create(
                unit_amount=int(price * 100),  # Convert to cents
                currency="usd",
                product_data={
                    "name": f"Premium World: {world_data.get('world_name', 'Custom World')}",
                    "description": "One-time purchase for a premium world creation"
                }
            )
            
            # Create checkout session
            checkout_session = stripe.checkout.Session.create(
                customer=stripe_customer_id,
                payment_method_types=["card"],
                line_items=[{
                    "price": price_obj.id,
                    "quantity": 1
                }],
                mode="payment",  # one-time payment
                success_url=f"{success_url}?session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=cancel_url,
                metadata={
                    "user_id": user.id,
                    "product_type": "premium_world",
                    # Store world data in metadata (limited to what fits)
                    "world_name": world_data.get("world_name", ""),
                    "world_description": world_data.get("world_description", "")[:100] if world_data.get("world_description") else "",
                    "world_genre": world_data.get("world_genre", "")
                }
            )
            
            return checkout_session.url
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error: {str(e)}")
            raise ValueError(f"Payment processing error: {str(e)}")


    def handle_premium_world_checkout_completed(self, session_id: str) -> Optional[str]:
        """
        Handle completed checkout session for premium world
        
        Args:
            session_id: Stripe checkout session ID
            
        Returns:
            ID of the created world, or None if failed
        """
        try:
            # Get checkout session
            session = stripe.checkout.Session.retrieve(session_id)
            
            # Check if this is a premium world purchase
            if session.metadata.get("product_type") != "premium_world":
                logger.error(f"Not a premium world checkout: {session_id}")
                return None
            
            # Get user ID from metadata
            user_id = session.metadata.get("user_id")
            
            if not user_id:
                logger.error(f"User ID not found in session metadata: {session_id}")
                return None
            
            # Get user
            user = self.user_service.get_user(user_id)
            if not user:
                logger.error(f"User not found: {user_id}")
                return None
            
            # Create the premium world
            from app.services.world_service import WorldService
            world_service = WorldService(self.db)
            
            world = world_service.create_world(
                owner_id=user_id,
                name=session.metadata.get("world_name", "Premium World"),
                description=session.metadata.get("world_description", ""),
                genre=session.metadata.get("world_genre", ""),
                is_premium=True,
                price=249.99
            )
            
            if not world:
                logger.error(f"Failed to create premium world for user: {user_id}")
                return None
            
            return world.id
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Error handling premium world checkout: {str(e)}")
            return None
        
    def create_zone_upgrade_checkout(self, 
                                user_id: str, 
                                world_id: str,
                                success_url: str, 
                                cancel_url: str,
                                price: float = 49.99) -> str:
        """
        Create a Stripe checkout session for zone limit upgrade
        
        Args:
            user_id: User ID
            world_id: ID of the world to upgrade
            success_url: URL to redirect after successful payment
            cancel_url: URL to redirect if payment is canceled
            price: Price in USD (defaults to $49.99)
                
        Returns:
            Checkout session URL
        """
        # Get user
        user = self.user_service.get_user(user_id)
        if not user:
            raise ValueError("User not found")
        
        # Get world
        from app.services.world_service import WorldService
        world_service = WorldService(self.db)
        world = world_service.get_world(world_id)
        
        if not world:
            raise ValueError("World not found")
        
        # Check if user is the world owner
        if world.owner_id != user_id:
            raise ValueError("Only the world owner can purchase zone upgrades")
        
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
            
            # Create price object for one-time purchase
            price_obj = stripe.Price.create(
                unit_amount=int(price * 100),  # Convert to cents
                currency="usd",
                product_data={
                    "name": f"Zone Limit Upgrade: {world.name}",
                    "description": "Increase zone limit by 100 for your world"
                }
            )
            
            # Create checkout session
            checkout_session = stripe.checkout.Session.create(
                customer=stripe_customer_id,
                payment_method_types=["card"],
                line_items=[{
                    "price": price_obj.id,
                    "quantity": 1
                }],
                mode="payment",  # one-time payment
                success_url=f"{success_url}?session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=cancel_url,
                metadata={
                    "user_id": user.id,
                    "product_type": "zone_upgrade",
                    "world_id": world_id
                }
            )
            
            return checkout_session.url
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error: {str(e)}")
            raise ValueError(f"Payment processing error: {str(e)}")


    def handle_zone_upgrade_checkout_completed(self, session_id: str) -> Optional[bool]:
        """
        Handle completed checkout session for zone limit upgrade
        
        Args:
            session_id: Stripe checkout session ID
            
        Returns:
            True if successful, None if failed
        """
        try:
            # Get checkout session
            session = stripe.checkout.Session.retrieve(session_id)
            
            # Check if this is a zone upgrade purchase
            if session.metadata.get("product_type") != "zone_upgrade":
                logger.error(f"Not a zone upgrade checkout: {session_id}")
                return None
            
            # Get world ID from metadata
            world_id = session.metadata.get("world_id")
            user_id = session.metadata.get("user_id")
            
            if not world_id or not user_id:
                logger.error(f"World ID or User ID not found in session metadata: {session_id}")
                return None
            
            # Verify world and ownership
            from app.services.world_service import WorldService
            world_service = WorldService(self.db)
            
            world = world_service.get_world(world_id)
            if not world:
                logger.error(f"World not found: {world_id}")
                return None
                
            if world.owner_id != user_id:
                logger.error(f"User {user_id} is not the owner of world {world_id}")
                return None
            
            # Apply the upgrade
            world.zone_limit_upgrades += 1
            self.db.commit()
            
            logger.info(f"Zone limit upgraded for world {world_id}. New limit: {world.total_zone_limit}")
            return True
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Error handling zone upgrade checkout: {str(e)}")
            return None
        
    def create_agent_limit_upgrade_checkout(self, 
                                        user_id: str, 
                                        zone_id: str,
                                        success_url: str, 
                                        cancel_url: str,
                                        price: float = 9.99) -> str:
        """
        Create a Stripe checkout session for agent limit upgrade
        
        Args:
            user_id: User ID
            zone_id: ID of the zone to upgrade
            success_url: URL to redirect after successful payment
            cancel_url: URL to redirect if payment is canceled
            price: Price in USD (defaults to $9.99)
                
        Returns:
            Checkout session URL
        """
        # Get user
        user = self.user_service.get_user(user_id)
        if not user:
            raise ValueError("User not found")
        
        # Get zone to verify it exists
        from app.services.zone_service import ZoneService
        zone_service = ZoneService(self.db)
        
        zone = zone_service.get_zone(zone_id)
        if not zone:
            raise ValueError("Zone not found")
        
        # Get world to verify ownership
        from app.services.world_service import WorldService
        world_service = WorldService(self.db)
        
        world = world_service.get_world(zone.world_id)
        if not world:
            raise ValueError("World not found")
            
        if world.owner_id != user_id:
            raise ValueError("Only the world owner can purchase agent limit upgrades")
        
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
            
            # Create price object for one-time purchase
            price_obj = stripe.Price.create(
                unit_amount=int(price * 100),  # Convert to cents
                currency="usd",
                product_data={
                    "name": f"Agent Limit Upgrade: {zone.name}",
                    "description": "Increase agent limit by 10 for your zone"
                }
            )
            
            # Create checkout session
            checkout_session = stripe.checkout.Session.create(
                customer=stripe_customer_id,
                payment_method_types=["card"],
                line_items=[{
                    "price": price_obj.id,
                    "quantity": 1
                }],
                mode="payment",  # one-time payment
                success_url=f"{success_url}?session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=cancel_url,
                metadata={
                    "user_id": user.id,
                    "product_type": "agent_limit_upgrade",
                    "zone_id": zone_id
                }
            )
            
            return checkout_session.url
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error: {str(e)}")
            raise ValueError(f"Payment processing error: {str(e)}")

    def handle_agent_limit_upgrade_checkout_completed(self, session_id: str) -> Optional[bool]:
        """
        Handle completed checkout session for agent limit upgrade
        
        Args:
            session_id: Stripe checkout session ID
            
        Returns:
            True if successful, None if failed
        """
        try:
            # Get checkout session
            session = stripe.checkout.Session.retrieve(session_id)
            
            # Check if this is an agent limit upgrade purchase
            if session.metadata.get("product_type") != "agent_limit_upgrade":
                logger.error(f"Not an agent limit upgrade checkout: {session_id}")
                return None
            
            # Get zone ID from metadata
            zone_id = session.metadata.get("zone_id")
            user_id = session.metadata.get("user_id")
            
            if not zone_id or not user_id:
                logger.error(f"Zone ID or User ID not found in session metadata: {session_id}")
                return None
            
            # Verify zone and ownership
            from app.services.zone_service import ZoneService
            zone_service = ZoneService(self.db)
            
            zone = zone_service.get_zone(zone_id)
            if not zone:
                logger.error(f"Zone not found: {zone_id}")
                return None
                
            # Verify world ownership
            from app.services.world_service import WorldService
            world_service = WorldService(self.db)
            
            world = world_service.get_world(zone.world_id)
            if not world or world.owner_id != user_id:
                logger.error(f"User {user_id} is not the owner of this zone's world")
                return None
            
            # Apply the upgrade
            zone.agent_limit_upgrades += 1
            self.db.commit()
            
            logger.info(f"Agent limit upgraded for zone {zone_id}. New limit: {zone.total_agent_limit}")
            return True
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Error handling agent limit upgrade checkout: {str(e)}")
            return None