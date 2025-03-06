"""
Simple agent system for the Agentique Game Engine.
"""
from typing import Dict, List, Optional, Any, Callable, Awaitable, Union
from pydantic import BaseModel
from pydantic_ai import Agent, RunContext
import logging

from base_models import (
    World, Zone, NPC, Player, Object, Item, Event, EventType
)


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agentique")

class AgentContext(BaseModel):
    """Context provided to agents when they run"""
    world: World
    player_id: str
    zone_id: str
    
    class Config:
        arbitrary_types_allowed = True

class AgentResponse(BaseModel):
    """Response model for agent operations"""
    event: Event

class SimpleAgent:
    """
    A simple wrapper around pydantic_ai Agent that provides core functionality
    """
    
    def __init__(
        self, 
        entity_id: str,
        entity_type: str,
        model_name: str = "openai:gpt-4o-mini",
        system_prompt: str = ""
    ):
        self.entity_id = entity_id
        self.entity_type = entity_type  # "zone", "npc", "object", "player"
        
        # Create the pydantic_ai agent
        self.agent = Agent(
            model_name,
            result_type=AgentResponse,
            deps_type=AgentContext,
            system_prompt=system_prompt
        )
    
    def add_tool(self, func: Callable[[RunContext[AgentContext]], Awaitable[Event]]) -> None:
        """Add a tool function to the agent"""
        self.agent.tool(func)

    async def run(self, message: str, context: AgentContext) -> AgentResponse:
        """Run the agent with a message and context"""
        try:
            result = await self.agent.run(message, deps=context)
            return result.data
        except Exception as e:
            logger.error(f"Error running agent {self.entity_id}: {str(e)}")
            # Return a default error event if agent fails
            return AgentResponse(
                event=Event(
                    type=EventType.MESSAGE,
                    content=f"Error: {str(e)}",
                    source_id="system",
                    target_id=context.player_id
                )
            )

class ZoneAgent(SimpleAgent):
    """Agent for a zone that can describe the zone and route to NPCs/objects"""
    
    def __init__(
        self,
        zone_id: str,
        zone_name: str,
        model_name: str = "openai:gpt-4o-mini"
    ):
        system_prompt = f"""
        You are the AI for the zone "{zone_name}" (ID: {zone_id}).
        
        Your role is to:
        1. Describe the zone when players enter or look around
        2. Help players understand what they can do in this zone
        3. Respond to general inquiries about the zone
        
        Always stay in character and maintain the atmosphere of the zone.
        """
        
        super().__init__(
            entity_id=zone_id,
            entity_type="zone",
            model_name=model_name,
            system_prompt=system_prompt
        )
        
        # Add zone-specific tools
        self._add_zone_tools()
    
    def _add_zone_tools(self):
        """Add zone-specific tools"""
        
        @self.agent.tool
        async def describe_zone(ctx: RunContext[AgentContext]) -> Event:
            """Describe the current zone and what's in it"""
            zone = ctx.deps.world.zones.get(ctx.deps.zone_id)
            if not zone:
                return Event(
                    type=EventType.MESSAGE,
                    content=f"Error: Zone {ctx.deps.zone_id} not found",
                    source_id="system",
                    target_id=ctx.deps.player_id
                )
            
            # Build description
            objects_desc = ", ".join([obj.name for obj in zone.objects.values()]) if zone.objects else "nothing notable"
            npcs_desc = ", ".join([npc.name for npc in zone.npcs.values()]) if zone.npcs else "no one"
            exits_desc = ", ".join([ctx.deps.world.zones[z_id].name for z_id in zone.connected_zones if z_id in ctx.deps.world.zones])
            
            description = f"""
            {zone.name}
            {zone.description}
            
            You can see: {objects_desc}
            Present here: {npcs_desc}
            Exits: {exits_desc}
            """
            
            return Event(
                type=EventType.MESSAGE,
                content=description,
                source_id=zone.id,
                target_id=ctx.deps.player_id
            )

