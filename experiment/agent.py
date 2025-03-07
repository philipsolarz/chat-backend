"""
Simplified agent system for autonomous character conversations.
"""
import logging
import asyncio
from typing import Dict, List, Optional, Callable, Awaitable
from pydantic import BaseModel
from pydantic_ai import Agent as PydanticAgent

from models import Character, Conversation

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("character_chat")

class CharacterAgent:
    """Agent that controls a character in conversations"""
    
    def __init__(self, character: Character, model_name: str = "openai:gpt-4o-mini"):
        self.character = character
        
        # Create the agent with a system prompt based on character description
        system_prompt = f"""
        You are roleplaying as {character.name}.
        
        {character.description}
        
        Always stay in character and respond as {character.name} would.
        Keep responses conversational and concise (1-3 sentences).
        
        Respond with just the dialogue - no quotation marks or narration.
        """
        
        # Create the AI agent
        self.agent = PydanticAgent(
            model_name,
            result_type=str,
            system_prompt=system_prompt
        )
    
    async def generate_response(self, conversation: Conversation, other_character: Character) -> str:
        """Generate a response based on the conversation context"""
        try:
            # Create a prompt with conversation history
            history = conversation.get_conversation_history()
            
            # Find the last message (if any)
            last_message = None
            if conversation.messages:
                last_msg = conversation.messages[-1]
                if last_msg["character_id"] != self.character.id:
                    last_message = last_msg
            
            prompt = f"You are in conversation with {other_character.name}.\n\n"
            
            if history:
                prompt += f"Recent conversation:\n{history}\n\n"
            
            if last_message:
                prompt += f"{other_character.name} just said: \"{last_message['content']}\"\n\n"
            else:
                prompt += f"You're starting a conversation with {other_character.name}.\n\n"
            
            prompt += f"As {self.character.name}, your response:"
            
            # Generate response
            result = await self.agent.run(prompt)
            response = result.data.strip()
            
            # Clean up response if needed
            if response.startswith('"') and response.endswith('"'):
                response = response[1:-1].strip()
                
            return response
            
        except Exception as e:
            logger.error(f"Error generating response: {str(e)}")
            return f"*{self.character.name} seems distracted*"

class ConversationManager:
    """Manages conversations between characters"""
    
    def __init__(self):
        self.conversations: Dict[str, Conversation] = {}
        self.agents: Dict[str, CharacterAgent] = {}
    
    def create_conversation(self, characters: List[Character]) -> Conversation:
        """Create a new conversation between characters"""
        if len(characters) < 2:
            raise ValueError("A conversation requires at least 2 characters")
        
        # Create the conversation
        conversation = Conversation()
        
        # Add characters to the conversation
        for character in characters:
            conversation.characters[character.id] = character
            
            # Create an agent for each character if it doesn't exist
            if character.id not in self.agents:
                self.agents[character.id] = CharacterAgent(character)
        
        # Store the conversation
        self.conversations[conversation.id] = conversation
        
        return conversation
    
    async def generate_next_message(self, conversation_id: str, character_id: str) -> str:
        """Generate the next message from a specific character"""
        conversation = self.conversations.get(conversation_id)
        if not conversation:
            raise ValueError(f"Conversation {conversation_id} not found")
            
        character = conversation.characters.get(character_id)
        if not character:
            raise ValueError(f"Character {character_id} not in conversation")
            
        # Get the other character (assuming 2 characters)
        other_character_id = next(
            (cid for cid in conversation.characters.keys() if cid != character_id),
            None
        )
        
        if not other_character_id:
            raise ValueError("No other character found in conversation")
            
        other_character = conversation.characters[other_character_id]
        
        # Get the agent
        agent = self.agents.get(character_id)
        
        # Generate response
        response = await agent.generate_response(conversation, other_character)
        
        # Add to conversation
        conversation.add_message(character_id, response)
        
        return response
    
    async def run_conversation(
        self, 
        conversation_id: str, 
        turns: int = 10,
        delay: float = 2.0,
        message_callback: Optional[Callable[[str, str], Awaitable[None]]] = None
    ) -> None:
        """Run an autonomous conversation for a specified number of turns"""
        conversation = self.conversations.get(conversation_id)
        if not conversation:
            raise ValueError(f"Conversation {conversation_id} not found")
            
        # Get character IDs (assuming exactly 2 characters)
        if len(conversation.characters) != 2:
            raise ValueError("Only conversations with exactly 2 characters are supported")
            
        character_ids = list(conversation.characters.keys())
        
        # Run the conversation
        current_idx = 0
        for _ in range(turns):
            # Get current character
            current_id = character_ids[current_idx]
            current_character = conversation.characters[current_id]
            
            # Generate message
            message = await self.generate_next_message(conversation_id, current_id)
            
            # Callback (properly awaited)
            if message_callback:
                await message_callback(current_character.name, message)
                
            # Switch speaker
            current_idx = (current_idx + 1) % len(character_ids)
            
            # Delay
            await asyncio.sleep(delay)