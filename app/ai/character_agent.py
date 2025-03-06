from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from pydantic_ai import Agent, RunContext
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.services.character_service import CharacterService
from app.services.conversation_service import ConversationService
from app.services.message_service import MessageService
from app.services.world_service import WorldService
from app.services.zone_service import ZoneService

class EventType(str, Enum):
    SYSTEM = "system"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    MESSAGE = "message"

class Event(BaseModel):
    type: EventType
    content: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}

CHARACTER_AGENT = """
You are a CharacterAgent in a role-playing game. Your role is to interpret user messages and decide which action to take by calling one of your function tools. Your available tools and their uses are:

1. get_world(): Use this tool when the user asks for details about the overall world or environment (keywords: world, universe, environment, land, realm).
2. get_zone(): Use this tool when the user asks for information about the current zone, area, or location (keywords: zone, area, location, region, place).
3. get_objectives(): Use this tool when the user inquires about current quests, objectives, missions, or goals (keywords: objectives, quest, mission, goal).
4. get_status(): Use this tool when the user wants to know the character’s current status, health, HP, condition, or state (keywords: status, health, condition, HP).
5. get_inventory(): Use this tool when the user asks for the current inventory or items carried (keywords: inventory, items, bag, equipment).
6. send_message(message): This is your default tool. If the user's message does not clearly match any of the above, or if the input is general conversation, call send_message to translate the user’s text into in-character dialogue.

When processing each user message:
- Analyze the text for keywords or phrases related to each tool.
- If the message contains multiple intents, prioritize the most specific one.

- Do not include any extra commentary or explanation in your output—only the structured JSON response.
- Your goal is to provide the most relevant game information or in-character dialogue based on the user's query.

For example, if a user says "Tell me about the enchanted forest," you should detect the location-related intent and call get_zone(). If a user says "I feel great today!" with no clear actionable intent, default to send_message() to generate a character reply.

Follow these guidelines strictly to ensure that each user input is handled appropriately.
"""

@dataclass
class CharacterAgentDependencies:
    """Dependencies for agent operations"""
    db: Session
    world_service: Optional[WorldService] = None 
    zone_service: Optional[ZoneService] = None
    character_service: Optional[CharacterService] = None

character_agent = Agent(
            "openai:gpt-4o-mini",
            result_type=Event,
            deps_type=CharacterAgentDependencies,
            system_prompt=CHARACTER_AGENT
        )

@character_agent.tool
def get_world(ctx: RunContext) -> Event:
    return Event(
        type=EventType.SUCCESS,
        content="The world is vast and filled with ancient ruins, bustling cities, and mysterious forests."
    )

@character_agent.tool
def get_zone(ctx: RunContext) -> Event:
    return Event(
        type=EventType.SUCCESS,
        content="You are currently in the enchanted forest, where magic and nature intertwine."
    )

@character_agent.tool
def get_objectives(ctx: RunContext) -> Event:
    return Event(
        type=EventType.SUCCESS,
        content="Current Objective: Find the lost amulet hidden in the dragon’s cave."
    )

@character_agent.tool
def get_status(ctx: RunContext) -> Event:
    return Event(
        type=EventType.SUCCESS,
        content="Character Status: Healthy, with 100 HP and fully equipped for adventure."
    )

@character_agent.tool
def get_inventory(ctx: RunContext) -> Event:
    return Event(
        type=EventType.SUCCESS,
        content="Inventory: Sword, Shield, Potion of Healing, and a mysterious key."
    )

@character_agent.tool
def send_message(ctx: RunContext, message: str) -> Event:
    return Event(
        type=EventType.SUCCESS,
        content=f"Translated into character: {message}"
    )
