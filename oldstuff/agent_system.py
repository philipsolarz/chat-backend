from typing import Dict, List, Optional, Union, Any, Type, Callable, Awaitable
from pydantic import BaseModel
from pydantic_ai import Agent, RunContext
import asyncio

from base_models import (
    World, Zone, NPC, Player, Object, Item, Event, EventType,
    Memory, MemoryStore
)

class AgentContext(BaseModel):
    """Context for agent operations"""
    world: World
    zone_id: Optional[str] = None
    character_id: Optional[str] = None
    object_id: Optional[str] = None
    memory_store: MemoryStore
    
    class Config:
        arbitrary_types_allowed = True

class AgentResult(BaseModel):
    """Base result model for agent responses"""
    event: Event
    memory_update: Optional[Memory] = None

class AgentiqueAgent:
    """Wrapper around pydantic_ai Agent to provide additional functionality"""
    
    def __init__(
        self,
        model_name: str = "openai:gpt-4o-mini",
        system_prompt: str = "",
        result_type: Type = AgentResult
    ):
        self.agent = Agent(
            model_name,
            result_type=result_type,
            deps_type=AgentContext,
            system_prompt=system_prompt
        )
        self.tools = {}  # name -> function
    
    def add_tool(self, func: Callable[[RunContext[AgentContext], Any], Awaitable[Any]]) -> None:
        """Add a tool function to the agent"""
        self.agent.tool(func)
        self.tools[func.__name__] = func
    
    async def run(self, message: str, context: AgentContext) -> Any:
        """Run the agent with a message and context"""
        result = await self.agent.run(message, deps=context)
        
        # If the result includes a memory update, store it
        if hasattr(result.data, 'memory_update') and result.data.memory_update:
            context.memory_store.add_memory(result.data.memory_update)
            
        return result.data

class AgentGraph:
    """
    A directed graph of agents that can route messages between them.
    """
    
    def __init__(self):
        self.agents: Dict[str, AgentiqueAgent] = {}
        self.connections: Dict[str, List[str]] = {}  # source_id -> [target_ids]
    
    def add_agent(self, agent_id: str, agent: AgentiqueAgent) -> None:
        """Add an agent to the graph"""
        self.agents[agent_id] = agent
        if agent_id not in self.connections:
            self.connections[agent_id] = []
    
    def connect(self, source_id: str, target_id: str) -> None:
        """Connect two agents (directed)"""
        if source_id not in self.agents or target_id not in self.agents:
            raise ValueError(f"Both agents must be in the graph: {source_id}, {target_id}")
        
        if source_id not in self.connections:
            self.connections[source_id] = []
        
        if target_id not in self.connections[source_id]:
            self.connections[source_id].append(target_id)
    
    def disconnect(self, source_id: str, target_id: str) -> None:
        """Disconnect two agents"""
        if source_id in self.connections and target_id in self.connections[source_id]:
            self.connections[source_id].remove(target_id)
    
    def get_connections(self, agent_id: str) -> List[str]:
        """Get all agents that a specific agent is connected to"""
        return self.connections.get(agent_id, [])
    
    async def route_message(
        self,
        source_id: str,
        message: str,
        context: AgentContext,
        target_id: Optional[str] = None,
        max_hops: int = 3
    ) -> Dict[str, Any]:
        """
        Route a message from a source agent to either a specific target agent
        or to all connected agents within max_hops.
        
        Returns a dictionary mapping agent IDs to their responses.
        """
        if source_id not in self.agents:
            raise ValueError(f"Source agent not found: {source_id}")
        
        results = {}
        visited = set()
        
        async def _route(current_id: str, current_message: str, current_context: AgentContext, hops: int) -> None:
            if hops > max_hops or current_id in visited:
                return
            
            visited.add(current_id)
            
            if current_id == target_id or target_id is None:
                # Process with the current agent
                agent = self.agents[current_id]
                try:
                    result = await agent.run(current_message, current_context)
                    results[current_id] = result
                    
                    # If we're targeting a specific agent and found it, we're done
                    if current_id == target_id:
                        return
                except Exception as e:
                    results[current_id] = f"Error: {str(e)}"
            
            # Continue routing if we haven't reached max hops
            if hops < max_hops:
                for next_id in self.connections.get(current_id, []):
                    # Create a modified context for the next hop
                    next_context = AgentContext(
                        world=current_context.world,
                        zone_id=current_context.zone_id,
                        character_id=current_context.character_id,
                        object_id=current_context.object_id,
                        memory_store=current_context.memory_store
                    )
                    
                    # Include the current result in the message
                    next_message = f"Routed from {current_id}: {current_message}"
                    
                    await _route(next_id, next_message, next_context, hops + 1)
        
        # Start routing from the source
        await _route(source_id, message, context, 0)
        
        return results

