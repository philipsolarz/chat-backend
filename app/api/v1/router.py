# app/api/v1/router.py
from fastapi import APIRouter
from app.api.v1 import users, characters, agents, conversations, messages, auth, payments, usage

# Create the main router
api_router = APIRouter()

# Include all the sub-routers
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(characters.router, prefix="/characters", tags=["characters"])
api_router.include_router(agents.router, prefix="/agents", tags=["agents"])
api_router.include_router(conversations.router, prefix="/conversations", tags=["conversations"])
api_router.include_router(messages.router, prefix="/messages", tags=["messages"])
api_router.include_router(payments.router, prefix="/payments", tags=["payments"])
api_router.include_router(usage.router, prefix="/usage", tags=["usage"])