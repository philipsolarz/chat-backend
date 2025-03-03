from fastapi import APIRouter, Depends, HTTPException, status, Request, Body
from sqlalchemy.orm import Session
import stripe
import logging
from typing import List, Dict, Any, Optional

from app.database import get_db
# from app.api import schemas  # our schemas module from above
from app.api.auth import get_current_user
from app.api.dependencies import get_service
from app.models.player import Player as User
from app.schemas.subscriptions import CheckoutResponse, PortalResponse, SubscriptionInfoResponse, SubscriptionPlanResponse
from app.services.payment_service import PaymentService
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter()

# Configure Stripe API
stripe.api_key = settings.STRIPE_API_KEY

@router.get("/plans", response_model=List[SubscriptionPlanResponse])
async def get_subscription_plans(
    current_user: User = Depends(get_current_user),
    payment_service: PaymentService = Depends(get_service(PaymentService))
):
    """
    Get available subscription plans.
    """
    plans = payment_service.get_subscription_plans()
    
    # Using Pydantic's orm_mode, we can simply return the ORM objects.
    return plans

@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout_session(
    plan_id: str = Body(..., embed=True),
    success_url: str = Body(..., embed=True),
    cancel_url: str = Body(..., embed=True),
    current_user: User = Depends(get_current_user),
    payment_service: PaymentService = Depends(get_service(PaymentService))
):
    """
    Create a checkout session for a subscription purchase.
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

@router.post("/billing-portal", response_model=PortalResponse)
async def create_billing_portal_session(
    return_url: str = Body(..., embed=True),
    current_user: User = Depends(get_current_user),
    payment_service: PaymentService = Depends(get_service(PaymentService))
):
    """
    Create a billing portal session for managing subscriptions.
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
    Webhook endpoint for Stripe events.
    
    Handles events such as checkout.session.completed,
    customer.subscription.updated, and customer.subscription.deleted.
    """
    webhook_secret = settings.STRIPE_WEBHOOK_SECRET
    signature = request.headers.get("stripe-signature")
    if not signature:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing Stripe signature"
        )
    
    payload = await request.body()
    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=signature,
            secret=webhook_secret
        )
    except ValueError as e:
        logger.error(f"Invalid Stripe payload: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid payload"
        )
    except stripe.error.SignatureVerificationError as e:
        logger.error(f"Invalid Stripe signature: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid signature"
        )
    
    payment_service = PaymentService(db)
    
    try:
        event_type = event["type"]
        if event_type == "checkout.session.completed":
            session = event["data"]["object"]
            product_type = session.metadata.get("product_type")
            
            if product_type == "zone_upgrade":
                payment_service.handle_zone_upgrade_checkout_completed(session.id)
            elif product_type == "premium_world":
                payment_service.handle_premium_world_checkout_completed(session.id)
            elif product_type == "entity_limit_upgrade":
                payment_service.handle_entity_limit_upgrade_checkout_completed(session.id)
            else:
                # Default to handling as a subscription checkout session
                payment_service.handle_subscription_checkout_completed(session.id)
        
        elif event_type == "customer.subscription.updated":
            subscription = event["data"]["object"]
            payment_service.handle_subscription_updated(subscription.id)
            
        elif event_type == "customer.subscription.deleted":
            subscription = event["data"]["object"]
            payment_service.handle_subscription_deleted(subscription.id)
        
        return {"status": "success"}
        
    except Exception as e:
        logger.error(f"Error handling Stripe webhook: {str(e)}")
        # Return 200 to prevent retries from Stripe even on errors.
        return {"status": "error", "message": str(e)}

@router.get("/subscription", response_model=SubscriptionInfoResponse)
async def get_subscription_info(
    current_user: User = Depends(get_current_user),
    payment_service: PaymentService = Depends(get_service(PaymentService))
):
    """
    Get current user's subscription information.
    """
    subscription = payment_service.get_user_subscription(current_user.id)
    if not subscription:
        return {"is_premium": False, "subscription": None}
    
    return {
        "is_premium": current_user.is_premium,
        "subscription": subscription
    }

@router.post("/subscription/cancel", status_code=status.HTTP_200_OK)
async def cancel_subscription(
    current_user: User = Depends(get_current_user),
    payment_service: PaymentService = Depends(get_service(PaymentService))
):
    """
    Cancel the current user's subscription.
    """
    success = payment_service.cancel_subscription(current_user.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to cancel subscription"
        )
    return {"status": "success", "message": "Subscription canceled"}
