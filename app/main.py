# app/main.py
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
import logging

from app.api.v1.router import api_router
from app.database import engine, Base, get_db
from app.config import get_settings
from app.websockets.connection_manager import handle_game_connection
# from app.websockets.connection_manager import handle_websocket_connection, 
# from app.websockets.connection_manager import handle_websocket_connection
from app.database_seeder import seed_database
from app.services.auth_service import AuthService
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

# Error handler for global exceptions
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global exception: {str(exc)}")
    return {
        "error": "Internal server error",
        "detail": str(exc) if not isinstance(exc, HTTPException) else exc.detail
    }, status.HTTP_500_INTERNAL_SERVER_ERROR



@app.websocket("/ws/game/{world_id}/{character_id}")
async def game_websocket_endpoint(
    websocket: WebSocket,
    world_id: str,
    character_id: str,
    access_token: str,
    db: Session = Depends(get_db)
):
    """
    WebSocket endpoint for real-time game connection
    
    Args:
        websocket: WebSocket connection
        world_id: ID of the world the character is playing in
        character_id: ID of the character connecting to the game
        zone_id: ID of the zone the character is in
        access_token: JWT authentication token
    """
    
    await handle_game_connection(
        websocket=websocket,
        world_id=world_id,
        character_id=character_id,
        access_token=access_token,
        db=db
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)