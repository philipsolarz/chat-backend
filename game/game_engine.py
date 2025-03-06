"""
Simple game engine for the Agentique Game Engine.
"""
import asyncio
import logging
from typing import Dict, List, Optional, Any, Callable

from base_models import (
    World, Zone, NPC, Player, Object, Item, Event, EventType
)

from agent_system import (
    SimpleAgent, ZoneAgent, NPCAgent, ObjectAgent, PlayerAgent, AgentContext
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agentique")

class EventHandler:
    """Simple event handler for routing events"""
    
    def __init__(self):
        self.handlers: Dict[EventType, List[Callable]] = {}
        self.global_handlers: List[Callable] = []
    
    def register(self, event_type: Optional[EventType], handler: Callable) -> None:
        """Register a handler for an event type (or all events if None)"""
        if event_type is None:
            self.global_handlers.append(handler)
        else:
            if event_type not in self.handlers:
                self.handlers[event_type] = []
            self.handlers[event_type].append(handler)
    
    async def handle(self, event: Event) -> None:
        """Handle an event by routing it to appropriate handlers"""
        # Call specific handlers
        if event.type in self.handlers:
            for handler in self.handlers[event.type]:
                try:
                    await handler(event)
                except Exception as e:
                    logger.error(f"Error in event handler: {str(e)}")
        
        # Call global handlers
        for handler in self.global_handlers:
            try:
                await handler(event)
            except Exception as e:
                logger.error(f"Error in global event handler: {str(e)}")

class SimpleGameEngine:
    """Simple game engine that manages the world and agents"""
    
    def __init__(self):
        self.world = World(name="Game World", description="A default game world")
        self.agents: Dict[str, SimpleAgent] = {}
        self.event_handler = EventHandler()
        self.running = False
        
        # Set up default event handlers
        self._setup_default_handlers()
    
    def _setup_default_handlers(self) -> None:
        """Set up default event handlers"""
        
        # Log all events
        async def log_event(event: Event) -> None:
            logger.info(f"EVENT: {event.type} - From: {event.source_id}, To: {event.target_id}")
            logger.info(f"Content: {event.content}")
        
        self.event_handler.register(None, log_event)
        
        # Handle movement events to update player location
        async def handle_movement(event: Event) -> None:
            if event.type != EventType.MOVEMENT:
                return
            
            # The metadata should contain from_zone and to_zone
            from_zone_id = event.metadata.get("from_zone")
            to_zone_id = event.metadata.get("to_zone")
            
            if not from_zone_id or not to_zone_id:
                return
            
            # Player has already been moved in the move() tool, but we can do other tasks
            # For example, we could automatically describe the new zone
            
            # Create context for describing the new zone
            player_id = event.source_id
            
            if not player_id or to_zone_id not in self.world.zones:
                return
            
            context = AgentContext(
                world=self.world,
                player_id=player_id,
                zone_id=to_zone_id
            )
            
            # Use the player agent to look around
            if player_id in self.agents:
                player_agent = self.agents[player_id]
                try:
                    response = await player_agent.run("look", context)
                    await self.event_handler.handle(response.event)
                except Exception as e:
                    logger.error(f"Error describing new zone: {str(e)}")
        
        self.event_handler.register(EventType.MOVEMENT, handle_movement)
        
        # Handle dialogue events to route to NPCs
        async def handle_dialogue(event: Event) -> None:
            if event.type != EventType.DIALOGUE:
                return
            
            # Make sure we have valid source and target
            if not event.source_id or not event.target_id:
                return
            
            # Determine if this is player->npc or npc->player
            if event.source_id in self.agents and self.agents[event.source_id].entity_type == "player":
                # Player is talking to NPC
                npc_id = event.target_id
                if npc_id in self.agents and self.agents[npc_id].entity_type == "npc":
                    # Find which zone they're in
                    player_zone = None
                    for zone in self.world.zones.values():
                        if event.source_id in zone.players:
                            player_zone = zone
                            break
                    
                    if not player_zone or npc_id not in player_zone.npcs:
                        # Player and NPC not in the same zone
                        await self.event_handler.handle(Event(
                            type=EventType.MESSAGE,
                            content="You can't talk to someone who isn't here.",
                            source_id="system",
                            target_id=event.source_id
                        ))
                        return
                    
                    # Create context for NPC response
                    context = AgentContext(
                        world=self.world,
                        player_id=event.source_id,
                        zone_id=player_zone.id
                    )
                    
                    # Run the NPC agent
                    npc_agent = self.agents[npc_id]
                    try:
                        response = await npc_agent.run(event.content, context)
                        await self.event_handler.handle(response.event)
                    except Exception as e:
                        logger.error(f"Error getting NPC response: {str(e)}")
            
            # If NPC is talking to player, we don't need to do anything special
        
        self.event_handler.register(EventType.DIALOGUE, handle_dialogue)
        
        # Handle interaction events
        async def handle_interaction(event: Event) -> None:
            if event.type != EventType.INTERACTION:
                return
            
            # Check if this is a player interacting with an object
            if not event.source_id or not event.target_id:
                return
            
            if event.source_id in self.agents and self.agents[event.source_id].entity_type == "player":
                # Player is interacting with object
                object_id = event.target_id
                if object_id in self.agents and self.agents[object_id].entity_type == "object":
                    # Find which zone they're in
                    player_zone = None
                    for zone in self.world.zones.values():
                        if event.source_id in zone.players:
                            player_zone = zone
                            break
                    
                    if not player_zone or object_id not in player_zone.objects:
                        # Player and object not in the same zone
                        await self.event_handler.handle(Event(
                            type=EventType.MESSAGE,
                            content="That object isn't here.",
                            source_id="system",
                            target_id=event.source_id
                        ))
                        return
                    
                    # Create context for object response
                    context = AgentContext(
                        world=self.world,
                        player_id=event.source_id,
                        zone_id=player_zone.id
                    )
                    
                    # Run the object agent
                    object_agent = self.agents[object_id]
                    try:
                        response = await object_agent.run(event.content, context)
                        await self.event_handler.handle(response.event)
                    except Exception as e:
                        logger.error(f"Error getting object response: {str(e)}")
        
        self.event_handler.register(EventType.INTERACTION, handle_interaction)
    
    def create_world(self, name: str, description: str) -> World:
        """Create a new game world"""
        self.world = World(name=name, description=description)
        return self.world
    
    def add_zone(self, zone: Zone) -> None:
        """Add a zone to the world and create an agent for it"""
        self.world.add_zone(zone)
        
        # Create zone agent
        zone_agent = ZoneAgent(zone.id, zone.name)
        self.agents[zone.id] = zone_agent
        
        logger.info(f"Added zone: {zone.name} ({zone.id})")
    
    def add_npc(self, npc: NPC, zone_id: str) -> None:
        """Add an NPC to a zone and create an agent for it"""
        zone = self.world.zones.get(zone_id)
        if not zone:
            raise ValueError(f"Zone {zone_id} not found")
        
        zone.add_npc(npc)
        
        # Create NPC agent
        npc_agent = NPCAgent(npc.id, npc.name, npc.description)
        self.agents[npc.id] = npc_agent
        
        logger.info(f"Added NPC: {npc.name} ({npc.id}) to zone {zone.name}")
    
    def add_object(self, obj: Object, zone_id: str) -> None:
        """Add an object to a zone and create an agent for it"""
        zone = self.world.zones.get(zone_id)
        if not zone:
            raise ValueError(f"Zone {zone_id} not found")
        
        zone.add_object(obj)
        
        # Create object agent
        obj_agent = ObjectAgent(obj.id, obj.name, obj.description)
        self.agents[obj.id] = obj_agent
        
        logger.info(f"Added object: {obj.name} ({obj.id}) to zone {zone.name}")
    
    def add_item(self, item: Item) -> None:
        """Add an item to the world's item registry"""
        self.world.add_item(item)
        logger.info(f"Added item: {item.name} ({item.id})")
    
    def add_player(self, player: Player, zone_id: str) -> None:
        """Add a player to a zone and create an agent for them"""
        zone = self.world.zones.get(zone_id)
        if not zone:
            raise ValueError(f"Zone {zone_id} not found")
        
        zone.add_player(player)
        
        # Create player agent
        player_agent = PlayerAgent(player.id)
        self.agents[player.id] = player_agent
        
        logger.info(f"Added player: {player.name} ({player.id}) to zone {zone.name}")
    
    def connect_zones(self, zone_id1: str, zone_id2: str) -> bool:
        """Connect two zones bidirectionally"""
        return self.world.connect_zones(zone_id1, zone_id2)
    
    async def process_player_input(self, player_id: str, input_text: str) -> Event:
        """Process player input and return the result"""
        # Find player's current zone
        zone = self.world.get_zone_for_player(player_id)
        if not zone:
            return Event(
                type=EventType.MESSAGE,
                content="Error: Player not found in any zone",
                source_id="system",
                target_id=player_id
            )
        
        # Create context
        context = AgentContext(
            world=self.world,
            player_id=player_id,
            zone_id=zone.id
        )
        
        # Get player agent
        if player_id not in self.agents:
            return Event(
                type=EventType.MESSAGE,
                content="Error: No agent for player",
                source_id="system",
                target_id=player_id
            )
        
        player_agent = self.agents[player_id]
        
        # Process the input
        try:
            response = await player_agent.run(input_text, context)
            event = response.event
            
            # Handle the event
            await self.event_handler.handle(event)
            
            return event
        except Exception as e:
            logger.error(f"Error processing player input: {str(e)}")
            return Event(
                type=EventType.MESSAGE,
                content=f"Error: {str(e)}",
                source_id="system",
                target_id=player_id
            )
    
    async def run_game_loop(self) -> None:
        """Run the main game loop"""
        self.running = True
        logger.info("Game loop started")
        
        while self.running:
            # We're keeping things simple, so we won't do anything here for now
            # In a more complex game, you could:
            # - Update NPC behaviors
            # - Trigger random events
            # - Update game time
            
            await asyncio.sleep(1)
    
    def stop(self) -> None:
        """Stop the game loop"""
        self.running = False
        logger.info("Game loop stopped")