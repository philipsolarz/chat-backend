# app/database_seeder.py
from sqlalchemy.orm import Session
import logging
from typing import List

from app.database import SessionLocal, engine, Base
from app.models.subscription import SubscriptionPlan
from app.models.agent import Agent
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def seed_subscription_plans(db: Session) -> List[SubscriptionPlan]:
    """Seed the database with subscription plans"""
    
    # Check if plans already exist
    existing_plans = db.query(SubscriptionPlan).all()
    if existing_plans:
        logger.info(f"Found {len(existing_plans)} existing subscription plans")
        return existing_plans
    
    # Create subscription plans
    free_plan = SubscriptionPlan(
        name="Free",
        description="Basic access to the chat platform",
        stripe_price_id="price_free",  # Placeholder, not used for payments
        price_amount=0,
        price_currency="usd",
        interval="month",
        messages_per_day=settings.FREE_MESSAGES_PER_DAY,
        max_conversations=settings.FREE_CONVERSATIONS_LIMIT,
        max_characters=settings.FREE_CHARACTERS_LIMIT,
        can_make_public_characters=False
    )
    
    premium_plan = SubscriptionPlan(
        name="Premium",
        description="Enhanced access with more characters and messages",
        stripe_price_id=settings.STRIPE_PREMIUM_PRICE_ID,
        price_amount=999,  # $9.99
        price_currency="usd",
        interval="month",
        messages_per_day=settings.PREMIUM_MESSAGES_PER_DAY,
        max_conversations=settings.PREMIUM_CONVERSATIONS_LIMIT,
        max_characters=settings.PREMIUM_CHARACTERS_LIMIT,
        can_make_public_characters=True
    )
    
    # Add plans to database
    db.add(free_plan)
    db.add(premium_plan)
    db.commit()
    
    logger.info("Created subscription plans: Free and Premium")
    return [free_plan, premium_plan]


def seed_default_agents(db: Session) -> List[Agent]:
    """Seed the database with default AI agents"""
    
    # Check if agents already exist
    existing_agents = db.query(Agent).all()
    if existing_agents:
        logger.info(f"Found {len(existing_agents)} existing agents")
        return existing_agents
    
    # Create default agent
    default_agent = Agent(
        name="Assistant",
        description="A helpful AI assistant that can roleplay as various characters",
        system_prompt=(
            "You are a helpful AI assistant participating in a conversation. "
            "You will be assigned a character to roleplay as, with a specific name and personality. "
            "Stay in character at all times, responding as your assigned character would. "
            "Be attentive and engaging, keeping your responses appropriate for the context of the conversation."
        ),
        is_active=True
    )
    
    # Add agent to database
    db.add(default_agent)
    db.commit()
    
    logger.info("Created default agent: Assistant")
    return [default_agent]


def seed_database():
    """Seed the database with initial data"""
    logger.info("Starting database seeding...")
    
    # Create database session
    db = SessionLocal()
    
    try:
        # Create tables if they don't exist
        Base.metadata.create_all(bind=engine)
        
        # Seed subscription plans
        seed_subscription_plans(db)
        
        # Seed default agents
        seed_default_agents(db)
        
        logger.info("Database seeding completed successfully")
    
    except Exception as e:
        logger.error(f"Error seeding database: {str(e)}")
    
    finally:
        db.close()


if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Run seeder
    seed_database()