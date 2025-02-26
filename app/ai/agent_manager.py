# app/ai/agent_manager.py
import asyncio
import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from langchain.chat_models import ChatOpenAI
from langchain.schema import SystemMessage, HumanMessage, AIMessage
from datetime import datetime

from app.config import get_settings
from app.services.message_service import MessageService
from app.services.conversation_service import ConversationService

logger = logging.getLogger(__name__)
settings = get_settings()


class AgentManager:
    """
    Class for managing AI agents in conversations using Langchain
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.message_service = MessageService(db)
        self.conversation_service = ConversationService(db)
        self.settings = get_settings()
    
    async def generate_response(self, participant_id: str) -> Optional[str]:
        """
        Generate a response from an AI agent in a conversation
        
        Args:
            participant_id: ID of the agent participant
            
        Returns:
            The generated response text or None if generation failed
        """
        try:
            # Get the participant
            participant = self.conversation_service.get_participant(participant_id)
            if not participant or not participant.agent_id:
                logger.error(f"Participant {participant_id} not found or not an agent")
                return None
            
            # Get the agent
            agent = participant.agent
            if not agent or not agent.is_active:
                logger.error(f"Agent {participant.agent_id} not found or not active")
                return None
            
            # Get the character
            character = participant.character
            if not character:
                logger.error(f"Character {participant.character_id} not found")
                return None
            
            # Get conversation history
            conversation_history = self.message_service.get_conversation_history(
                conversation_id=participant.conversation_id,
                limit=50  # Limit to most recent 50 messages for context
            )
            
            # Generate response using Langchain
            response = await self._generate_with_langchain(
                agent=agent,
                character=character,
                conversation_history=conversation_history
            )
            
            if response:
                # Save the response to the database
                message = self.message_service.create_message(
                    conversation_id=participant.conversation_id,
                    participant_id=participant_id,
                    content=response
                )
                
                if message:
                    return response
            
            return None
        
        except Exception as e:
            logger.error(f"Error generating AI response: {str(e)}")
            return None
    
    async def _generate_with_langchain(self, 
                                      agent: Any, 
                                      character: Any, 
                                      conversation_history: List[Dict[str, Any]]) -> Optional[str]:
        """
        Generate a response using Langchain
        
        Args:
            agent: The agent model
            character: The character model
            conversation_history: List of previous messages with sender info
        
        Returns:
            The generated response text
        """
        try:
            # Initialize ChatOpenAI with the specified model
            chat_model = ChatOpenAI(
                model_name=self.settings.AI_MODEL_NAME,
                openai_api_key=self.settings.OPENAI_API_KEY,
                temperature=0.7
            )
            
            # Prepare the system message (agent instructions)
            base_system_prompt = f"""You are {character.name}, a character in a conversation. 
{character.description or ''}

{agent.system_prompt or ''}

Respond in the first person as this character. Stay in character at all times.
Keep your responses conversational and appropriate to the context."""
            
            # Format conversation history as messages
            messages = [SystemMessage(content=base_system_prompt)]
            
            for msg in conversation_history:
                # Get sender character name
                sender_name = msg["character_name"]
                
                if msg["character_id"] == character.id:
                    # This is a previous message from this character
                    messages.append(AIMessage(content=msg["content"]))
                else:
                    # This is a message from another participant
                    messages.append(HumanMessage(content=f"{sender_name}: {msg['content']}"))
            
            # Generate response
            response = chat_model.predict_messages(messages)
            return response.content
        
        except Exception as e:
            logger.error(f"Langchain error: {str(e)}")
            return None
    
    async def process_new_message(self, conversation_id: str, participant_id: str) -> List[Dict[str, Any]]:
        """
        Process a new message and generate responses from all AI agents in the conversation
        
        Args:
            conversation_id: ID of the conversation
            participant_id: ID of the message sender
            
        Returns:
            List of generated responses with details
        """
        # Get all agent participants in the conversation
        agent_participants = self.conversation_service.get_agent_participants(conversation_id)
        
        responses = []
        
        # Generate responses from all agent participants
        for agent_participant in agent_participants:
            participant_id = agent_participant["participant_id"]
            
            # Generate response
            response_text = await self.generate_response(participant_id)
            
            if response_text:
                # Get the latest message from this participant
                participant = agent_participant["participant_id"]
                character = agent_participant["character"]
                agent = agent_participant["agent"]
                
                # Find the message that was just created
                recent_messages = self.message_service.get_recent_messages(conversation_id, limit=5)
                message = next((m for m in recent_messages if m.participant_id == participant_id), None)
                
                if message:
                    responses.append({
                        "message_id": message.id,
                        "participant_id": participant_id,
                        "character_id": character.id,
                        "character_name": character.name,
                        "agent_id": agent.id,
                        "agent_name": agent.name,
                        "content": response_text,
                        "created_at": message.created_at.isoformat() if message else datetime.now().isoformat()
                    })
        
        return responses