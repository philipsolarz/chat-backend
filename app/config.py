# app/config.py
import os
from pydantic_settings import BaseSettings
from functools import lru_cache
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Settings(BaseSettings):
    # Supabase configuration
    SUPABASE_URL: str
    SUPABASE_KEY: str
    SUPABASE_JWT_SECRET: str
    
    # Database
    DATABASE_URL: str
    
    # API configuration
    API_PREFIX: str = "/api/v1"
    
    # AI configuration
    OPENAI_API_KEY: str = ""
    AI_MODEL_NAME: str = "gpt-4o-mini"
    
    # Stripe configuration
    STRIPE_API_KEY: str
    STRIPE_WEBHOOK_SECRET: str
    STRIPE_PREMIUM_PRICE_ID: str
    
    # Usage limits
    FREE_MESSAGES_PER_DAY: int = 50
    FREE_CONVERSATIONS_LIMIT: int = 5
    FREE_CHARACTERS_LIMIT: int = 3
    
    # Premium features
    PREMIUM_MESSAGES_PER_DAY: int = 1000
    PREMIUM_CONVERSATIONS_LIMIT: int = 100
    PREMIUM_CHARACTERS_LIMIT: int = 20
    
    class Config:
        env_file = ".env"


@lru_cache()
def get_settings():
    return Settings()