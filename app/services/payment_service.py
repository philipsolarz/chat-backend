# app/services/payment_service.py
import stripe
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.player import Player
from app.models.subscription import SubscriptionPlan, UserSubscription, SubscriptionStatus
from app.models.enums import SubscriptionStatus  # if needed
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

    # --- Subscription and Plan Retrieval Methods ---

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

    # --- Customer and Checkout Helpers ---

    def _get_or_create_customer(self, user: Player) -> str:
        """
        Get or create a Stripe customer for a user.
        """
        stripe_customer_id = None
        existing_subscription = self.get_user_subscription(user.id)
        if existing_subscription and existing_subscription.stripe_customer_id:
            stripe_customer_id = existing_subscription.stripe_customer_id

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
        Verify that a user owns the resource associated with an entity.
        Raises ValueError if not authorized.
        
        Assumes that either entity.world_id or entity.zone_id is set.
        """
        from app.services.world_service import WorldService
        world_service = WorldService(self.db)

        if entity.world_id:
            world = world_service.get_world(entity.world_id)
            if not world or world.owner_id != user_id:
                raise ValueError("Only the world owner can purchase upgrades for this entity.")
        elif entity.zone_id:
            from app.services.zone_service import ZoneService
            zone_service = ZoneService(self.db)
            zone = zone_service.get_zone(entity.zone_id)
            if not zone:
                raise ValueError("Zone not found.")
            world = world_service.get_world(zone.world_id)
            if not world or world.owner_id != user_id:
                raise ValueError("Only the world owner can purchase upgrades for this entity.")
        else:
            raise ValueError("Entity does not belong to any world or zone.")

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
        Base function for creating tier upgrade checkout sessions.
        The metadata key will be set to f"{resource_type}_id" for resource identification.
        """
        user = self.player_service.get_player(user_id)
        if not user:
            raise ValueError("User not found")

        stripe_customer_id = self._get_or_create_customer(user)

        price_obj = stripe.Price.create(
            unit_amount=int(price * 100),  # convert to cents
            currency="usd",
            product_data={
                "name": f"{resource_type.capitalize()} Tier Upgrade: {resource_name}",
                "description": f"Upgrade {resource_type} tier to unlock additional capabilities"
            }
        )

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

    # --- Subscription Checkout Methods ---

    def create_subscription_checkout(
        self, user_id: str, plan_id: str, success_url: str, cancel_url: str
    ) -> str:
        """
        Create a Stripe checkout session for a subscription purchase.
        """
        user = self.player_service.get_player(user_id)
        if not user:
            raise ValueError("User not found")
        plan = self.get_plan_by_id(plan_id)
        if not plan:
            raise ValueError("Subscription plan not found")

        try:
            stripe_customer_id = self._get_or_create_customer(user)

            checkout_session = stripe.checkout.Session.create(
                customer=stripe_customer_id,
                payment_method_types=["card"],
                line_items=[{"price": plan.stripe_price_id, "quantity": 1}],
                mode="subscription",
                success_url=f"{success_url}?session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=cancel_url,
                metadata={"user_id": user.id, "plan_id": plan.id},
            )
            return checkout_session.url

        except stripe.error.StripeError as e:
            logger.error(f"Stripe error: {str(e)}")
            raise ValueError(f"Payment processing error: {str(e)}")

    def handle_subscription_checkout_completed(self, session_id: str) -> Optional[UserSubscription]:
        """
        Handle a completed checkout session to create a new subscription.
        """
        try:
            session = stripe.checkout.Session.retrieve(session_id)
            subscription = stripe.Subscription.retrieve(session.subscription)

            user_id = session.metadata.get("user_id")
            plan_id = session.metadata.get("plan_id")
            user = self.player_service.get_player(user_id)
            plan = self.get_plan_by_id(plan_id)
            if not user or not plan:
                logger.error(f"User or plan not found: user_id={user_id}, plan_id={plan_id}")
                return None

            # Deactivate any existing subscriptions for this user
            existing_subscriptions = self.db.query(UserSubscription).filter(
                UserSubscription.user_id == user_id,
                UserSubscription.is_active == True
            ).all()
            for sub in existing_subscriptions:
                sub.is_active = False

            new_subscription = UserSubscription(
                user_id=user_id,
                plan_id=plan_id,
                stripe_customer_id=session.customer,
                stripe_subscription_id=subscription.id,
                status=SubscriptionStatus(subscription.status),
                current_period_start=datetime.fromtimestamp(subscription.current_period_start),
                current_period_end=datetime.fromtimestamp(subscription.current_period_end),
                is_active=True,
            )
            self.db.add(new_subscription)

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
        Handle subscription update events from Stripe.
        """
        try:
            stripe_subscription = stripe.Subscription.retrieve(subscription_id)
            subscription = self.get_subscription_by_stripe_id(subscription_id)
            if not subscription:
                logger.error(f"Subscription not found: {subscription_id}")
                return None

            subscription.status = SubscriptionStatus(stripe_subscription.status)
            subscription.current_period_start = datetime.fromtimestamp(stripe_subscription.current_period_start)
            subscription.current_period_end = datetime.fromtimestamp(stripe_subscription.current_period_end)
            if stripe_subscription.canceled_at:
                subscription.canceled_at = datetime.fromtimestamp(stripe_subscription.canceled_at)

            subscription.is_active = stripe_subscription.status in ["active", "trialing"]

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
        Handle subscription deletion events from Stripe.
        """
        try:
            subscription = self.get_subscription_by_stripe_id(subscription_id)
            if not subscription:
                logger.error(f"Subscription not found: {subscription_id}")
                return False

            subscription.is_active = False
            subscription.status = SubscriptionStatus.CANCELED
            subscription.canceled_at = datetime.utcnow()

            user = self.player_service.get_player(subscription.user_id)
            if user:
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
        Cancel a user's subscription.
        """
        subscription = self.get_user_subscription(user_id)
        if not subscription or not subscription.stripe_subscription_id:
            logger.error(f"No active subscription found for user: {user_id}")
            return False

        try:
            stripe.Subscription.delete(subscription.stripe_subscription_id)
            subscription.is_active = False
            subscription.status = SubscriptionStatus.CANCELED
            subscription.canceled_at = datetime.utcnow()

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
        Create a Stripe billing portal session for managing subscriptions.
        """
        subscription = self.get_user_subscription(user_id)
        if not subscription or not subscription.stripe_customer_id:
            logger.error(f"No subscription with customer ID found for user: {user_id}")
            return None

        try:
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
        Check if a user has premium status.
        """
        user = self.player_service.get_player(user_id)
        return user is not None and user.is_premium

    # --- Premium World and Upgrade Checkouts ---

    def create_premium_world_checkout(
        self,
        user_id: str,
        world_data: Dict[str, Any],
        success_url: str,
        cancel_url: str,
        price: float = 249.99
    ) -> str:
        """
        Create a Stripe checkout session for a one-time premium world purchase.
        Note: Extra data (such as genre) is passed via metadata and should be handled in world_service.create_world.
        """
        user = self.player_service.get_player(user_id)
        if not user:
            raise ValueError("User not found")

        try:
            stripe_customer_id = self._get_or_create_customer(user)

            price_obj = stripe.Price.create(
                unit_amount=int(price * 100),
                currency="usd",
                product_data={
                    "name": f"Premium World: {world_data.get('world_name', 'Custom World')}",
                    "description": "One-time purchase for premium world creation"
                }
            )

            checkout_session = stripe.checkout.Session.create(
                customer=stripe_customer_id,
                payment_method_types=["card"],
                line_items=[{"price": price_obj.id, "quantity": 1}],
                mode="payment",
                success_url=f"{success_url}?session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=cancel_url,
                metadata={
                    "user_id": user.id,
                    "product_type": "premium_world",
                    "world_name": world_data.get("world_name", ""),
                    "world_description": (world_data.get("world_description", "")[:100]
                                          if world_data.get("world_description") else ""),
                    "world_genre": world_data.get("world_genre", "")
                }
            )
            return checkout_session.url

        except stripe.error.StripeError as e:
            logger.error(f"Stripe error: {str(e)}")
            raise ValueError(f"Payment processing error: {str(e)}")

    def handle_premium_world_checkout_completed(self, session_id: str) -> Optional[str]:
        """
        Handle a completed premium world checkout session.
        Returns the created world's ID (as provided by world_service.create_world) or None.
        """
        try:
            session = stripe.checkout.Session.retrieve(session_id)
            if session.metadata.get("product_type") != "premium_world":
                logger.error(f"Not a premium world checkout: {session_id}")
                return None

            user_id = session.metadata.get("user_id")
            if not user_id:
                logger.error(f"User ID not found in session metadata: {session_id}")
                return None

            user = self.player_service.get_player(user_id)
            if not user:
                logger.error(f"User not found: {user_id}")
                return None

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

    def create_zone_upgrade_checkout(
        self,
        user_id: str,
        world_id: str,
        success_url: str,
        cancel_url: str,
        price: float = 49.99
    ) -> str:
        """
        Create a checkout session for a world zone limit upgrade.
        Assumes that the World model has a field `zone_limit_upgrades`.
        """
        user = self.player_service.get_player(user_id)
        if not user:
            raise ValueError("User not found")

        from app.services.world_service import WorldService
        world_service = WorldService(self.db)
        world = world_service.get_world(world_id)
        if not world:
            raise ValueError("World not found")
        if world.owner_id != user_id:
            raise ValueError("Only the world owner can purchase zone upgrades")

        try:
            stripe_customer_id = self._get_or_create_customer(user)

            price_obj = stripe.Price.create(
                unit_amount=int(price * 100),
                currency="usd",
                product_data={
                    "name": f"Zone Limit Upgrade: {world.name}",
                    "description": "Increase zone limit by 1 for your world"
                }
            )
            checkout_session = stripe.checkout.Session.create(
                customer=stripe_customer_id,
                payment_method_types=["card"],
                line_items=[{"price": price_obj.id, "quantity": 1}],
                mode="payment",
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
        Handle a completed checkout session for a zone limit upgrade.
        Assumes World model has a field `zone_limit_upgrades` and a computed property `total_zone_limit`.
        """
        try:
            session = stripe.checkout.Session.retrieve(session_id)
            if session.metadata.get("product_type") != "zone_upgrade":
                logger.error(f"Not a zone upgrade checkout: {session_id}")
                return None

            world_id = session.metadata.get("world_id")
            user_id = session.metadata.get("user_id")
            if not world_id or not user_id:
                logger.error(f"World ID or User ID missing in session metadata: {session_id}")
                return None

            from app.services.world_service import WorldService
            world_service = WorldService(self.db)
            world = world_service.get_world(world_id)
            if not world:
                logger.error(f"World not found: {world_id}")
                return None
            if world.owner_id != user_id:
                logger.error(f"User {user_id} is not the owner of world {world_id}")
                return None

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

    def create_entity_limit_upgrade_checkout(
        self,
        user_id: str,
        zone_id: str,
        success_url: str,
        cancel_url: str,
        price: float = 9.99
    ) -> str:
        """
        Create a checkout session for a zone's entity limit upgrade.
        Assumes Zone model has fields `entity_limit_upgrades` and a property `total_entity_limit`.
        """
        user = self.player_service.get_player(user_id)
        if not user:
            raise ValueError("User not found")

        from app.services.zone_service import ZoneService
        zone_service = ZoneService(self.db)
        zone = zone_service.get_zone(zone_id)
        if not zone:
            raise ValueError("Zone not found")

        from app.services.world_service import WorldService
        world_service = WorldService(self.db)
        world = world_service.get_world(zone.world_id)
        if not world or world.owner_id != user_id:
            raise ValueError("Only the world owner can purchase entity limit upgrades")

        try:
            stripe_customer_id = self._get_or_create_customer(user)

            price_obj = stripe.Price.create(
                unit_amount=int(price * 100),
                currency="usd",
                product_data={
                    "name": f"Entity Limit Upgrade: {zone.name}",
                    "description": "Increase entity limit by 10 for your zone"
                }
            )
            checkout_session = stripe.checkout.Session.create(
                customer=stripe_customer_id,
                payment_method_types=["card"],
                line_items=[{"price": price_obj.id, "quantity": 1}],
                mode="payment",
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
        Handle a completed checkout session for an entity limit upgrade.
        """
        try:
            session = stripe.checkout.Session.retrieve(session_id)
            if session.metadata.get("product_type") != "entity_limit_upgrade":
                logger.error(f"Not an entity limit upgrade checkout: {session_id}")
                return None

            zone_id = session.metadata.get("zone_id")
            user_id = session.metadata.get("user_id")
            if not zone_id or not user_id:
                logger.error(f"Zone ID or User ID missing in session metadata: {session_id}")
                return None

            from app.services.zone_service import ZoneService
            zone_service = ZoneService(self.db)
            zone = zone_service.get_zone(zone_id)
            if not zone:
                logger.error(f"Zone not found: {zone_id}")
                return None

            from app.services.world_service import WorldService
            world_service = WorldService(self.db)
            world = world_service.get_world(zone.world_id)
            if not world or world.owner_id != user_id:
                logger.error(f"User {user_id} is not the owner of this zone's world")
                return None

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

    # --- Tier Upgrade Checkouts for Entities, Characters, and Objects ---

    def create_entity_tier_upgrade_checkout(
        self, 
        user_id: str,
        entity_id: str,
        success_url: str, 
        cancel_url: str,
        price: float = 4.99
    ) -> str:
        """
        Create a checkout session for an entity tier upgrade.
        This uses the base helper after verifying ownership.
        """
        from app.services.entity_service import EntityService
        entity_service = EntityService(self.db)
        entity = entity_service.get_entity(entity_id)
        if not entity:
            raise ValueError("Entity not found")
        self._verify_entity_ownership(entity, user_id)
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
        Create a checkout session for a character tier upgrade.
        """
        from app.services.character_service import CharacterService
        character_service = CharacterService(self.db)
        character = character_service.get_character(character_id)
        if not character:
            raise ValueError("Character not found")
        if character.player_id != user_id:
            raise ValueError("You can only upgrade your own characters")
        if not character.entity_id:
            raise ValueError("Character cannot be upgraded (no associated entity)")
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
        Create a checkout session for an object tier upgrade.
        """
        from app.services.object_service import ObjectService
        object_service = ObjectService(self.db)
        obj = object_service.get_object(object_id)
        if not obj:
            raise ValueError("Object not found")
        if not obj.entity_id:
            raise ValueError("Object cannot be upgraded (no associated entity)")
        from app.services.entity_service import EntityService
        entity_service = EntityService(self.db)
        entity = entity_service.get_entity(obj.entity_id)
        if not entity:
            raise ValueError("Object's entity not found")
        self._verify_entity_ownership(entity, user_id)
        return self.create_tier_upgrade_checkout_base(
            user_id=user_id,
            resource_id=object_id,
            resource_type="object",
            resource_name=obj.name,
            success_url=success_url,
            cancel_url=cancel_url,
            price=price
        )