class NPCAgent(SimpleAgent):
    """Agent for an NPC that can engage in dialogue"""
    
    def __init__(
        self,
        npc_id: str,
        npc_name: str,
        npc_description: str,
        model_name: str = "openai:gpt-4o-mini"
    ):
        system_prompt = f"""
        You are {npc_name}, {npc_description}
        
        When interacting with players:
        1. Stay in character based on your description
        2. Provide information about yourself and your surroundings
        3. Remember you are an NPC in a game world
        
        Keep responses conversational and engaging.
        """
        
        super().__init__(
            entity_id=npc_id,
            entity_type="npc",
            model_name=model_name,
            system_prompt=system_prompt
        )
        
        # Add NPC-specific tools
        self._add_npc_tools()
    
    def _add_npc_tools(self):
        """Add NPC-specific tools"""
        
        @self.agent.tool
        async def speak(ctx: RunContext[AgentContext], message: str) -> Event:
            """Speak to the player"""
            # Get the NPC 
            zone = ctx.deps.world.zones.get(ctx.deps.zone_id)
            if not zone:
                return Event(
                    type=EventType.MESSAGE,
                    content="Error: Zone not found",
                    source_id="system",
                    target_id=ctx.deps.player_id
                )
            
            npc = zone.npcs.get(self.entity_id)
            if not npc:
                return Event(
                    type=EventType.MESSAGE,
                    content=f"Error: NPC {self.entity_id} not found in this zone",
                    source_id="system",
                    target_id=ctx.deps.player_id
                )
            
            # Record dialogue in NPC's history
            npc.dialogue_history.append(message)
            
            return Event(
                type=EventType.DIALOGUE,
                content=message,
                source_id=self.entity_id,
                target_id=ctx.deps.player_id
            )

class ObjectAgent(SimpleAgent):
    """Agent for an interactive object"""
    
    def __init__(
        self,
        object_id: str,
        object_name: str,
        object_description: str,
        model_name: str = "openai:gpt-4o-mini"
    ):
        system_prompt = f"""
        You represent the object: {object_name}, {object_description}
        
        When players interact with you:
        1. Describe what happens based on the object's nature
        2. Consider any special properties or functions of the object
        3. Keep the interaction appropriate to the object
        
        Focus on creating meaningful interactions with this object.
        """
        
        super().__init__(
            entity_id=object_id,
            entity_type="object",
            model_name=model_name,
            system_prompt=system_prompt
        )
        
        # Add object-specific tools
        self._add_object_tools()
    
    def _add_object_tools(self):
        """Add object-specific tools"""
        
        @self.agent.tool
        async def describe_interaction(ctx: RunContext[AgentContext], description: str) -> Event:
            """Describe what happens when the player interacts with this object"""
            return Event(
                type=EventType.INTERACTION,
                content=description,
                source_id=self.entity_id,
                target_id=ctx.deps.player_id
            )

