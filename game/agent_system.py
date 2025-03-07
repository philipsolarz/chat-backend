"""
Revised agent system for the Agentique Game Engine.
Uses a two-stage approach:
1. Agents generate natural language responses as strings
2. GameMaster interprets strings and converts to structured events
"""
from typing import Dict, List, Optional, Any, Callable, Awaitable, Union, Literal, Type
from pydantic import BaseModel, create_model, Field
from pydantic_ai import Agent as PydanticAgent, RunContext
import logging
from uuid import uuid4
import json

from base_models import (
    World, Zone, Character, Object, Item, Event, EventType
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agentique.agents")

# Agent context models
class AgentContext(BaseModel):
    """Context provided to agents when they run"""
    world: World
    character_id: str  # ID of the character making the request or being controlled
    zone_id: str       # Current zone ID
    
    class Config:
        arbitrary_types_allowed = True

class GameMasterContext(BaseModel):
    """Context provided to the GameMaster"""
    world: World
    character_id: str   # ID of the character/entity that generated the response
    zone_id: str        # Current zone ID
    agent_type: str     # Type of agent that generated the response
    action_type: Optional[str] = None  # Type of action (for character agents)
    target_id: Optional[str] = None    # Target entity ID if relevant
    
    class Config:
        arbitrary_types_allowed = True

class AgentType(str):
    """Types of agents in the system"""
    CHARACTER = "character"
    ZONE = "zone"
    OBJECT = "object"
    SYSTEM = "system"
    GAME_MASTER = "game_master"

class BaseAgent:
    """
    Base agent class that provides core functionality for all agents
    """
    
    def __init__(
        self, 
        entity_id: str,
        agent_type: str,
        model_name: str = "openai:gpt-4o-mini",
        system_prompt: str = ""
    ):
        self.entity_id = entity_id
        self.agent_type = agent_type
        self.id = f"{agent_type}_{entity_id}_{str(uuid4())[:4]}"
        
        # Create the pydantic_ai agent that returns strings
        self.agent = PydanticAgent(
            model_name,
            result_type=str,  # Now all agents return strings
            deps_type=AgentContext,
            system_prompt=system_prompt
        )
        
        # Cache of tool functions
        self.tools: List[Callable] = []
    
    def add_tool(self, func: Callable[[RunContext[AgentContext]], Awaitable[str]]) -> None:
        """Add a tool function to the agent"""
        tool_func = self.agent.tool(func)
        self.tools.append(tool_func)

    async def run(self, message: str, context: AgentContext) -> str:
        """Run the agent with a message and context - returns a string response"""
        try:
            result = await self.agent.run(message, deps=context)
            return result.data
        except Exception as e:
            logger.error(f"Error running agent {self.id}: {str(e)}")
            # Return a default error message
            return f"Error: {str(e)}"

class CharacterAgent(BaseAgent):
    """
    Agent that controls a character and generates natural language responses
    """
    
    def __init__(
        self,
        character_id: str,
        character_name: str,
        character_description: str,
        is_interpreter: bool = False,
        model_name: str = "openai:gpt-4o-mini"
    ):
        # Different system prompts based on whether this is a player command interpreter
        # or an autonomous character agent
        if is_interpreter:
            system_prompt = """
            You are an AI assistant that interprets player commands in an interactive text adventure.
            
            Your primary goal is to understand the player's intent, regardless of how they phrase it.
            Focus on what the player is trying to accomplish rather than specific command syntax.
            
            For example:
            - "look around", "what do I see?", "describe my surroundings" → use the look tool
            - "go to tavern", "head north", "enter the cave" → use the move tool
            - "talk to innkeeper about rumors", "ask guard about town" → use the talk tool
            - "check fountain", "inspect the crystal", "what's this tree?" → use the examine tool
            - "check my stuff", "what am I carrying?" → use the inventory tool
            
            You should intelligently handle contextual commands like:
            - "talk to her" (infer which character is meant from context)
            - "pick it up" (infer which object is meant from recent interactions)
            - "go back" (infer the previous location)
            
            When you decide on a tool to use, respond with what tool to use and the necessary parameters.
            
            Example responses:
            - "ACTION: look"
            - "ACTION: move | destination: tavern"
            - "ACTION: talk | target: innkeeper | message: What do you know about the old castle?"
            - "ACTION: examine | object: fountain"
            - "ACTION: inventory"
            
            If you need clarification, respond with a simple question like "Who would you like to talk to?"
            
            Remember, your job is to make the game enjoyable by understanding what the player wants to do,
            not forcing them to learn specific command structures.
            """
        else:
            system_prompt = f"""
            You are {character_name}, {character_description}
            
            You exist in a rich, interactive fantasy world. As this character, you should:
            
            1. Respond naturally and stay true to your character's personality, background, and motivations
            2. React to player interactions based on your character's knowledge, feelings, and biases
            3. Engage in meaningful dialogue that reflects your character's goals and interests
            4. Remember past interactions and reference them when appropriate
            5. Have opinions about the world around you and other characters you know
            
            When conversing with players, use natural language and appropriate emotional responses.
            Always speak in first person as your character would. Don't describe your actions in third person.
            
            Your responses will be interpreted by the game system automatically, so just focus on
            providing natural, in-character responses.
            """
        
        super().__init__(
            entity_id=character_id,
            agent_type=AgentType.CHARACTER,
            model_name=model_name,
            system_prompt=system_prompt
        )
        
        self.is_interpreter = is_interpreter
        
        # Add character-specific tools for the interpreter
        if is_interpreter:
            self._add_interpreter_tools()
    
    def _add_interpreter_tools(self):
        """Add tools for the character interpreter"""
        
        @self.agent.tool
        async def look(ctx: RunContext[AgentContext]) -> str:
            """Look around the current zone"""
            return "ACTION: look"
        
        @self.agent.tool
        async def move(ctx: RunContext[AgentContext], destination: str) -> str:
            """Move to a connected zone"""
            return f"ACTION: move | destination: {destination}"
        
        @self.agent.tool
        async def talk(ctx: RunContext[AgentContext], target: str, message: str) -> str:
            """Talk to another character in the current zone"""
            return f"ACTION: talk | target: {target} | message: {message}"
        
        @self.agent.tool
        async def examine(ctx: RunContext[AgentContext], object_name: str) -> str:
            """Examine an object in the current zone"""
            return f"ACTION: examine | object: {object_name}"
        
        @self.agent.tool
        async def inventory(ctx: RunContext[AgentContext]) -> str:
            """Check the character's inventory"""
            return "ACTION: inventory"

class ZoneAgent(BaseAgent):
    """Agent for a zone that generates descriptive text"""
    
    def __init__(
        self,
        zone_id: str,
        zone_name: str,
        model_name: str = "openai:gpt-4o-mini"
    ):
        system_prompt = f"""
        You embody the environment and atmosphere of "{zone_name}".
        
        Your purpose is to create immersive, evocative descriptions that bring this location to life:
        
        1. Engage all senses in your descriptions - not just what can be seen, but also sounds, smells, 
           textures, and the general feel of the environment
           
        2. Adjust your tone and style to match the atmosphere of the location (peaceful, foreboding, 
           mysterious, welcoming, etc.)
           
        3. Highlight interesting or unique features that might prompt player exploration or interaction
        
        4. Subtly incorporate environmental storytelling - hints about the history, purpose, or 
           significance of the location
           
        5. Adapt descriptions based on time of day, weather, or other changing conditions when applicable
        
        6. Include dynamic elements - what's happening in this location right now besides the static environment
        
        Focus on creating a rich, atmospheric sense of place rather than simply listing objects and characters.
        Your descriptions should evoke emotion and curiosity, making players feel truly present in this world.
        
        Respond with descriptive text only - the system will automatically format your response.
        """
        
        super().__init__(
            entity_id=zone_id,
            agent_type=AgentType.ZONE,
            model_name=model_name,
            system_prompt=system_prompt
        )

class ObjectAgent(BaseAgent):
    """Agent for an interactive object that generates descriptive responses"""
    
    def __init__(
        self,
        object_id: str,
        object_name: str,
        object_description: str,
        model_name: str = "openai:gpt-4o-mini"
    ):
        system_prompt = f"""
        You represent: {object_name}
        Description: {object_description}
        
        As this object, you should respond to a wide variety of interactions in imaginative but consistent ways:
        
        1. Consider diverse ways players might interact with you beyond just looking:
           - Touching, pushing, pulling, lifting, turning
           - Using tools or other objects with you
           - Applying different substances to you
           - Speaking to you (if appropriate for the object)
           
        2. Respond based on your physical properties:
           - Materials (wood, metal, stone, cloth, etc.)
           - Size, weight, temperature
           - Age, condition, state of repair
           - Moving parts or mechanisms
           
        3. Consider cause and effect relationships:
           - What happens when interacted with in different ways?
           - Does the object change state? Make sounds? Move? 
           - Does it reveal new information or features with certain interactions?
           
        4. If you have special properties (magical, technological, etc.), incorporate these
           into your responses in interesting but logical ways
           
        Create a sense that this object exists within a physically consistent world, while still allowing
        for discovery and surprise. Don't limit yourself to only the obvious interactions.
        
        Respond with descriptive text about what happens during the interaction - the system will
        automatically format your response appropriately.
        """
        
        super().__init__(
            entity_id=object_id,
            agent_type=AgentType.OBJECT,
            model_name=model_name,
            system_prompt=system_prompt
        )

class GameMasterAgent:
    """
    Special agent that interprets string responses from other agents and converts them to structured events.
    """
    
    def __init__(self, model_name: str = "openai:gpt-4o-mini"):
        system_prompt = """
        You are the GameMaster AI that interprets responses from various game agents and converts them into
        structured game events for processing by the game engine.
        
        Your task is to analyze text input and determine:
        1. What type of event it represents
        2. The content of the event
        3. Any relevant source and target entities
        4. Any additional metadata
        
        You will be given context about:
        - The type of agent that generated the response
        - The ID of the entity that generated it
        - The current zone
        - Any target entity (if applicable)
        
        You need to convert this to a structured event.
        
        EVENT TYPES:
        - MESSAGE: General information displayed to a player
        - MOVEMENT: Character moving from one zone to another
        - DIALOGUE: Character speaking to another character
        - INTERACTION: Character interacting with an object
        - ITEM_TRANSFER: Item being transferred between characters or locations
        - WORLD_STATE: A change in the game world state
        - SYSTEM: System-level messages or errors
        
        For interpreter responses, you'll receive formatted strings like:
        "ACTION: look"
        "ACTION: move | destination: tavern"
        "ACTION: talk | target: innkeeper | message: Hello there!"
        
        For these, extract the action type and parameters, then map them to the appropriate event type.
        
        For character, zone, and object agents, you'll receive natural language responses that need
        to be interpreted based on the context provided.
        
        Return a JSON structure with the event details, following this format:
        {
          "type": "EVENT_TYPE",
          "content": "Event content or message",
          "source_id": "ID of the source entity",
          "target_id": "ID of the target entity (if applicable)",
          "metadata": {}
        }
        
        The metadata can include any additional information relevant to the event.
        """
        
        # Create the pydantic_ai agent
        self.agent = PydanticAgent(
            model_name,
            result_type=str,  # Returns a JSON string
            deps_type=GameMasterContext,
            system_prompt=system_prompt
        )
    
    async def interpret(self, response: str, context: GameMasterContext) -> Event:
        """
        Interpret a string response from another agent and convert it to an Event.
        
        Args:
            response: The string response from another agent
            context: Context about the agent and situation
            
        Returns:
            A structured Event object
        """
        try:
            # Handle interpreter responses with a simple parser first
            if context.agent_type == AgentType.CHARACTER and "ACTION:" in response:
                # Try to parse the structured response without using the LLM
                return self._parse_interpreter_response(response, context)
            
            # For other responses, use the LLM to interpret
            result = await self.agent.run(response, deps=context)
            json_str = result.data
            
            # Parse the JSON string
            try:
                event_data = json.loads(json_str)
                
                # Create an Event from the data
                event = Event(
                    type=event_data.get("type", EventType.MESSAGE),
                    content=event_data.get("content", ""),
                    source_id=event_data.get("source_id", context.character_id),
                    target_id=event_data.get("target_id", context.target_id),
                    metadata=event_data.get("metadata", {})
                )
                return event
            except json.JSONDecodeError:
                # If JSON parsing fails, create a simple message event
                logger.error(f"Error parsing GameMaster JSON: {json_str}")
                return Event(
                    type=EventType.MESSAGE,
                    content=response,
                    source_id=context.character_id,
                    target_id=context.target_id
                )
                
        except Exception as e:
            logger.error(f"Error in GameMaster interpretation: {str(e)}")
            # Return a simple event with the original response
            return Event(
                type=EventType.MESSAGE,
                content=response,
                source_id=context.character_id,
                target_id=context.target_id
            )
    
    def _parse_interpreter_response(self, response: str, context: GameMasterContext) -> Event:
        """Parse a structured interpreter response without using the LLM"""
        try:
            # Clean up the response
            response = response.strip()
            
            # Simple parser for structured responses
            if response.startswith("ACTION:"):
                parts = response[7:].strip().split("|")
                action = parts[0].strip().lower()
                
                # Parse parameters
                params = {}
                for part in parts[1:]:
                    if ":" in part:
                        key, value = part.split(":", 1)
                        params[key.strip().lower()] = value.strip()
                
                # Map to appropriate event
                if action == "look":
                    return Event(
                        type=EventType.MESSAGE,
                        content="Looking around",  # Will be replaced by zone description
                        source_id=context.character_id,
                        target_id=context.character_id,
                        metadata={"action": "look"}
                    )
                
                elif action == "move":
                    destination = params.get("destination", "")
                    return Event(
                        type=EventType.MOVEMENT,
                        content=f"Moving to {destination}",
                        source_id=context.character_id,
                        target_id=None,  # Will be filled in by the game engine
                        metadata={"action": "move", "destination": destination}
                    )
                
                elif action == "talk":
                    target = params.get("target", "")
                    message = params.get("message", "")
                    return Event(
                        type=EventType.DIALOGUE,
                        content=message,
                        source_id=context.character_id,
                        target_id=None,  # Will be filled in by the game engine
                        metadata={"action": "talk", "target_name": target}
                    )
                
                elif action == "examine":
                    object_name = params.get("object", "")
                    return Event(
                        type=EventType.INTERACTION,
                        content=f"Examining {object_name}",
                        source_id=context.character_id,
                        target_id=None,  # Will be filled in by the game engine
                        metadata={"action": "examine", "object_name": object_name}
                    )
                
                elif action == "inventory":
                    return Event(
                        type=EventType.MESSAGE,
                        content="Checking inventory",  # Will be replaced by inventory description
                        source_id=context.character_id,
                        target_id=context.character_id,
                        metadata={"action": "inventory"}
                    )
            
            # If parsing fails, return a simple message
            return Event(
                type=EventType.MESSAGE,
                content=response,
                source_id=context.character_id,
                target_id=context.target_id
            )
            
        except Exception as e:
            logger.error(f"Error parsing interpreter response: {str(e)}")
            return Event(
                type=EventType.MESSAGE,
                content=response,
                source_id=context.character_id,
                target_id=context.target_id
            )

class AgentFactory:
    """
    Factory class for creating agents for different entity types
    """
    
    @staticmethod
    def create_character_agent(
        character: Character,
        is_interpreter: bool = False,
        model_name: str = "openai:gpt-4o-mini"
    ) -> CharacterAgent:
        """Create an agent for a character"""
        return CharacterAgent(
            character_id=character.id,
            character_name=character.name,
            character_description=character.description,
            is_interpreter=is_interpreter,
            model_name=model_name
        )
    
    @staticmethod
    def create_zone_agent(
        zone: Zone,
        model_name: str = "openai:gpt-4o-mini"
    ) -> ZoneAgent:
        """Create an agent for a zone"""
        return ZoneAgent(
            zone_id=zone.id,
            zone_name=zone.name,
            model_name=model_name
        )
    
    @staticmethod
    def create_object_agent(
        obj: Object,
        model_name: str = "openai:gpt-4o-mini"
    ) -> ObjectAgent:
        """Create an agent for an object"""
        return ObjectAgent(
            object_id=obj.id,
            object_name=obj.name,
            object_description=obj.description,
            model_name=model_name
        )
    
    @staticmethod
    def create_game_master(
        model_name: str = "openai:gpt-4o-mini"
    ) -> GameMasterAgent:
        """Create a GameMaster agent"""
        return GameMasterAgent(model_name=model_name)