# app/api/v1/payments.py
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response, Body
from sqlalchemy.orm import Session
import stripe
import json
import logging
from typing import List, Dict, Any, Optional

from app.database import get_db
from app.api import schemas
from app.api.auth import get_current_user
from app.api.dependencies import get_service
from app.models.user import User
from app.services.payment_service import PaymentService
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter()

# Configure Stripe API
stripe.api_key = settings.STRIPE_API_KEY


@router.get("/plans", response_model=List[Dict[str, Any]])
async def get_subscription_plans(
    current_user: User = Depends(get_current_user),
    payment_service: PaymentService = Depends(get_service(PaymentService))
):
    """
    Get available subscription plans
    
    Returns a list of subscription plans
    """
    plans = payment_service.get_subscription_plans()
    
    # Convert to response format
    result = []
    for plan in plans:
        result.append({
            "id": plan.id,
            "name": plan.name,
            "description": plan.description,
            "price_amount": plan.price_amount,
            "price_currency": plan.price_currency,
            "interval": plan.interval,
            "features": {
                "messages_per_day": plan.messages_per_day,
                "max_conversations": plan.max_conversations,
                "max_characters": plan.max_characters,
                "can_make_public_characters": plan.can_make_public_characters
            }
        })
    
    return result


@router.post("/checkout", response_model=Dict[str, str])
async def create_checkout_session(
    plan_id: str = Body(..., embed=True),
    success_url: str = Body(..., embed=True),
    cancel_url: str = Body(..., embed=True),
    current_user: User = Depends(get_current_user),
    payment_service: PaymentService = Depends(get_service(PaymentService))
):
    """
    Create a checkout session for subscription purchase
    
    Returns a URL to redirect the user to for payment
    """
    try:
        checkout_url = payment_service.create_subscription_checkout(
            user_id=current_user.id,
            plan_id=plan_id,
            success_url=success_url,
            cancel_url=cancel_url
        )
        
        return {"checkout_url": checkout_url}
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error creating checkout session: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create checkout session"
        )


@router.post("/billing-portal", response_model=Dict[str, str])
async def create_billing_portal_session(
    return_url: str = Body(..., embed=True),
    current_user: User = Depends(get_current_user),
    payment_service: PaymentService = Depends(get_service(PaymentService))
):
    """
    Create a billing portal session for managing subscription
    
    Returns a URL to redirect the user to for subscription management
    """
    try:
        portal_url = payment_service.create_billing_portal_session(
            user_id=current_user.id,
            return_url=return_url
        )
        
        if not portal_url:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No active subscription found"
            )
        
        return {"portal_url": portal_url}
    
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error creating billing portal session: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create billing portal session"
        )


@router.post("/webhook", status_code=status.HTTP_200_OK)
async def stripe_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Webhook endpoint for Stripe events
    
    Handles events like checkout.session.completed, subscription updates, etc.
    """
    # Get the webhook secret from settings
    webhook_secret = settings.STRIPE_WEBHOOK_SECRET
    
    # Get the signature from headers
    signature = request.headers.get("stripe-signature")
    
    if not signature:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing Stripe signature"
        )
    
    # Get the request body
    payload = await request.body()
    
    try:
        # Verify signature and extract event
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=signature,
            secret=webhook_secret
        )
    except ValueError as e:
        # Invalid payload
        logger.error(f"Invalid Stripe payload: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid payload"
        )
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        logger.error(f"Invalid Stripe signature: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid signature"
        )
    
    # Initialize payment service
    payment_service = PaymentService(db)
    
    # Handle the event based on type
    try:
        event_type = event["type"]
        
        if event_type == "checkout.session.completed":
            # Checkout completed, handle based on product type
            session = event["data"]["object"]
            product_type = session.metadata.get("product_type")
            
            if product_type == "zone_upgrade":
                # Handle zone upgrade purchase
                payment_service.handle_zone_upgrade_checkout_completed(session.id)
            elif product_type == "agent_limit_upgrade":
                # Handle agent limit upgrade purchase
                payment_service.handle_agent_limit_upgrade_checkout_completed(session.id)
            elif product_type == "premium_world":
                # Handle premium world purchase
                payment_service.handle_premium_world_checkout_completed(session.id)
            else:
                # Regular subscription checkout
                payment_service.handle_subscription_checkout_completed(session.id)
        
        elif event_type == "customer.subscription.updated":
            # Subscription updated
            subscription = event["data"]["object"]
            payment_service.handle_subscription_updated(subscription.id)
            
        elif event_type == "customer.subscription.deleted":
            # Subscription deleted
            subscription = event["data"]["object"]
            payment_service.handle_subscription_deleted(subscription.id)
        
        return {"status": "success"}
        
    except Exception as e:
        logger.error(f"Error handling Stripe webhook: {str(e)}")
        # We still return 200 to Stripe to prevent retries
        return {"status": "error", "message": str(e)}


@router.get("/subscription", response_model=Dict[str, Any])
async def get_subscription_info(
    current_user: User = Depends(get_current_user),
    payment_service: PaymentService = Depends(get_service(PaymentService))
):
    """
    Get current user's subscription information
    
    Returns subscription details if any
    """
    subscription = payment_service.get_user_subscription(current_user.id)
    
    if not subscription:
        return {
            "is_premium": False,
            "subscription": None
        }
    
    # Get plan info
    plan = subscription.plan
    
    return {
        "is_premium": current_user.is_premium,
        "subscription": {
            "id": subscription.id,
            "status": subscription.status.value,
            "current_period_start": subscription.current_period_start.isoformat() if subscription.current_period_start else None,
            "current_period_end": subscription.current_period_end.isoformat() if subscription.current_period_end else None,
            "canceled_at": subscription.canceled_at.isoformat() if subscription.canceled_at else None,
            "plan": {
                "id": plan.id,
                "name": plan.name,
                "description": plan.description,
                "price_amount": plan.price_amount,
                "price_currency": plan.price_currency,
                "interval": plan.interval,
                "features": {
                    "messages_per_day": plan.messages_per_day,
                    "max_conversations": plan.max_conversations,
                    "max_characters": plan.max_characters,
                    "can_make_public_characters": plan.can_make_public_characters
                }
            }
        }
    }


@router.post("/subscription/cancel", status_code=status.HTTP_200_OK)
async def cancel_subscription(
    current_user: User = Depends(get_current_user),
    payment_service: PaymentService = Depends(get_service(PaymentService))
):
    """
    Cancel current user's subscription
    
    Returns success or error
    """
    success = payment_service.cancel_subscription(current_user.id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to cancel subscription"
        )
    
    return {"status": "success", "message": "Subscription canceled"}