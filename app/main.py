# app/main.py
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
import logging

from app.api.v1.router import api_router
from app.database import engine, Base, get_db
from app.config import get_settings
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

# @app.websocket("/ws/conversations/{conversation_id}")
# async def websocket_endpoint(
#     websocket: WebSocket,
#     conversation_id: str,
#     participant_id: str,
#     access_token: str,
#     db: Session = Depends(get_db)
# ):
#     """
#     WebSocket endpoint for real-time chat with character voice transformation
    
#     Args:
#         websocket: WebSocket connection
#         conversation_id: ID of the conversation to join
#         participant_id: ID of the participant using the connection
#         access_token: JWT authentication token
#     """
#     await handle_websocket_connection(
#         websocket=websocket,
#         conversation_id=conversation_id,
#         participant_id=participant_id,
#         token=access_token,
#         db=db
#     )

# @app.get("/chat")
# async def get():
#     html_content = """
# <!DOCTYPE html>
# <html>
# <head>
#     <title>WebSocket Chat</title>
#     <style>
#         #chat-log {
#             border: 1px solid #ccc;
#             height: 300px;
#             overflow-y: scroll;
#             padding: 10px;
#             margin-bottom: 10px;
#         }
#         #message-input {
#             width: 80%;
#         }
#     </style>
# </head>
# <body>
#     <h1>WebSocket Chat</h1>
#     <div>
#         <!-- For testing, we hardcode conversation and participant IDs -->
#         <label for="access-token">Access Token:</label>
#         <input type="text" id="access-token" placeholder="Enter access token">
#         <br>
#         <label for="conversation-id">Conversation ID:</label>
#         <input type="text" id="conversation-id" placeholder="Enter conversation id" value="1">
#         <br>
#         <label for="participant-id">Participant ID:</label>
#         <input type="text" id="participant-id" placeholder="Enter participant id" value="test">
#         <br>
#         <button id="connect-btn" onclick="connectWebSocket()">Connect</button>
#     </div>
#     <div id="chat-log"></div>
#     <input type="text" id="message-input" placeholder="Type a message..." autofocus/>
#     <button onclick="sendMessage()">Send</button>
#     <script>
#         let ws;

#         function connectWebSocket() {
#             const token = document.getElementById("access-token").value;
#             const conversationId = document.getElementById("conversation-id").value;
#             const participantId = document.getElementById("participant-id").value;
#             // Build the URL using the conversation ID from the path and query parameters for token and participant_id
#             const wsUrl = "ws://" + location.host + "/ws/conversations/" + encodeURIComponent(conversationId) +
#                           "?participant_id=" + encodeURIComponent(participantId) +
#                           "&access_token=" + encodeURIComponent(token);
#             ws = new WebSocket(wsUrl);
            
#             ws.onmessage = function(event) {
#                 const chatLog = document.getElementById("chat-log");
#                 const messageElem = document.createElement("div");
#                 messageElem.textContent = event.data;
#                 chatLog.appendChild(messageElem);
#             };

#             ws.onclose = function() {
#                 alert("Connection closed");
#             };

#             ws.onerror = function(event) {
#                 console.error("WebSocket error observed:", event);
#             };
#         }

#         function sendMessage() {
#             const input = document.getElementById("message-input");
#             if (ws && input.value) {
#                 ws.send(input.value);
#                 input.value = "";
#             }
#         }
#     </script>
# </body>
# </html>
#     """
#     return HTMLResponse(content=html_content)

# Error handler for global exceptions
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global exception: {str(exc)}")
    return {
        "error": "Internal server error",
        "detail": str(exc) if not isinstance(exc, HTTPException) else exc.detail
    }, status.HTTP_500_INTERNAL_SERVER_ERROR



@app.websocket("/ws/game/{character_id}")
async def game_websocket_endpoint(
    websocket: WebSocket,
    character_id: str,
    zone_id: str,
    access_token: str,
    db: Session = Depends(get_db)
):
    """
    WebSocket endpoint for real-time game connection
    
    Args:
        websocket: WebSocket connection
        character_id: ID of the character connecting to the game
        zone_id: ID of the zone the character is in
        access_token: JWT authentication token
    """
    from app.websockets.connection_manager import handle_game_connection
    
    await handle_game_connection(
        websocket=websocket,
        character_id=character_id,
        zone_id=zone_id,
        token=access_token,
        db=db
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)