# app/main.py
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import logging

from app.api.v1.router import api_router
from app.database import engine, Base, get_db
from app.config import get_settings
from app.websockets.connection_manager import handle_websocket_connection
from app.database_seeder import seed_database

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Create tables in the database
Base.metadata.create_all(bind=engine)

# Seed the database with initial data
seed_database()

# Get settings
settings = get_settings()

# Initialize app
app = FastAPI(
    title="Chat Application API",
    description="API for a chat application with AI-controlled characters using Supabase for authentication",
    version="0.1.0"
)

# CORS middleware for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Replace with specific origins in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router, prefix=settings.API_PREFIX)


@app.get("/")
async def root():
    """Health check and welcome message"""
    return {
        "message": "Welcome to the Chat Application API",
        "status": "online",
        "version": "0.1.0"
    }


@app.websocket("/ws/conversations/{conversation_id}")
async def websocket_endpoint(
    websocket: WebSocket, 
    conversation_id: str,
    token: str,
    participant_id: str = None
):
    """
    WebSocket endpoint for real-time chat
    
    Args:
        websocket: WebSocket connection
        conversation_id: ID of the conversation to join
        token: JWT authentication token
        participant_id: Optional ID of the participant the user is using
    """
    await handle_websocket_connection(
        websocket=websocket,
        conversation_id=conversation_id,
        token=token,
        participant_id=participant_id
    )


# Error handler for global exceptions
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global exception: {str(exc)}")
    return {
        "error": "Internal server error",
        "detail": str(exc) if not isinstance(exc, HTTPException) else exc.detail
    }, status.HTTP_500_INTERNAL_SERVER_ERROR


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)