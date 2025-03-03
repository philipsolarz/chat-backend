# app/ai/agent_manager.py
import asyncio
import logging
from typing import List, Dict, Any, Optional, Tuple, Union
from sqlalchemy.orm import Session
from dataclasses import dataclass
from datetime import datetime

from pydantic_ai import Agent, RunContext
from pydantic import BaseModel

from app.config import get_settings
from app.services.message_service import MessageService
from app.services.conversation_service import ConversationService
from app.services.character_service import CharacterService

logger = logging.getLogger(__name__)
settings = get_settings()

# Create Pydantic models for structured output
class MessageResponse(BaseModel):
    """Structured output for generated responses"""
    content: str

class TransformedMessage(BaseModel):
    """Structured output for transformed messages"""
    content: str

class GameMasterResponse(BaseModel):
    """Structured output for GameMaster responses"""
    is_question: bool = False

# Define the dependencies type
@dataclass
class AgentDependencies:
    """Dependencies for agent operations"""
    db: Session
    message_service: Optional[MessageService] = None
    conversation_service: Optional[ConversationService] = None
    character_service: Optional[CharacterService] = None


class AgentManager:
    """
    Class for managing AI agents in conversations using PydanticAI
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.message_service = MessageService(db)
        self.conversation_service = ConversationService(db)
        self.character_service = CharacterService(db)
        self.settings = get_settings()
        
        # Initialize agents dictionary to cache agent instances
        self._agents = {}
    

    async def process_game_master_message(self, message: str) -> Dict[str, Any]:
        """
        Process a player message through the GameMaster AI
        
        Args:
            message: The message to process
            character_id: ID of the player character
            zone_id: ID of the current zone
        
        Returns:
            Processed message with interpretation
        """
        try:
            # Create dependencies
            deps = AgentDependencies(
                db=self.db,
                message_service=self.message_service,
                conversation_service=self.conversation_service,
                character_service=self.character_service
            )
            
            # Create a system prompt for our game master
            system_prompt = """
            You are the GameMaster, an AI managing a text-based RPG.  
            Your role is to analyze player messages and determine if they are questions.
            """
            
            # Create agent with structured output
            agent = Agent(
                self.settings.AI_MODEL_NAME, 
                system_prompt=system_prompt,
                result_type=GameMasterResponse,
                # deps_type=AgentDependencies
            )
            
            # # Get character info for context
            # character = self.character_service.get_character(character_id)
            # character_info = f"Character: {character.name}" if character else "Unknown character"
            
            # Get zone info for context
            # from app.services.zone_service import ZoneService
            # zone_service = ZoneService(self.db)
            # zone = zone_service.get_zone(zone_id)
            # zone_info = f"Zone: {zone.name}" if zone else "Unknown zone"
            
            # # Run the agent with the message and context
            # prompt = f"""
            # Process the following player message:
            
            # "{message}"
            
            # Context:
            # {character_info}
            # {zone_info}
            
            # Identify if this is a request, and if so, what type of request.
            # Remember to respond to requests in ALL CAPS.
            # """
            
            result = await agent.run(message, deps=deps)
            print(result.data)
            return result.data
            
        except Exception as e:
            logger.error(f"Error processing game master message: {str(e)}")
            # Return a default response in case of error
            return {
                "original_message": message,
                "is_request": False,
                "request_type": None,
                "response": None
            }










#     def _get_character_agent(self, character_id: str) -> Agent:
#         """Get or create an agent for a specific character"""
#         if character_id in self._agents:
#             return self._agents[character_id]
        
#         # Get character from database
#         character = self.character_service.get_character(character_id)
#         if not character:
#             raise ValueError(f"Character {character_id} not found")
        
#         # Create dependencies
#         deps = AgentDependencies(
#             db=self.db,
#             message_service=self.message_service,
#             conversation_service=self.conversation_service,
#             character_service=self.character_service
#         )
        
#         # Create agent with character-specific system prompt
#         system_prompt = self._generate_character_prompt(character)
#         agent = Agent(
#             self.settings.AI_MODEL_NAME, 
#             system_prompt=system_prompt,
#             result_type=MessageResponse,
#             deps_type=AgentDependencies
#         )
        
#         # Add dynamic system prompt if character has additional description
#         if character.description:
#             @agent.system_prompt
#             def add_character_description(ctx: RunContext[AgentDependencies]) -> str:
#                 return f"Additional character details:\n{character.description}"
        
#         # Cache and return agent
#         self._agents[character_id] = agent
#         return agent
    
#     def _generate_character_prompt(self, character) -> str:
#         """Generate a system prompt for a character"""
#         # Use the character's template if it exists
#         if character.template:
#             return character.template
        
#         # Default template if none exists
#         return f"""
# You are {character.name}. Respond to messages in character, maintaining a consistent personality.

# Guidelines:
# - Always stay in character
# - Be conversational and engaging
# - Maintain the character's unique voice and mannerisms
# - If you don't know something, respond as the character would when uncertain
# """
    
#     async def transform_message(self, message: str, character_id: str) -> str:
#         """
#         Transform a message based on character personality
        
#         Args:
#             message: The original message text
#             character_id: The ID of the character to use for transformation
            
#         Returns:
#             The transformed message text or original if transformation failed
#         """
#         try:
#             # Skip transformation if message is empty
#             if not message or message.strip() == "":
#                 return "..."
            
#             # Get the character
#             character = self.character_service.get_character(character_id)
#             if not character:
#                 logger.error(f"Character {character_id} not found")
#                 return message
            
