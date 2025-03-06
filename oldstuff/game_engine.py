import asyncio
from typing import Dict, List, Optional, Tuple, Union, Any, Set
from datetime import datetime
import logging

from base_models import (
    World, Zone, NPC, Player, Object, Item, Event, EventType,
    Memory, MemoryStore, Inventory, InventoryItem
)

from agent_system import (
    AgentiqueAgent, AgentGraph, ZoneAgent, NPCAgent,
    ObjectAgent, PlayerAgent, AgentContext, AgentResult
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("agentique")

class EventBus:
    """
    Event distribution system that allows components to subscribe to and publish events.
    """
    
    def __init__(self):
        self.subscribers: Dict[EventType, List[callable]] = {}
        self.all_subscribers: List[callable] = []  # Subscribers to all event types
    
    def subscribe(self, event_type: Optional[EventType], handler: callable) -> None:
        """
        Subscribe to a specific event type or all events if event_type is None.
        
        Args:
            event_type: The event type to subscribe to, or None for all events
            handler: Async function that takes an Event as its argument
        """
        if event_type is None:
            self.all_subscribers.append(handler)
        else:
            if event_type not in self.subscribers:
                self.subscribers[event_type] = []
            self.subscribers[event_type].append(handler)
    
    def unsubscribe(self, event_type: Optional[EventType], handler: callable) -> None:
        """
        Unsubscribe from a specific event type or all events if event_type is None.
        
        Args:
            event_type: The event type to unsubscribe from, or None for all events
            handler: The handler function to unsubscribe
        """
        if event_type is None:
            if handler in self.all_subscribers:
                self.all_subscribers.remove(handler)
        else:
            if event_type in self.subscribers and handler in self.subscribers[event_type]:
                self.subscribers[event_type].remove(handler)
    
    async def publish(self, event: Event) -> None:
        """
        Publish an event to all subscribed handlers.
        
        Args:
            event: The event to publish
        """
        # Call type-specific subscribers
        if event.type in self.subscribers:
            for handler in self.subscribers[event.type]:
                try:
                    await handler(event)
                except Exception as e:
                    logger.error(f"Error in event handler for {event.type}: {str(e)}")
        
        # Call subscribers to all events
        for handler in self.all_subscribers:
            try:
                await handler(event)
            except Exception as e:
                logger.error(f"Error in global event handler: {str(e)}")

class GameEngine:
    """
    Main game engine that coordinates the world, agents, and event handling.
    """
    
    def __init__(self):
        self.world = World(id="world", name="Default World", description="A default game world")
        self.agent_graph = AgentGraph()
        self.event_bus = EventBus()
        self.memory_store = MemoryStore()
        self.running = False
        self.tick_rate = 1.0  # seconds per tick
        
        # Map of entity IDs to their respective agents
        self.entity_agents: Dict[str, Union[ZoneAgent, NPCAgent, ObjectAgent, PlayerAgent]] = {}
        
        # Set up event handlers
        self._setup_event_handlers()
    
    def _setup_event_handlers(self) -> None:
        """Set up the default event handlers"""
        
        # Log all events
        async def log_event(event: Event) -> None:
            logger.info(f"EVENT: {event.type} from {event.source_id} to {event.target_id}: {event.content}")
        
        self.event_bus.subscribe(None, log_event)  # Subscribe to all events
        
        # Handle movement events
        async def handle_movement(event: Event) -> None:
            if event.type != EventType.MOVEMENT:
                return
            
            # Get the player who moved
            player_id = event.source_id
            player, _ = self.world.find_character(player_id)
            
            if not player or not isinstance(player, Player):
                return
            
            # Update last active timestamp
            player.last_active = datetime.now()
            
            # Log movement for memory
            memory = Memory(
                owner_id=player_id,
                content=f"Moved to {event.target_id}",
                context={"event_type": "movement", "timestamp": datetime.now().isoformat()},
                importance=3,
                related_ids=[event.target_id]
            )
            self.memory_store.add_memory(memory)
            
            # If there's a zone agent for the new zone, notify it
            if event.target_id in self.entity_agents:
                zone_agent = self.entity_agents[event.target_id]
                
                # Create context for the zone agent
                context = AgentContext(
                    world=self.world,
                    zone_id=event.target_id,
                    character_id=player_id,
                    memory_store=self.memory_store
                )
                
                # Run the zone agent with a notification about the player's arrival
                try:
                    await zone_agent.run(f"Player {player.name} has arrived in the zone.", context)
                except Exception as e:
                    logger.error(f"Error notifying zone agent about movement: {str(e)}")
        
        self.event_bus.subscribe(EventType.MOVEMENT, handle_movement)
        
        # Handle dialogue events
        async def handle_dialogue(event: Event) -> None:
            if event.type != EventType.DIALOGUE:
                return
            
            # If there's no target, we can't route the dialogue
            if not event.target_id:
                return
            
            # Find the source and target entities
            source_entity = None
            source_zone = None
            
            if event.source_id:
                source_entity, source_zone = self.world.find_character(event.source_id)
            
            target_entity = None
            target_zone = None
            
            if event.target_id:
                target_entity, target_zone = self.world.find_character(event.target_id)
            
            # If the source and target aren't in the same zone, we can't route the dialogue
            if source_zone and target_zone and source_zone.id != target_zone.id:
                return
            
            # If the target entity has an agent, route the dialogue to it
            if event.target_id in self.entity_agents and source_entity:
                target_agent = self.entity_agents[event.target_id]
                
                # Create context for the target agent
                context = AgentContext(
                    world=self.world,
                    zone_id=target_zone.id if target_zone else None,
                    character_id=event.source_id,
                    memory_store=self.memory_store
                )
                
                # Run the target agent with the dialogue
                try:
                    result = await target_agent.run(event.content, context)
                    
                    # If the result is an event, publish it
                    if hasattr(result, 'event'):
                        await self.event_bus.publish(result.event)
                except Exception as e:
                    logger.error(f"Error routing dialogue to agent: {str(e)}")
            
            # Store dialogue in memory for both participants
            if event.source_id:
                source_memory = Memory(
                    owner_id=event.source_id,
                    content=f"Said to {event.target_id}: {event.content}",
                    context={"event_type": "dialogue", "timestamp": datetime.now().isoformat()},
                    importance=4,
                    related_ids=[event.target_id]
                )
                self.memory_store.add_memory(source_memory)
            
            if event.target_id:
                target_memory = Memory(
                    owner_id=event.target_id,
                    content=f"Heard from {event.source_id}: {event.content}",
                    context={"event_type": "dialogue", "timestamp": datetime.now().isoformat()},
                    importance=4,
                    related_ids=[event.source_id]
                )
                self.memory_store.add_memory(target_memory)
        
        self.event_bus.subscribe(EventType.DIALOGUE, handle_dialogue)
        
        # Handle interaction events
        async def handle_interaction(event: Event) -> None:
            if event.type != EventType.INTERACTION:
                return
            
            # If there's no target, we can't route the interaction
            if not event.target_id:
                return
            
            # Find the source entity and its zone
            source_entity = None
            source_zone = None
            
            if event.source_id:
                source_entity, source_zone = self.world.find_character(event.source_id)
            
            # If the target is an object, we need to find it in the zone
            target_obj = None
            if source_zone:
                target_obj = source_zone.get_object(event.target_id)
            
            # If the object has an agent, route the interaction to it
            if event.target_id in self.entity_agents and source_entity:
                obj_agent = self.entity_agents[event.target_id]
                
                # Create context for the object agent
                context = AgentContext(
                    world=self.world,
                    zone_id=source_zone.id if source_zone else None,
                    character_id=event.source_id,
                    object_id=event.target_id,
                    memory_store=self.memory_store
                )
                
                # Run the object agent with the interaction
                try:
                    result = await obj_agent.run(event.content, context)
                    
                    # If the result is an event, publish it
                    if hasattr(result, 'event'):
                        await self.event_bus.publish(result.event)
                except Exception as e:
                    logger.error(f"Error routing interaction to agent: {str(e)}")
        
        self.event_bus.subscribe(EventType.INTERACTION, handle_interaction)
        
        # Handle trade events
        async def handle_trade(event: Event) -> None:
            if event.type != EventType.TRADE:
                return
            
            # For now, just log the trade
            logger.info(f"TRADE: {event.source_id} -> {event.target_id}: {event.content}")
            
            # In a full implementation, this would handle the actual trade mechanics
        
        self.event_bus.subscribe(EventType.TRADE, handle_trade)
    
    def create_world(self, name: str, description: str) -> World:
        """Create a new game world"""
        self.world = World(id="world", name=name, description=description)
        return self.world
    
    def add_zone(self, zone: Zone) -> None:
        """Add a zone to the world and create an agent for it"""
        # Add the zone to the world
        self.world.add_zone(zone)
        
        # Create an agent for the zone
        zone_agent = ZoneAgent(zone.id)
        self.entity_agents[zone.id] = zone_agent
        
        # Add the agent to the graph
        self.agent_graph.add_agent(zone.id, zone_agent)
        
        logger.info(f"Added zone: {zone.name} ({zone.id})")
    
    def add_npc(self, npc: NPC, zone_id: str) -> None:
        """Add an NPC to a zone and create an agent for it"""
        # Get the zone
        zone = self.world.get_zone(zone_id)
        if not zone:
            raise ValueError(f"Zone {zone_id} not found")
        
        # Add the NPC to the zone
        zone.add_npc(npc)
        
        # Create an agent for the NPC
        npc_agent = NPCAgent(npc)
        self.entity_agents[npc.id] = npc_agent
        
        # Add the agent to the graph
        self.agent_graph.add_agent(npc.id, npc_agent)
        
        # Connect the NPC agent to the zone agent
        self.agent_graph.connect(zone_id, npc.id)
        self.agent_graph.connect(npc.id, zone_id)
        
        logger.info(f"Added NPC: {npc.name} ({npc.id}) to zone {zone.name}")
    
    def add_object(self, obj: Object, zone_id: str) -> None:
        """Add an object to a zone and create an agent for it"""
        # Get the zone
        zone = self.world.get_zone(zone_id)
        if not zone:
            raise ValueError(f"Zone {zone_id} not found")
        
        # Add the object to the zone
        zone.add_object(obj)
        
        # Create an agent for the object
        obj_agent = ObjectAgent(obj)
        self.entity_agents[obj.id] = obj_agent
        
        # Add the agent to the graph
        self.agent_graph.add_agent(obj.id, obj_agent)
        
        # Connect the object agent to the zone agent
        self.agent_graph.connect(zone_id, obj.id)
        self.agent_graph.connect(obj.id, zone_id)
        
        logger.info(f"Added object: {obj.name} ({obj.id}) to zone {zone.name}")
    
    def add_player(self, player: Player, zone_id: str) -> None:
        """Add a player to a zone and create an agent for them"""
        # Get the zone
        zone = self.world.get_zone(zone_id)
        if not zone:
            raise ValueError(f"Zone {zone_id} not found")
        
        # Add the player to the zone
        zone.add_player(player)
        
        # Create an agent for the player
        player_agent = PlayerAgent(player)
        self.entity_agents[player.id] = player_agent
        
        # Add the agent to the graph
        self.agent_graph.add_agent(player.id, player_agent)
        
        # Connect the player agent to the zone agent
        self.agent_graph.connect(player.id, zone_id)
        
        logger.info(f"Added player: {player.name} ({player.id}) to zone {zone.name}")
    
    def connect_zones(self, zone_id1: str, zone_id2: str) -> bool:
        """Connect two zones bidirectionally"""
        success = self.world.connect_zones(zone_id1, zone_id2)
        
        if success:
            # Connect their agents too
            self.agent_graph.connect(zone_id1, zone_id2)
            self.agent_graph.connect(zone_id2, zone_id1)
            
            logger.info(f"Connected zones: {zone_id1} <-> {zone_id2}")
        
        return success
    
    async def process_player_input(self, player_id: str, input_text: str) -> Event:
        """
        Process input from a player and generate a response.
        
        Args:
            player_id: ID of the player
            input_text: The input text from the player
            
        Returns:
            An event representing the response
        """
        # Find the player
        player, zone = self.world.find_character(player_id)
        
        if not player or not isinstance(player, Player) or not zone:
            return Event(
                type=EventType.MESSAGE,
                source_id="system",
                target_id=player_id,
                content="Error: Player not found or not in a zone"
            )
        
        # Update last active timestamp
        player.last_active = datetime.now()
        
        # Create context for the player agent
        context = AgentContext(
            world=self.world,
            zone_id=zone.id,
            character_id=player_id,
            memory_store=self.memory_store
        )
        
        # Get the player agent
        if player_id not in self.entity_agents:
            return Event(
                type=EventType.MESSAGE,
                source_id="system",
                target_id=player_id,
                content="Error: No agent found for player"
            )
        
        player_agent = self.entity_agents[player_id]
        
        try:
            # Process the input with the player agent
            result = await player_agent.run(input_text, context)
            
            # If the result has an event, publish it
            if hasattr(result, 'event'):
                event = result.event
                await self.event_bus.publish(event)
                return event
            
            # If no event, create a generic response
            return Event(
                type=EventType.MESSAGE,
                source_id="system",
                target_id=player_id,
                content="Your command was processed, but no specific response was generated."
            )
            
        except Exception as e:
            logger.error(f"Error processing player input: {str(e)}")
            return Event(
                type=EventType.MESSAGE,
                source_id="system",
                target_id=player_id,
                content=f"Error processing your input: {str(e)}"
            )
    
    async def run_game_loop(self) -> None:
        """Run the main game loop"""
        self.running = True
        logger.info("Game loop started")
        
        while self.running:
            # Periodic tasks can go here, such as:
            # - NPC autonomous actions
            # - World events
            # - Time-based mechanics
            
            # For now, we'll just sleep
            await asyncio.sleep(self.tick_rate)
    
    def stop(self) -> None:
        """Stop the game loop"""
        self.running = False
        logger.info("Game loop stopped")