class ZoneAgent(AgentiqueAgent):
    """Agent specifically for managing a zone"""
    
    def __init__(
        self,
        zone_id: str,
        model_name: str = "openai:gpt-4o-mini",
        system_prompt: str = ""
    ):
        self.zone_id = zone_id
        
        # Enhance the system prompt with zone-specific information
        zone_prompt = f"""
        You are the AI managing the zone with ID {zone_id}.
        Your responsibility is to:
        1. Handle player interactions within this zone
        2. Route messages to the appropriate NPCs or objects
        3. Describe the environment and provide immersive responses
        4. Keep track of the state of the zone and its contents
        
        {system_prompt}
        """
        
        super().__init__(
            model_name=model_name,
            system_prompt=zone_prompt
        )
        
        # Add zone-specific tools
        self._add_zone_tools()
    
    def _add_zone_tools(self):
        """Add zone-specific tools to the agent"""
        
        @self.agent.tool
        async def describe_zone(ctx: RunContext[AgentContext]) -> Event:
            """Describe the current zone and its contents"""
            zone = ctx.deps.world.get_zone(self.zone_id)
            if not zone:
                return Event(
                    type=EventType.MESSAGE,
                    source_id=self.zone_id,
                    content=f"Error: Zone {self.zone_id} not found"
                )
            
            # Build a description of the zone
            npcs_desc = ", ".join([npc.name for npc in zone.npcs]) if zone.npcs else "no NPCs"
            players_desc = ", ".join([player.name for player in zone.players]) if zone.players else "no players"
            objects_desc = ", ".join([obj.name for obj in zone.objects]) if zone.objects else "no objects"
            
            description = f"""
            {zone.name}: {zone.description}
            
            Present here: {npcs_desc}
            Players: {players_desc}
            Objects: {objects_desc}
            """
            
            return Event(
                type=EventType.MESSAGE,
                source_id=self.zone_id,
                content=description
            )
        
        @self.agent.tool
        async def route_to_npc(ctx: RunContext[AgentContext], npc_id: str, message: str) -> Event:
            """Route a message to an NPC in this zone"""
            zone = ctx.deps.world.get_zone(self.zone_id)
            if not zone:
                return Event(
                    type=EventType.MESSAGE,
                    source_id=self.zone_id,
                    content=f"Error: Zone {self.zone_id} not found"
                )
            
            # Find the NPC
            npc = zone.get_character(npc_id)
            if not npc or not isinstance(npc, NPC):
                return Event(
                    type=EventType.MESSAGE,
                    source_id=self.zone_id,
                    content=f"Error: NPC {npc_id} not found in this zone"
                )
            
            # In a real implementation, this would route to the NPC's agent
            # For now, we'll just return a placeholder event
            return Event(
                type=EventType.DIALOGUE,
                source_id=npc_id,
                target_id=ctx.deps.character_id,
                content=f"[NPC {npc.name} would respond to: {message}]"
            )
        
        @self.agent.tool
        async def interact_with_object(ctx: RunContext[AgentContext], object_id: str) -> Event:
            """Interact with an object in this zone"""
            zone = ctx.deps.world.get_zone(self.zone_id)
            if not zone:
                return Event(
                    type=EventType.MESSAGE,
                    source_id=self.zone_id,
                    content=f"Error: Zone {self.zone_id} not found"
                )
            
            # Find the object
            obj = zone.get_object(object_id)
            if not obj:
                return Event(
                    type=EventType.MESSAGE,
                    source_id=self.zone_id,
                    content=f"Error: Object {object_id} not found in this zone"
                )
            
            # In a real implementation, this would route to the object's agent
            # For now, we'll just return a placeholder event
            return Event(
                type=EventType.INTERACTION,
                source_id=ctx.deps.character_id or "system",
                target_id=object_id,
                content=f"[Interaction with {obj.name}: {obj.description}]"
            )