#             # Create transformation agent with MessageResponse result type
#             transform_agent = Agent(
#                 self.settings.AI_MODEL_NAME,
#                 result_type=TransformedMessage,
#                 system_prompt=f"""
# You are {character.name}, {character.description or "a unique character"}.

# Your task is to rewrite the input message as if {character.name} is saying it, maintaining the essential meaning 
# but adapting the style, vocabulary, and tone to match {character.name}'s personality.

# Return ONLY the transformed message with no additional commentary.
# """
#             )
            
#             # Add the character template if available
#             if character.template:
#                 @transform_agent.system_prompt
#                 def add_template() -> str:
#                     return character.template
            
#             # Run the transformation
#             result = await transform_agent.run(f"Transform this message:\n\n{message}")
            
#             # Get the transformed content
#             transformed_message = result.data.content.strip()
            
#             if not transformed_message:
#                 logger.warning("Transformation returned empty result, falling back to original message")
#                 return message
                
#             logger.info(f"Transformed message: {transformed_message}")
#             return transformed_message
            
#         except Exception as e:
#             logger.error(f"Error transforming message: {str(e)}")
#             return message  # Fall back to original message on error
    
#     async def generate_response(self, participant_id: str) -> Optional[str]:
#         """
#         Generate a response from an AI agent in a conversation
        
#         Args:
#             participant_id: ID of the agent participant
            
#         Returns:
#             The generated response text or None if generation failed
#         """
#         try:
#             # Get the participant
#             participant = self.conversation_service.get_participant(participant_id)
#             if not participant or not participant.agent_id:
#                 logger.error(f"Participant {participant_id} not found or not an agent")
#                 return None
            
#             # Get the agent
#             agent = participant.agent
#             if not agent or not agent.is_active:
#                 logger.error(f"Agent {participant.agent_id} not found or not active")
#                 return None
            
#             # Get the character
#             character = participant.character
#             if not character:
#                 logger.error(f"Character {participant.character_id} not found")
#                 return None
            
#             # Get character agent
#             character_agent = self._get_character_agent(character.id)
            
#             # Create deps
#             deps = AgentDependencies(
#                 db=self.db,
#                 message_service=self.message_service,
#                 conversation_service=self.conversation_service,
#                 character_service=self.character_service
#             )
            
#             # Get conversation history
#             conversation_history = self.message_service.get_conversation_history(
#                 conversation_id=participant.conversation_id,
#                 limit=50  # Limit to most recent 50 messages for context
#             )
            
#             # Format history for pydantic_ai
#             formatted_history = []
#             for msg in conversation_history:
#                 sender_name = msg["character_name"]
#                 content = msg["content"]
                
#                 if msg["character_id"] == character.id:
#                     # This is a previous message from this character (assistant)
#                     formatted_history.append({"role": "assistant", "content": content})
#                 else:
#                     # This is a message from another participant (user)
#                     formatted_history.append({"role": "user", "content": f"{sender_name}: {content}"})
            
#             # Generate response using message history
#             result = await character_agent.run(
#                 "What would you say next in this conversation?",
#                 message_history=formatted_history,
#                 deps=deps
#             )
            
#             # Get response content
#             response = result.data.content
            
#             if response:
#                 # Save the response to the database
#                 message = self.message_service.create_message(
#                     conversation_id=participant.conversation_id,
#                     participant_id=participant_id,
#                     content=response
#                 )
                
#                 if message:
#                     return response
            
#             return None
        
#         except Exception as e:
#             logger.error(f"Error generating AI response: {str(e)}")
#             return None
    
#     async def process_new_message(self, conversation_id: str, participant_id: str) -> List[Dict[str, Any]]:
#         """
#         Process a new message and generate responses from all AI agents in the conversation
        
#         Args:
#             conversation_id: ID of the conversation
#             participant_id: ID of the message sender
            
#         Returns:
#             List of generated responses with details
#         """
#         # Get all agent participants in the conversation
#         agent_participants = self.conversation_service.get_agent_participants(conversation_id)
        
#         responses = []
        
#         # Generate responses from all agent participants
#         for agent_participant in agent_participants:
#             agent_participant_id = agent_participant["participant_id"]
            
#             # Generate response
#             response_text = await self.generate_response(agent_participant_id)
            
#             if response_text:
#                 # Get the latest message from this participant
#                 character = agent_participant["character"]
#                 agent = agent_participant["agent"]
                
#                 # Find the message that was just created
#                 recent_messages = self.message_service.get_recent_messages(conversation_id, limit=5)
#                 message = next((m for m in recent_messages if m.participant_id == agent_participant_id), None)
                
#                 if message:
#                     responses.append({
#                         "message_id": message.id,
#                         "participant_id": agent_participant_id,
#                         "character_id": character.id,
#                         "character_name": character.name,
#                         "agent_id": agent.id,
#                         "agent_name": agent.name,
#                         "content": response_text,
#                         "created_at": message.created_at.isoformat() if message else datetime.now().isoformat()
#                     })
        
#         return responses
    
#     # Add a tool for fetching database info
#     @staticmethod
#     def _add_database_tool(agent: Agent):
#         """Add database query tool to an agent"""
        
#         @agent.tool
#         def query_database(ctx: RunContext[AgentDependencies], query: str) -> str:
#             """Query the database for information using SQL-like syntax"""
#             try:
#                 # This is just a placeholder - in a real implementation, you would
#                 # properly validate and execute the query using ctx.deps.db
#                 return f"Results for query: {query}"
#             except Exception as e:
#                 return f"Error executing query: {str(e)}"