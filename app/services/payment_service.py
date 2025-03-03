# app/services/payment_service.py
import stripe
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple
import logging

from app.config import get_settings
from app.models.player import Player
from app.models.subscription import SubscriptionPlan, UserSubscription, SubscriptionStatus
from app.services.player_service import PlayerService

logger = logging.getLogger(__name__)
settings = get_settings()

# Configure Stripe API
stripe.api_key = settings.STRIPE_API_KEY


class PaymentService:
    """Service for handling Stripe payments and subscriptions"""
    
    def __init__(self, db: Session):
        self.db = db
        self.player_service = PlayerService(db)
    
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
        user = self.player_service.get_player(user_id)
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
            
            user = self.player_service.get_player(user_id)
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
            user = self.player_service.get_player(subscription.user_id)
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
            user = self.player_service.get_player(subscription.user_id)
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
            user = self.player_service.get_player(user_id)
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
        user = self.player_service.get_player(user_id)
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
        user = self.player_service.get_player(user_id)
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
            user = self.player_service.get_player(user_id)
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
        user = self.player_service.get_player(user_id)
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
        
    def create_entity_limit_upgrade_checkout(self, 
                                        user_id: str, 
                                        zone_id: str,
                                        success_url: str, 
                                        cancel_url: str,
                                        price: float = 9.99) -> str:
        """
        Create a Stripe checkout session for entity limit upgrade
        
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
        user = self.player_service.get_player(user_id)
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
            raise ValueError("Only the world owner can purchase entity limit upgrades")
        
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
                    "name": f"Entity Limit Upgrade: {zone.name}",
                    "description": "Increase entity limit by 10 for your zone"
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
                    "product_type": "entity_limit_upgrade",
                    "zone_id": zone_id
                }
            )
            
            return checkout_session.url
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error: {str(e)}")
            raise ValueError(f"Payment processing error: {str(e)}")


    def handle_entity_limit_upgrade_checkout_completed(self, session_id: str) -> Optional[bool]:
        """
        Handle completed checkout session for entity limit upgrade
        
        Args:
            session_id: Stripe checkout session ID
            
        Returns:
            True if successful, None if failed
        """
        try:
            # Get checkout session
            session = stripe.checkout.Session.retrieve(session_id)
            
            # Check if this is an entity limit upgrade purchase
            if session.metadata.get("product_type") != "entity_limit_upgrade":
                logger.error(f"Not an entity limit upgrade checkout: {session_id}")
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
            zone.entity_limit_upgrades += 1
            self.db.commit()
            
            logger.info(f"Entity limit upgraded for zone {zone_id}. New limit: {zone.total_entity_limit}")
            return True
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Error handling entity limit upgrade checkout: {str(e)}")
            return None


    def create_world_tier_upgrade_checkout(self, 
                                    user_id: str, 
                                    world_id: str,
                                    success_url: str, 
                                    cancel_url: str,
                                    price: float = 49.99) -> str:
        """
        Create a Stripe checkout session for world tier upgrade
        
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
        user = self.player_service.get_player(user_id)
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
            raise ValueError("Only the world owner can purchase world tier upgrades")
        
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
                    "name": f"World Tier Upgrade: {world.name}",
                    "description": f"Upgrade world tier from {world.tier} to {world.tier + 1}"
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
                    "product_type": "world_tier_upgrade",
                    "world_id": world_id,
                    "current_tier": world.tier
                }
            )
            
            return checkout_session.url
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error: {str(e)}")
            raise ValueError(f"Payment processing error: {str(e)}")


    def handle_world_tier_upgrade_checkout_completed(self, session_id: str) -> Optional[bool]:
        """
        Handle completed checkout session for world tier upgrade
        
        Args:
            session_id: Stripe checkout session ID
            
        Returns:
            True if successful, None if failed
        """
        try:
            # Get checkout session
            session = stripe.checkout.Session.retrieve(session_id)
            
            # Check if this is a world tier upgrade purchase
            if session.metadata.get("product_type") != "world_tier_upgrade":
                logger.error(f"Not a world tier upgrade checkout: {session_id}")
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
            
            # Apply the tier upgrade
            success = world_service.upgrade_world_tier(world_id)
            
            if success:
                logger.info(f"World tier upgraded for world {world_id}. New tier: {world.tier + 1}")
            else:
                logger.error(f"Failed to upgrade world tier for world {world_id}")
                
            return success
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Error handling world tier upgrade checkout: {str(e)}")
            return None
        
    def create_zone_tier_upgrade_checkout(self, 
                                    user_id: str, 
                                    zone_id: str,
                                    success_url: str, 
                                    cancel_url: str,
                                    price: float = 9.99) -> str:
        """
        Create a Stripe checkout session for zone tier upgrade
        
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
        user = self.player_service.get_player(user_id)
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
            raise ValueError("Only the world owner can purchase zone tier upgrades")
        
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
                    "name": f"Zone Tier Upgrade: {zone.name}",
                    "description": f"Upgrade zone tier from {zone.tier} to {zone.tier + 1}"
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
                    "product_type": "zone_tier_upgrade",
                    "zone_id": zone_id,
                    "current_tier": zone.tier
                }
            )
            
            return checkout_session.url
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error: {str(e)}")
            raise ValueError(f"Payment processing error: {str(e)}")


    def handle_zone_tier_upgrade_checkout_completed(self, session_id: str) -> Optional[bool]:
        """
        Handle completed checkout session for zone tier upgrade
        
        Args:
            session_id: Stripe checkout session ID
            
        Returns:
            True if successful, None if failed
        """
        try:
            # Get checkout session
            session = stripe.checkout.Session.retrieve(session_id)
            
            # Check if this is a zone tier upgrade purchase
            if session.metadata.get("product_type") != "zone_tier_upgrade":
                logger.error(f"Not a zone tier upgrade checkout: {session_id}")
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
            
            # Apply the tier upgrade
            success = zone_service.upgrade_zone_tier(zone_id)
            
            if success:
                logger.info(f"Zone tier upgraded for zone {zone_id}. New tier: {zone.tier + 1}")
            else:
                logger.error(f"Failed to upgrade zone tier for zone {zone_id}")
                
            return success
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Error handling zone tier upgrade checkout: {str(e)}")
            return None
            
    def create_entity_tier_upgrade_checkout(self, 
                                        user_id: str, 
                                        entity_id: str,
                                        success_url: str, 
                                        cancel_url: str,
                                        price: float = 4.99) -> str:
        """
        Create a Stripe checkout session for entity tier upgrade
        
        Args:
            user_id: User ID
            entity_id: ID of the entity to upgrade
            success_url: URL to redirect after successful payment
            cancel_url: URL to redirect if payment is canceled
            price: Price in USD (defaults to $4.99)
                
        Returns:
            Checkout session URL
        """
        # Get user
        user = self.player_service.get_player(user_id)
        if not user:
            raise ValueError("User not found")
        
        # Get the entity
        from app.services.entity_service import EntityService
        entity_service = EntityService(self.db)
        
        entity = entity_service.get_entity(entity_id)
        if not entity:
            raise ValueError("Entity not found")
        
        # Verify ownership - this requires checking world ownership
        world_id = entity.world_id
        zone_id = entity.zone_id
        
        from app.services.world_service import WorldService
        world_service = WorldService(self.db)
        
        # If entity has a world ID, check ownership directly
        if world_id:
            world = world_service.get_world(world_id)
            if not world or world.owner_id != user_id:
                raise ValueError("Only the world owner can purchase entity tier upgrades")
        
        # If entity has a zone ID, get the world from the zone and check ownership
        elif zone_id:
            from app.services.zone_service import ZoneService
            zone_service = ZoneService(self.db)
            
            zone = zone_service.get_zone(zone_id)
            if not zone:
                raise ValueError("Zone not found")
                
            world = world_service.get_world(zone.world_id)
            if not world or world.owner_id != user_id:
                raise ValueError("Only the world owner can purchase entity tier upgrades")
        else:
            raise ValueError("Entity does not belong to any world or zone")
        
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
                    "name": f"Entity Tier Upgrade: {entity.name}",
                    "description": f"Upgrade entity tier from {entity.tier} to {entity.tier + 1}"
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
                    "product_type": "entity_tier_upgrade",
                    "entity_id": entity_id,
                    "entity_type": entity.type,
                    "current_tier": entity.tier
                }
            )
            
            return checkout_session.url
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error: {str(e)}")
            raise ValueError(f"Payment processing error: {str(e)}")


    def handle_entity_tier_upgrade_checkout_completed(self, session_id: str) -> Optional[bool]:
        """
        Handle completed checkout session for entity tier upgrade
        
        Args:
            session_id: Stripe checkout session ID
            
        Returns:
            True if successful, None if failed
        """
        try:
            # Get checkout session
            session = stripe.checkout.Session.retrieve(session_id)
            
            # Check if this is an entity tier upgrade purchase
            if session.metadata.get("product_type") != "entity_tier_upgrade":
                logger.error(f"Not an entity tier upgrade checkout: {session_id}")
                return None
            
            # Get entity ID from metadata
            entity_id = session.metadata.get("entity_id")
            user_id = session.metadata.get("user_id")
            entity_type = session.metadata.get("entity_type")
            
            if not entity_id or not user_id:
                logger.error(f"Entity ID or User ID not found in session metadata: {session_id}")
                return None
            
            # Get the entity
            from app.services.entity_service import EntityService
            entity_service = EntityService(self.db)
            
            entity = entity_service.get_entity(entity_id)
            if not entity:
                logger.error(f"Entity not found: {entity_id}")
                return None
                
            # Verify ownership
            from app.services.world_service import WorldService
            world_service = WorldService(self.db)
            
            # Handle verification based on whether entity has world_id or zone_id
            if entity.world_id:
                world = world_service.get_world(entity.world_id)
                if not world or world.owner_id != user_id:
                    logger.error(f"User {user_id} is not the owner of this entity's world")
                    return None
            elif entity.zone_id:
                from app.services.zone_service import ZoneService
                zone_service = ZoneService(self.db)
                
                zone = zone_service.get_zone(entity.zone_id)
                if not zone:
                    logger.error(f"Zone not found for entity: {entity_id}")
                    return None
                    
                world = world_service.get_world(zone.world_id)
                if not world or world.owner_id != user_id:
                    logger.error(f"User {user_id} is not the owner of this entity's world")
                    return None
            else:
                logger.error(f"Entity does not belong to any world or zone: {entity_id}")
                return None
            
            # Apply the tier upgrade based on entity type
            success = False
            if entity_type == "agent":
                from app.services.agent_service import AgentService
                agent_service = AgentService(self.db)
                # Find the agent with this entity_id
                agent = agent_service.db.query(agent_service.db.model_class).filter_by(entity_id=entity_id).first()
                if agent:
                    success = agent_service.upgrade_agent_tier(agent.id)
            elif entity_type == "object":
                from app.services.object_service import ObjectService
                object_service = ObjectService(self.db)
                # Find the object with this entity_id
                obj = object_service.db.query(object_service.db.model_class).filter_by(entity_id=entity_id).first()
                if obj:
                    success = object_service.upgrade_object_tier(obj.id)
            elif entity_type == "character":
                # Character tier upgrades might be handled differently
                # For now, we'll just upgrade the base entity
                success = entity_service.upgrade_entity_tier(entity_id)
            else:
                # Fallback to upgrading just the entity
                success = entity_service.upgrade_entity_tier(entity_id)
            
            if success:
                logger.info(f"Entity tier upgraded for entity {entity_id}. New tier: {entity.tier + 1}")
            else:
                logger.error(f"Failed to upgrade entity tier for entity {entity_id}")
                
            return success
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Error handling entity tier upgrade checkout: {str(e)}")
            return None
        
    def _get_or_create_customer(self, user) -> str:
        """
        Get or create a Stripe customer for a user
        
        Args:
            user: User object
            
        Returns:
            Stripe customer ID
        """
        # Check if user already has a Stripe customer ID
        stripe_customer_id = None
        existing_subscription = self.get_user_subscription(user.id)
        
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
            
        return stripe_customer_id

    def _verify_entity_ownership(self, entity, user_id: str) -> None:
        """
        Verify that a user has ownership rights to an entity
        Raises ValueError if not authorized
        
        Args:
            entity: Entity object
            user_id: User ID
        """
        # Verify ownership - this requires checking world ownership
        world_id = entity.world_id
        zone_id = entity.zone_id
        
        from app.services.world_service import WorldService
        world_service = WorldService(self.db)
        
        # If entity has a world ID, check ownership directly
        if world_id:
            world = world_service.get_world(world_id)
            if not world or world.owner_id != user_id:
                raise ValueError("Only the world owner can purchase entity tier upgrades")
        
        # If entity has a zone ID, get the world from the zone and check ownership
        elif zone_id:
            from app.services.zone_service import ZoneService
            zone_service = ZoneService(self.db)
            
            zone = zone_service.get_zone(zone_id)
            if not zone:
                raise ValueError("Zone not found")
                
            world = world_service.get_world(zone.world_id)
            if not world or world.owner_id != user_id:
                raise ValueError("Only the world owner can purchase entity tier upgrades")
        else:
            raise ValueError("Entity does not belong to any world or zone")

    def create_tier_upgrade_checkout_base(
        self,
        user_id: str,
        resource_id: str,
        resource_type: str,
        resource_name: str,
        success_url: str,
        cancel_url: str,
        price: float
    ) -> str:
        """
        Base function for creating tier upgrade checkout sessions
        
        Args:
            user_id: User ID
            resource_id: ID of the resource being upgraded
            resource_type: Type of resource ("entity", "character", "object", etc.)
            resource_name: Name of the resource for display
            success_url: URL to redirect after successful payment
            cancel_url: URL to redirect if payment is canceled
            price: Price in USD
            
        Returns:
            Checkout session URL
        """
        # Get user
        user = self.player_service.get_player(user_id)
        if not user:
            raise ValueError("User not found")
        
        # Stripe customer handling
        stripe_customer_id = self._get_or_create_customer(user)
        
        # Create price object
        price_obj = stripe.Price.create(
            unit_amount=int(price * 100),  # Convert to cents
            currency="usd",
            product_data={
                "name": f"{resource_type.capitalize()} Tier Upgrade: {resource_name}",
                "description": f"Upgrade {resource_type} tier to unlock more capabilities"
            }
        )
        
        # Create checkout session
        checkout_session = stripe.checkout.Session.create(
            customer=stripe_customer_id,
            payment_method_types=["card"],
            line_items=[{"price": price_obj.id, "quantity": 1}],
            mode="payment",
            success_url=f"{success_url}?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=cancel_url,
            metadata={
                "user_id": user_id,
                "product_type": f"{resource_type}_tier_upgrade",
                f"{resource_type}_id": resource_id
            }
        )
        
        return checkout_session.url

    def create_entity_tier_upgrade_checkout(
        self, 
        user_id: str,
        entity_id: str,
        success_url: str, 
        cancel_url: str,
        price: float = 4.99
    ) -> str:
        """
        Create a Stripe checkout session for entity tier upgrade
        
        Args:
            user_id: User ID
            entity_id: ID of the entity to upgrade
            success_url: URL to redirect after successful payment
            cancel_url: URL to redirect if payment is canceled
            price: Price in USD
            
        Returns:
            Checkout session URL
        """
        # Verify entity exists and user has permission
        from app.services.entity_service import EntityService
        entity_service = EntityService(self.db)
        
        entity = entity_service.get_entity(entity_id)
        if not entity:
            raise ValueError("Entity not found")
        
        # Verify ownership
        self._verify_entity_ownership(entity, user_id)
        
        # Create checkout using base function
        return self.create_tier_upgrade_checkout_base(
            user_id=user_id,
            resource_id=entity_id,
            resource_type="entity",
            resource_name=entity.name,
            success_url=success_url,
            cancel_url=cancel_url,
            price=price
        )

    def create_character_tier_upgrade_checkout(
        self, 
        user_id: str,
        character_id: str,
        success_url: str, 
        cancel_url: str,
        price: float = 4.99
    ) -> str:
        """
        Create a checkout session for character tier upgrade
        
        Args:
            user_id: User ID
            character_id: ID of the character to upgrade
            success_url: URL to redirect after successful payment
            cancel_url: URL to redirect if payment is canceled
            price: Price in USD
            
        Returns:
            Checkout session URL
        """
        # Verify character exists and belongs to user
        from app.services.character_service import CharacterService
        character_service = CharacterService(self.db)
        
        character = character_service.get_character(character_id)
        if not character:
            raise ValueError("Character not found")
        
        if character.player_id != user_id:
            raise ValueError("You can only upgrade your own characters")
        
        if not character.entity_id:
            raise ValueError("Character cannot be upgraded (no associated entity)")
        
        # Create checkout using base function
        return self.create_tier_upgrade_checkout_base(
            user_id=user_id,
            resource_id=character_id,
            resource_type="character",
            resource_name=character.name,
            success_url=success_url,
            cancel_url=cancel_url,
            price=price
        )

    def create_object_tier_upgrade_checkout(
        self, 
        user_id: str,
        object_id: str,
        success_url: str, 
        cancel_url: str,
        price: float = 4.99
    ) -> str:
        """
        Create a checkout session for object tier upgrade
        
        Args:
            user_id: User ID
            object_id: ID of the object to upgrade
            success_url: URL to redirect after successful payment
            cancel_url: URL to redirect if payment is canceled
            price: Price in USD
            
        Returns:
            Checkout session URL
        """
        # Verify object exists
        from app.services.object_service import ObjectService
        object_service = ObjectService(self.db)
        
        obj = object_service.get_object(object_id)
        if not obj:
            raise ValueError("Object not found")
        
        # Verify ownership by checking entity
        if not obj.entity_id:
            raise ValueError("Object cannot be upgraded (no associated entity)")
        
        # Get the entity to verify ownership
        from app.services.entity_service import EntityService
        entity_service = EntityService(self.db)
        
        entity = entity_service.get_entity(obj.entity_id)
        if not entity:
            raise ValueError("Object's entity not found")
        
        # Verify ownership
        self._verify_entity_ownership(entity, user_id)
        
        # Create checkout using base function
        return self.create_tier_upgrade_checkout_base(
            user_id=user_id,
            resource_id=object_id,
            resource_type="object",
            resource_name=obj.name,
            success_url=success_url,
            cancel_url=cancel_url,
            price=price
        )