class NPCAgent(AgentiqueAgent):
    """Agent specifically for managing an NPC"""
    
    def __init__(
        self,
        npc: NPC,
        model_name: str = "openai:gpt-4o-mini",
        system_prompt: str = ""
    ):
        self.npc = npc
        
        # Enhance the system prompt with NPC-specific information
        npc_prompt = f"""
        You are {npc.name}, {npc.description}
        
        You should respond in character, based on your personality and history.
        For interactions, use the provided tools rather than describing actions.
        
        {system_prompt}
        """
        
        super().__init__(
            model_name=model_name,
            system_prompt=npc_prompt
        )
        
        # Add NPC-specific tools
        self._add_npc_tools()
    
    def _add_npc_tools(self):
        """Add NPC-specific tools to the agent"""
        
        @self.agent.tool
        async def speak(ctx: RunContext[AgentContext], message: str) -> Event:
            """Speak to a character"""
            return Event(
                type=EventType.DIALOGUE,
                source_id=self.npc.id,
                target_id=ctx.deps.character_id,
                content=message
            )
        
        @self.agent.tool
        async def trade(ctx: RunContext[AgentContext], offer_description: str) -> Event:
            """Engage in trade with a character"""
            return Event(
                type=EventType.TRADE,
                source_id=self.npc.id,
                target_id=ctx.deps.character_id,
                content=f"Trade offer: {offer_description}"
            )
        
        @self.agent.tool
        async def recall_memory(ctx: RunContext[AgentContext], topic: str = "") -> str:
            """Recall relevant memories about a topic or person"""
            memories = ctx.deps.memory_store.get_memories(self.npc.id)
            
            if not memories:
                return "I don't recall anything specific."
            
            # Filter for relevant memories if a topic is provided
            if topic:
                relevant_memories = [m for m in memories if topic.lower() in m.content.lower()]
                memories = relevant_memories if relevant_memories else memories
            
            return "\n".join([f"- {m.content}" for m in memories[:3]])

class ObjectAgent(AgentiqueAgent):
    """Agent specifically for managing an interactive object"""
    
    def __init__(
        self,
        obj: Object,
        model_name: str = "openai:gpt-4o-mini",
        system_prompt: str = ""
    ):
        self.obj = obj
        
        # Enhance the system prompt with object-specific information
        obj_prompt = f"""
        You represent the object: {obj.name}, {obj.description}
        
        You should provide responses that make sense for this object when players interact with it.
        Use the available tools to create appropriate interactive experiences.
        
        {system_prompt}
        """
        
        super().__init__(
            model_name=model_name,
            system_prompt=obj_prompt
        )
        
        # Add object-specific tools
        self._add_object_tools()
    
    def _add_object_tools(self):
        """Add object-specific tools to the agent"""
        
        @self.agent.tool
        async def interaction_result(
            ctx: RunContext[AgentContext], 
            description: str,
            effect_description: Optional[str] = None
        ) -> Event:
            """Describe the result of interacting with this object"""
            return Event(
                type=EventType.INTERACTION,
                source_id=self.obj.id,
                target_id=ctx.deps.character_id,
                content=description,
                metadata={"effect": effect_description} if effect_description else {}
            )