class PlayerAgent(SimpleAgent):
    """Agent that interprets player commands and translates them to actions"""
    
    def __init__(
        self,
        player_id: str,
        model_name: str = "openai:gpt-4o-mini"
    ):
        system_prompt = """
        You are an AI assistant that helps interpret player commands in a text-based game.
        
        Your job is to:
        1. Understand what the player wants to do
        2. Use the appropriate tool to perform that action
        3. Keep responses helpful and concise
        
        Available actions:
        - look: Describe the current location
        - move: Move to a connected zone
        - talk: Talk to an NPC
        - examine: Examine an object
        - inventory: Check the player's inventory
        
        If the player's intent is unclear, ask for clarification.
        """
        
        super().__init__(
            entity_id=player_id,
            entity_type="player",
            model_name=model_name,
            system_prompt=system_prompt
        )
        
        # Add player-specific tools
        self._add_player_tools()
    
    def _add_player_tools(self):
        """Add player-specific tools"""
        
        @self.agent.tool
        async def look(ctx: RunContext[AgentContext]) -> Event:
            """Look around the current zone"""
            zone = ctx.deps.world.zones.get(ctx.deps.zone_id)
            if not zone:
                return Event(
                    type=EventType.MESSAGE,
                    content="Error: You're not in a valid zone",
                    source_id="system",
                    target_id=ctx.deps.player_id
                )
            
            # Build description
            objects_desc = ", ".join([obj.name for obj in zone.objects.values()]) if zone.objects else "nothing notable"
            npcs_desc = ", ".join([npc.name for npc in zone.npcs.values()]) if zone.npcs else "no one"
            exits_desc = ", ".join([ctx.deps.world.zones[z_id].name for z_id in zone.connected_zones if z_id in ctx.deps.world.zones])
            
            description = f"""
            {zone.name}
            {zone.description}
            
            You can see: {objects_desc}
            Present here: {npcs_desc}
            Exits: {exits_desc}
            """
            
            return Event(
                type=EventType.MESSAGE,
                content=description,
                source_id="system",
                target_id=ctx.deps.player_id
            )
        
        @self.agent.tool
        async def move(ctx: RunContext[AgentContext], destination: str) -> Event:
            """Move to a connected zone"""
            current_zone = ctx.deps.world.zones.get(ctx.deps.zone_id)
            if not current_zone:
                return Event(
                    type=EventType.MESSAGE,
                    content="Error: You're not in a valid zone",
                    source_id="system",
                    target_id=ctx.deps.player_id
                )
            
            # Try to find the destination zone by name first
            destination_zone_id = None
            for zone_id in current_zone.connected_zones:
                if zone_id in ctx.deps.world.zones:
                    zone = ctx.deps.world.zones[zone_id]
                    if destination.lower() in zone.name.lower():
                        destination_zone_id = zone_id
                        break
            
            # If not found by name, try by ID
            if not destination_zone_id and destination in current_zone.connected_zones:
                destination_zone_id = destination
            
            if not destination_zone_id:
                return Event(
                    type=EventType.MESSAGE,
                    content=f"You can't go to '{destination}' from here.",
                    source_id="system",
                    target_id=ctx.deps.player_id
                )
            
            # Move the player
            success = ctx.deps.world.move_player(
                ctx.deps.player_id, 
                ctx.deps.zone_id, 
                destination_zone_id
            )
            
            if not success:
                return Event(
                    type=EventType.MESSAGE,
                    content=f"Failed to move to {destination}.",
                    source_id="system",
                    target_id=ctx.deps.player_id
                )
            
            destination_zone = ctx.deps.world.zones[destination_zone_id]
            
            return Event(
                type=EventType.MOVEMENT,
                content=f"You move to {destination_zone.name}.",
                source_id=ctx.deps.player_id,
                target_id=destination_zone_id,
                metadata={"from_zone": ctx.deps.zone_id, "to_zone": destination_zone_id}
            )
        
        @self.agent.tool
        async def talk(ctx: RunContext[AgentContext], npc_name: str, message: str) -> Event:
            """Talk to an NPC in the current zone"""
            zone = ctx.deps.world.zones.get(ctx.deps.zone_id)
            if not zone:
                return Event(
                    type=EventType.MESSAGE,
                    content="Error: You're not in a valid zone",
                    source_id="system",
                    target_id=ctx.deps.player_id
                )
            
            # Find NPC by name
            target_npc = None
            target_npc_id = None
            
            for npc_id, npc in zone.npcs.items():
                if npc_name.lower() in npc.name.lower():
                    target_npc = npc
                    target_npc_id = npc_id
                    break
            
            if not target_npc:
                return Event(
                    type=EventType.MESSAGE,
                    content=f"There's no one named '{npc_name}' here.",
                    source_id="system",
                    target_id=ctx.deps.player_id
                )
            
            return Event(
                type=EventType.DIALOGUE,
                content=message,
                source_id=ctx.deps.player_id,
                target_id=target_npc_id
            )
        
        @self.agent.tool
        async def examine(ctx: RunContext[AgentContext], object_name: str) -> Event:
            """Examine an object in the current zone"""
            zone = ctx.deps.world.zones.get(ctx.deps.zone_id)
            if not zone:
                return Event(
                    type=EventType.MESSAGE,
                    content="Error: You're not in a valid zone",
                    source_id="system",
                    target_id=ctx.deps.player_id
                )
            
            # Find object by name
            target_obj = None
            target_obj_id = None
            
            for obj_id, obj in zone.objects.items():
                if object_name.lower() in obj.name.lower():
                    target_obj = obj
                    target_obj_id = obj_id
                    break
            
            if not target_obj:
                return Event(
                    type=EventType.MESSAGE,
                    content=f"There's no '{object_name}' here to examine.",
                    source_id="system",
                    target_id=ctx.deps.player_id
                )
            
            return Event(
                type=EventType.INTERACTION,
                content=f"You examine the {target_obj.name}: {target_obj.description}",
                source_id=ctx.deps.player_id,
                target_id=target_obj_id
            )
        
        @self.agent.tool
        async def inventory(ctx: RunContext[AgentContext]) -> Event:
            """Check the player's inventory"""
            # Find the player
            player = None
            for zone in ctx.deps.world.zones.values():
                if ctx.deps.player_id in zone.players:
                    player = zone.players[ctx.deps.player_id]
                    break
            
            if not player:
                return Event(
                    type=EventType.MESSAGE,
                    content="Error: Player not found",
                    source_id="system",
                    target_id=ctx.deps.player_id
                )
            
            # Format inventory contents
            if not player.inventory.items:
                return Event(
                    type=EventType.MESSAGE,
                    content="Your inventory is empty.",
                    source_id="system",
                    target_id=ctx.deps.player_id
                )
            
            inventory_list = []
            for item_id, quantity in player.inventory.items.items():
                item = ctx.deps.world.get_item(item_id)
                if item:
                    inventory_list.append(f"{item.name} ({quantity})")
            
            inventory_text = "Inventory:\n" + "\n".join(inventory_list)
            
            return Event(
                type=EventType.MESSAGE,
                content=inventory_text,
                source_id="system",
                target_id=ctx.deps.player_id
            )