class PlayerAgent(AgentiqueAgent):
    """Agent that acts on behalf of a player"""
    
    def __init__(
        self,
        player: Player,
        model_name: str = "openai:gpt-4o-mini",
        system_prompt: str = ""
    ):
        self.player = player
        
        # Enhance the system prompt with player-specific information
        player_prompt = f"""
        You represent the player: {player.name}, {player.description}
        
        Your role is to help interpret the player's commands and translate them
        into meaningful actions in the game world. Use the available tools to
        fulfill the player's intentions.
        
        {system_prompt}
        """
        
        super().__init__(
            model_name=model_name,
            system_prompt=player_prompt
        )
        
        # Add player-specific tools
        self._add_player_tools()
    
    def _add_player_tools(self):
        """Add player-specific tools to the agent"""
        
        @self.agent.tool
        async def check_inventory(ctx: RunContext[AgentContext]) -> Event:
            """Check the player's inventory"""
            inventory = self.player.inventory
            
            if not inventory.items:
                return Event(
                    type=EventType.MESSAGE,
                    source_id="system",
                    target_id=self.player.id,
                    content="Your inventory is empty."
                )
            
            items_list = "\n".join([
                f"- {item.item.name} x{item.quantity}: {item.item.description}"
                for item in inventory.items
            ])
            
            return Event(
                type=EventType.MESSAGE,
                source_id="system",
                target_id=self.player.id,
                content=f"Inventory:\n{items_list}"
            )
        
        @self.agent.tool
        async def move_to_zone(ctx: RunContext[AgentContext], zone_id: str) -> Event:
            """Move to another zone"""
            current_zone_id = self.player.location_id
            if not current_zone_id:
                return Event(
                    type=EventType.MESSAGE,
                    source_id="system",
                    target_id=self.player.id,
                    content="You're not currently in any zone."
                )
            
            current_zone = ctx.deps.world.get_zone(current_zone_id)
            if not current_zone:
                return Event(
                    type=EventType.MESSAGE,
                    source_id="system",
                    target_id=self.player.id,
                    content=f"Error: Current zone {current_zone_id} not found"
                )
            
            # Check if target zone is adjacent
            if zone_id not in current_zone.adjacent_zones:
                return Event(
                    type=EventType.MESSAGE,
                    source_id="system",
                    target_id=self.player.id,
                    content=f"You cannot move directly to {zone_id} from here."
                )
            
            # Move the player
            success = ctx.deps.world.move_player(self.player.id, zone_id)
            if not success:
                return Event(
                    type=EventType.MESSAGE,
                    source_id="system",
                    target_id=self.player.id,
                    content=f"Failed to move to zone {zone_id}."
                )
            
            target_zone = ctx.deps.world.get_zone(zone_id)
            
            return Event(
                type=EventType.MOVEMENT,
                source_id=self.player.id,
                target_id=zone_id,
                content=f"You have moved to {target_zone.name}.",
                metadata={"from_zone_id": current_zone_id, "to_zone_id": zone_id}
            )
        
        @self.agent.tool
        async def talk_to_npc(ctx: RunContext[AgentContext], npc_id: str, message: str) -> Event:
            """Talk to an NPC"""
            zone_id = self.player.location_id
            if not zone_id:
                return Event(
                    type=EventType.MESSAGE,
                    source_id="system",
                    target_id=self.player.id,
                    content="You're not currently in any zone."
                )
            
            zone = ctx.deps.world.get_zone(zone_id)
            if not zone:
                return Event(
                    type=EventType.MESSAGE,
                    source_id="system",
                    target_id=self.player.id,
                    content=f"Error: Current zone {zone_id} not found"
                )
            
            # Find the NPC
            npc = zone.get_character(npc_id)
            if not npc or not isinstance(npc, NPC):
                return Event(
                    type=EventType.MESSAGE,
                    source_id="system",
                    target_id=self.player.id,
                    content=f"There's no NPC with ID {npc_id} here."
                )
            
            # In a real implementation, this would route to the NPC's agent
            # For now, we'll just return a placeholder event
            return Event(
                type=EventType.DIALOGUE,
                source_id=self.player.id,
                target_id=npc_id,
                content=message
            )
        
        @self.agent.tool
        async def interact_with_object(ctx: RunContext[AgentContext], object_id: str) -> Event:
            """Interact with an object"""
            zone_id = self.player.location_id
            if not zone_id:
                return Event(
                    type=EventType.MESSAGE,
                    source_id="system",
                    target_id=self.player.id,
                    content="You're not currently in any zone."
                )
            
            zone = ctx.deps.world.get_zone(zone_id)
            if not zone:
                return Event(
                    type=EventType.MESSAGE,
                    source_id="system",
                    target_id=self.player.id,
                    content=f"Error: Current zone {zone_id} not found"
                )
            
            # Find the object
            obj = zone.get_object(object_id)
            if not obj:
                return Event(
                    type=EventType.MESSAGE,
                    source_id="system",
                    target_id=self.player.id,
                    content=f"There's no object with ID {object_id} here."
                )
            
            # In a real implementation, this would route to the object's agent
            # For now, we'll just return a placeholder event
            return Event(
                type=EventType.INTERACTION,
                source_id=self.player.id,
                target_id=object_id,
                content=f"Interacting with {obj.name}"
            )