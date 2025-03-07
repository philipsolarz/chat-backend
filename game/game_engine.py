"""
Revised game engine for the Agentique Game Engine with GameMaster architecture.

This module provides a game engine that uses the revised agent system with:
- World Manager: Manages the game world state
- Agent Manager: Manages AI agents and the GameMaster
- Event Bus: Handles game events
- Game Loop: Manages game ticks and autonomous behavior
"""
import asyncio
import logging
import random
from typing import Dict, List, Optional, Any, Callable, Awaitable, Set, Tuple
from datetime import datetime

from base_models import (
    World, Zone, Character, Object, Item, Event, EventType, ControllerType
)

from agent_system import (
    AgentContext, GameMasterContext, BaseAgent, CharacterAgent, ZoneAgent, 
    ObjectAgent, GameMasterAgent, AgentFactory, AgentType
)

from event_system import EventBus

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agentique.engine")

class WorldManager:
    """
    Manages the game world and its entities.
    
    This class is responsible for:
    - Creating and managing the game world
    - Adding/removing zones, characters, objects
    - Processing game state changes
    """
    
    def __init__(self, event_bus: EventBus):
        self.world = World(name="Game World", description="A default game world")
        self.event_bus = event_bus
    
    def create_world(self, name: str, description: str) -> World:
        """Create a new game world"""
        self.world = World(name=name, description=description)
        return self.world
    
    def get_world(self) -> World:
        """Get the current world state"""
        return self.world
    
    def add_zone(self, zone: Zone) -> None:
        """Add a zone to the world"""
        self.world.add_zone(zone)
        logger.info(f"Added zone: {zone.name} ({zone.id})")
    
    def add_character(self, character: Character, zone_id: str) -> None:
        """Add a character to a zone"""
        zone = self.world.zones.get(zone_id)
        if not zone:
            raise ValueError(f"Zone {zone_id} not found")
        
        zone.add_character(character)
        logger.info(f"Added character: {character.name} ({character.id}) to zone {zone.name}")
    
    def add_object(self, obj: Object, zone_id: str) -> None:
        """Add an object to a zone"""
        zone = self.world.zones.get(zone_id)
        if not zone:
            raise ValueError(f"Zone {zone_id} not found")
        
        zone.add_object(obj)
        logger.info(f"Added object: {obj.name} ({obj.id}) to zone {zone.name}")
    
    def add_item(self, item: Item) -> None:
        """Add an item to the world's item registry"""
        self.world.add_item(item)
        logger.info(f"Added item: {item.name} ({item.id})")
    
    def connect_zones(self, zone_id1: str, zone_id2: str) -> bool:
        """Connect two zones bidirectionally"""
        success = self.world.connect_zones(zone_id1, zone_id2)
        if success:
            logger.info(f"Connected zones: {zone_id1} <-> {zone_id2}")
        return success
    
    def disconnect_zones(self, zone_id1: str, zone_id2: str) -> bool:
        """Disconnect two zones"""
        success = self.world.disconnect_zones(zone_id1, zone_id2)
        if success:
            logger.info(f"Disconnected zones: {zone_id1} <-> {zone_id2}")
        return success
    
    def move_character(self, character_id: str, from_zone_id: str, to_zone_id: str) -> bool:
        """Move a character from one zone to another"""
        success = self.world.move_character(character_id, from_zone_id, to_zone_id)
        if success:
            logger.info(f"Moved character {character_id} from {from_zone_id} to {to_zone_id}")
        return success
    
    def set_character_controller(self, character_id: str, controller_type: ControllerType) -> bool:
        """Change a character's controller type"""
        character = self.world.get_character_by_id(character_id)
        if not character:
            return False
        
        old_type = character.controller_type
        character.set_controller(controller_type)
        logger.info(f"Changed character {character.name} ({character_id}) controller from {old_type} to {controller_type}")
        return True
    
    def get_character_location(self, character_id: str) -> Optional[Zone]:
        """Get the zone a character is in"""
        return self.world.get_character_location(character_id)
    
    def tick(self, time_units: float = 1.0) -> None:
        """Advance the world time and update state"""
        self.world.advance_time(time_units)

class AgentManager:
    """
    Manages AI agents for game entities and the GameMaster.
    
    This class is responsible for:
    - Creating and managing agents for entities
    - Running agents to process input and generate responses
    - Using the GameMaster to convert string responses to events
    """
    
    def __init__(self, world_manager: WorldManager, event_bus: EventBus):
        self.world_manager = world_manager
        self.event_bus = event_bus
        self.agents: Dict[str, BaseAgent] = {}
        
        # Create the GameMaster agent
        self.game_master = AgentFactory.create_game_master()
        
        # Model selection strategy - default to using smaller models
        # for less critical agents to save resources
        self.default_model = "openai:gpt-4o-mini"
        self.character_model = "openai:gpt-4o-mini"
        self.zone_model = "openai:gpt-4o-mini"
        self.object_model = "openai:gpt-4o-mini"
    
    def create_agents_for_world(self) -> None:
        """Create agents for all entities in the world"""
        world = self.world_manager.get_world()
        
        # Create agents for all zones
        for zone_id, zone in world.zones.items():
            self.create_zone_agent(zone)
        
        # Create agents for all objects
        for zone in world.zones.values():
            for obj_id, obj in zone.objects.items():
                self.create_object_agent(obj)
        
        # Create agents for all AI-controlled characters
        for zone in world.zones.values():
            for char_id, char in zone.characters.items():
                if char.controller_type == "AI":
                    self.create_character_agent(char)
                elif char.controller_type == "PLAYER":
                    # For player characters, create an interpreter
                    self.create_character_interpreter(char)
    
    def create_zone_agent(self, zone: Zone) -> ZoneAgent:
        """Create an agent for a zone"""
        agent = AgentFactory.create_zone_agent(zone, model_name=self.zone_model)
        self.agents[agent.id] = agent
        logger.info(f"Created zone agent for {zone.name} ({zone.id})")
        return agent
    
    def create_object_agent(self, obj: Object) -> ObjectAgent:
        """Create an agent for an object"""
        agent = AgentFactory.create_object_agent(obj, model_name=self.object_model)
        self.agents[agent.id] = agent
        logger.info(f"Created object agent for {obj.name} ({obj.id})")
        return agent
    
    def create_character_agent(self, character: Character) -> CharacterAgent:
        """Create an agent for an AI-controlled character"""
        agent = AgentFactory.create_character_agent(
            character, is_interpreter=False, model_name=self.character_model
        )
        self.agents[agent.id] = agent
        logger.info(f"Created character agent for {character.name} ({character.id})")
        return agent
    
    def create_character_interpreter(self, character: Character) -> CharacterAgent:
        """Create a command interpreter for a player-controlled character"""
        agent = AgentFactory.create_character_agent(
            character, is_interpreter=True, model_name=self.character_model
        )
        # Special ID format for interpreters
        interpreter_id = f"interpreter_{character.id}"
        self.agents[interpreter_id] = agent
        logger.info(f"Created interpreter for {character.name} ({character.id})")
        return agent
    
    def get_agent_for_entity(self, entity_id: str, is_interpreter: bool = False) -> Optional[BaseAgent]:
        """Get an agent for an entity"""
        # For interpreters, look for the special interpreter ID
        if is_interpreter:
            interpreter_id = f"interpreter_{entity_id}"
            return self.agents.get(interpreter_id)
        
        # Otherwise, search through all agents for those controlling this entity
        matching_agents = [
            agent for agent in self.agents.values() 
            if agent.entity_id == entity_id
        ]
        
        if matching_agents:
            return matching_agents[0]
        
        return None
    
    async def _run_agent_and_interpret(
        self, 
        agent: BaseAgent, 
        message: str, 
        agent_context: AgentContext,
        game_master_context: GameMasterContext
    ) -> Event:
        """Run an agent and interpret its response with the GameMaster"""
        # Run the agent to get a string response
        response_str = await agent.run(message, agent_context)
        
        # Use the GameMaster to interpret the response
        event = await self.game_master.interpret(response_str, game_master_context)
        
        return event
    
    async def process_character_input(self, character_id: str, input_text: str) -> Event:
        """Process input for a player-controlled character"""
        # Get the character and their location
        character = self.world_manager.get_world().get_character_by_id(character_id)
        if not character:
            return Event(
                type=EventType.MESSAGE,
                content="Error: Character not found",
                source_id="system",
                target_id=character_id
            )
        
        zone = self.world_manager.get_character_location(character_id)
        if not zone:
            return Event(
                type=EventType.MESSAGE,
                content="Error: Character not in any zone",
                source_id="system",
                target_id=character_id
            )
        
        # Get the interpreter agent
        interpreter = self.get_agent_for_entity(character_id, is_interpreter=True)
        if not interpreter:
            return Event(
                type=EventType.MESSAGE,
                content="Error: No interpreter for character",
                source_id="system",
                target_id=character_id
            )
        
        # Create agent context
        agent_context = AgentContext(
            world=self.world_manager.get_world(),
            character_id=character_id,
            zone_id=zone.id
        )
        
        # Create GameMaster context
        gm_context = GameMasterContext(
            world=self.world_manager.get_world(),
            character_id=character_id,
            zone_id=zone.id,
            agent_type=AgentType.CHARACTER,
            action_type="interpreter"
        )
        
        try:
            # Run the interpreter and interpret the response
            event = await self._run_agent_and_interpret(
                interpreter, input_text, agent_context, gm_context
            )
            
            # Process the event (handle special cases like look, move, etc.)
            event = await self._process_interpreter_event(event)
            
            # Publish the event
            await self.event_bus.publish(event)
            
            return event
        except Exception as e:
            logger.error(f"Error processing character input: {str(e)}")
            return Event(
                type=EventType.MESSAGE,
                content=f"Error: {str(e)}",
                source_id="system",
                target_id=character_id
            )
    
    async def _process_interpreter_event(self, event: Event) -> Event:
        """Process an event from an interpreter agent to handle special cases"""
        # Get the world and character
        world = self.world_manager.get_world()
        character_id = event.source_id
        character = world.get_character_by_id(character_id)
        
        if not character:
            return event
        
        # Get the character's location
        zone = self.world_manager.get_character_location(character_id)
        if not zone:
            return event
        
        # Handle special actions based on metadata
        if "action" in event.metadata:
            action = event.metadata["action"]
            
            # Look action: get zone description
            if action == "look":
                zone_agent = self.get_agent_for_entity(zone.id)
                if zone_agent:
                    # Create contexts
                    agent_context = AgentContext(
                        world=world,
                        character_id=character_id,
                        zone_id=zone.id
                    )
                    
                    gm_context = GameMasterContext(
                        world=world,
                        character_id=zone.id,
                        zone_id=zone.id,
                        agent_type=AgentType.ZONE
                    )
                    
                    # Get zone description
                    look_prompt = "Describe this location to a character who just arrived or is looking around."
                    zone_event = await self._run_agent_and_interpret(
                        zone_agent, look_prompt, agent_context, gm_context
                    )
                    
                    # Preserve the event type but use the zone description
                    event.content = zone_event.content
                    event.source_id = zone.id
            
            # Move action: move character and get new zone description
            elif action == "move":
                destination_name = event.metadata.get("destination", "")
                if destination_name:
                    # Find the destination zone by name
                    destination_zone_id = None
                    for zone_id in zone.connected_zones:
                        if zone_id in world.zones:
                            dest_zone = world.zones[zone_id]
                            if destination_name.lower() in dest_zone.name.lower():
                                destination_zone_id = zone_id
                                break
                    
                    if destination_zone_id:
                        # Move the character
                        success = self.world_manager.move_character(
                            character_id, zone.id, destination_zone_id
                        )
                        
                        if success:
                            # Update event properties
                            event.target_id = destination_zone_id
                            event.content = f"You move to {world.zones[destination_zone_id].name}."
                            event.metadata["from_zone"] = zone.id
                            event.metadata["to_zone"] = destination_zone_id
                            
                            # Will trigger look at the new zone via movement handler
                        else:
                            event.type = EventType.MESSAGE
                            event.content = f"You can't go to {destination_name} from here."
                    else:
                        event.type = EventType.MESSAGE
                        event.content = f"You don't see a way to {destination_name} from here."
            
            # Talk action: find target character
            elif action == "talk":
                target_name = event.metadata.get("target_name", "")
                if target_name:
                    # Find the target character by name
                    target_character = None
                    for char_id, char in zone.characters.items():
                        if char_id != character_id and target_name.lower() in char.name.lower():
                            target_character = char
                            event.target_id = char_id
                            break
                    
                    if not target_character:
                        event.type = EventType.MESSAGE
                        event.content = f"You don't see anyone named '{target_name}' here."
            
            # Examine action: find target object
            elif action == "examine":
                object_name = event.metadata.get("object_name", "")
                if object_name:
                    # Find the target object by name
                    target_object = None
                    target_object_id = None
                    
                    for obj_id, obj in zone.objects.items():
                        if object_name.lower() in obj.name.lower():
                            target_object = obj
                            target_object_id = obj_id
                            break
                    
                    if target_object:
                        # Get object agent response
                        object_agent = self.get_agent_for_entity(target_object_id)
                        if object_agent:
                            # Create contexts
                            agent_context = AgentContext(
                                world=world,
                                character_id=character_id,
                                zone_id=zone.id
                            )
                            
                            gm_context = GameMasterContext(
                                world=world,
                                character_id=target_object_id,
                                zone_id=zone.id,
                                agent_type=AgentType.OBJECT,
                                target_id=character_id
                            )
                            
                            # Get object description
                            examine_prompt = f"A character is examining you. Describe what they see and experience."
                            obj_event = await self._run_agent_and_interpret(
                                object_agent, examine_prompt, agent_context, gm_context
                            )
                            
                            # Update the event
                            event.content = obj_event.content
                            event.target_id = target_object_id
                            
                            # Record the interaction
                            target_object.record_interaction(character_id, "examine")
                        else:
                            # No agent, use default description
                            event.content = f"You examine the {target_object.name}: {target_object.description}"
                            event.target_id = target_object_id
                    else:
                        event.type = EventType.MESSAGE
                        event.content = f"You don't see any '{object_name}' here to examine."
            
            # Inventory action: format inventory
            elif action == "inventory":
                if character.inventory.items:
                    inventory_list = []
                    for item_id, quantity in character.inventory.items.items():
                        item = world.get_item(item_id)
                        if item:
                            inventory_list.append(f"{item.name} ({quantity})")
                    
                    inventory_text = "Inventory:\n" + "\n".join(inventory_list)
                    event.content = inventory_text
                else:
                    event.content = "Your inventory is empty."
        
        return event
    
    async def process_ai_action(self, character_id: str) -> Optional[Event]:
        """Generate an autonomous action for an AI-controlled character"""
        # Get the character and their location
        character = self.world_manager.get_world().get_character_by_id(character_id)
        if not character or character.controller_type != "AI":
            return None
        
        zone = self.world_manager.get_character_location(character_id)
        if not zone:
            return None
        
        # Get the character agent
        agent = self.get_agent_for_entity(character_id)
        if not agent:
            return None
        
        # Create agent context
        agent_context = AgentContext(
            world=self.world_manager.get_world(),
            character_id=character_id,
            zone_id=zone.id
        )
        
        # Choose a randomly weighted action type
        action_types = [
            (70, "idle"),  # Most of the time, do nothing
            (20, "examine"),  # Sometimes examine objects
            (10, "talk")   # Occasionally talk to other characters
        ]
        
        action_type = random.choices(
            [a[1] for a in action_types],
            weights=[a[0] for a in action_types],
            k=1
        )[0]
        
        # Try to generate an action based on the chosen type
        try:
            # Get nearby characters (excluding self)
            nearby_characters = [
                char for char_id, char in zone.characters.items() 
                if char_id != character_id
            ]
            
            # Skip if the action requires other characters but none are present
            if action_type == "talk" and not nearby_characters:
                return None
                
            # Skip if the action requires objects but none are present
            if action_type == "examine" and not zone.objects:
                return None
                
            # Create appropriate prompt based on action type
            if action_type == "talk":
                # Pick a random character to talk to
                target = random.choice(nearby_characters)
                
                # Create GameMaster context
                gm_context = GameMasterContext(
                    world=self.world_manager.get_world(),
                    character_id=character_id,
                    zone_id=zone.id,
                    agent_type=AgentType.CHARACTER,
                    action_type="talk",
                    target_id=target.id
                )
                
                # Create a context-rich prompt
                recent_dialogues = []
                for entry in character.get_recent_dialogue(5):
                    if entry["speaker_id"] == target.id:
                        recent_dialogues.append(f"{target.name} said: \"{entry['content']}\"")
                
                # Build a more detailed prompt with context
                prompt = f"""
                You are in {zone.name}. {target.name} is here with you.
                
                {target.description}
                
                """
                
                # Add any recent dialogue context
                if recent_dialogues:
                    prompt += "Recent conversation:\n" + "\n".join(recent_dialogues) + "\n\n"
                
                # Add the actual prompt question
                prompt += f"What would you say to {target.name} right now? Respond in character."
                
                # Run the agent and interpret the response
                event = await self._run_agent_and_interpret(
                    agent, prompt, agent_context, gm_context
                )
                
                # Update the event
                event.type = EventType.DIALOGUE
                event.target_id = target.id
                
                # Record the dialogue
                character.add_dialogue(character_id, event.content)
                target.add_dialogue(character_id, event.content)
                
                # Publish the event
                await self.event_bus.publish(event)
                return event
                
            elif action_type == "examine":
                # Pick a random object to examine
                target_id, target = random.choice(list(zone.objects.items()))
                
                # Create GameMaster context
                gm_context = GameMasterContext(
                    world=self.world_manager.get_world(),
                    character_id=character_id,
                    zone_id=zone.id,
                    agent_type=AgentType.CHARACTER,
                    action_type="examine",
                    target_id=target_id
                )
                
                # Build a more detailed prompt with context
                prompt = f"""
                You are in {zone.name} and notice {target.name}.
                
                {target.description}
                
                What thoughts or observations does your character have about this {target.name}?
                Respond with just your character's internal thoughts.
                """
                
                # Run the agent and interpret the response
                event = await self._run_agent_and_interpret(
                    agent, prompt, agent_context, gm_context
                )
                
                # Update the event
                event.type = EventType.INTERACTION
                event.target_id = target_id
                
                # Record the interaction
                target.record_interaction(character_id, "examine")
                
                # Publish the event
                await self.event_bus.publish(event)
                return event
            
            return None
            
        except Exception as e:
            logger.error(f"Error generating AI action: {str(e)}")
            return None

class GameEngine:
    """
    Main game engine that coordinates all components and manages the game loop.
    """
    
    def __init__(self):
        # Create the event bus first
        self.event_bus = EventBus()
        
        # Create managers
        self.world_manager = WorldManager(self.event_bus)
        self.agent_manager = AgentManager(self.world_manager, self.event_bus)
        
        # Game loop state
        self.running = False
        self.tick_interval = 5.0  # Seconds between game ticks
        self.ai_action_interval = 60.0  # Seconds between AI character actions
        self.last_ai_action_time = 0.0
        
        # Setup default event handlers
        self._setup_event_handlers()
    
    def _setup_event_handlers(self) -> None:
        """Set up default event handlers"""
        
        # Log all events
        async def log_event(event: Event) -> None:
            logger.debug(f"EVENT: {event.type} - From: {event.source_id}, To: {event.target_id}")
            logger.debug(f"Content: {event.content}")
        
        self.event_bus.subscribe(None, log_event)
        
        # Handle movement events
        async def handle_movement(event: Event) -> None:
            if event.type != EventType.MOVEMENT:
                return
            
            # The metadata should contain from_zone and to_zone
            from_zone_id = event.metadata.get("from_zone")
            to_zone_id = event.metadata.get("to_zone")
            
            if not from_zone_id or not to_zone_id:
                return
            
            # Character has already been moved in the move() tool, but we can do other tasks
            # For example, we could automatically describe the new zone
            
            # Create context for describing the new zone
            character_id = event.source_id
            
            if not character_id or to_zone_id not in self.world_manager.get_world().zones:
                return
            
            # Check if this is a player character
            character = self.world_manager.get_world().get_character_by_id(character_id)
            if not character or not character.is_player_controlled():
                return
            
            # Create a look event to describe the new zone
            look_event = Event(
                type=EventType.MESSAGE,
                content="You look around...",
                source_id=character_id,
                target_id=character_id,
                metadata={"action": "look"}
            )
            
            # Process the look event
            processed_event = await self.agent_manager._process_interpreter_event(look_event)
            
            # Publish the processed event
            await self.event_bus.publish(processed_event)
        
        self.event_bus.subscribe(EventType.MOVEMENT, handle_movement)
        
        # Handle dialogue events
        async def handle_dialogue(event: Event) -> None:
            if event.type != EventType.DIALOGUE:
                return
            
            # Make sure we have valid source and target
            if not event.source_id or not event.target_id:
                return
            
            # Get the source and target characters
            source_char = self.world_manager.get_world().get_character_by_id(event.source_id)
            target_char = self.world_manager.get_world().get_character_by_id(event.target_id)
            
            if not source_char or not target_char:
                return
            
            # Check if they're in the same zone
            source_zone = self.world_manager.get_character_location(event.source_id)
            target_zone = self.world_manager.get_character_location(event.target_id)
            
            if not source_zone or not target_zone or source_zone.id != target_zone.id:
                # Characters not in the same zone
                await self.event_bus.publish(Event(
                    type=EventType.MESSAGE,
                    content="You can't talk to someone who isn't here.",
                    source_id="system",
                    target_id=event.source_id
                ))
                return
            
            # Record the dialogue in both characters' histories
            source_char.add_dialogue(event.source_id, event.content)
            target_char.add_dialogue(event.source_id, event.content)
            
            # If the target is AI controlled, generate a response
            if target_char.controller_type == "AI":
                # Get the target character's agent
                agent = self.agent_manager.get_agent_for_entity(event.target_id)
                if not agent:
                    return
                
                # Create contexts
                agent_context = AgentContext(
                    world=self.world_manager.get_world(),
                    character_id=event.target_id,
                    zone_id=source_zone.id
                )
                
                gm_context = GameMasterContext(
                    world=self.world_manager.get_world(),
                    character_id=event.target_id,
                    zone_id=source_zone.id,
                    agent_type=AgentType.CHARACTER,
                    action_type="respond",
                    target_id=event.source_id
                )
                
                # Generate a response
                try:
                    prompt = f"{source_char.name} says to you: \"{event.content}\". How do you respond?"
                    
                    # Run the agent and interpret the response
                    response_event = await self.agent_manager._run_agent_and_interpret(
                        agent, prompt, agent_context, gm_context
                    )
                    
                    # Set the correct source and target
                    response_event.type = EventType.DIALOGUE
                    response_event.source_id = event.target_id
                    response_event.target_id = event.source_id
                    
                    # Record the dialogue
                    target_char.add_dialogue(event.target_id, response_event.content)
                    source_char.add_dialogue(event.target_id, response_event.content)
                    
                    # Publish the response
                    await self.event_bus.publish(response_event)
                except Exception as e:
                    logger.error(f"Error getting character response: {str(e)}")
        
        self.event_bus.subscribe(EventType.DIALOGUE, handle_dialogue)
    
    async def setup_world(self, world_creator: Callable[[], Awaitable[Tuple[World, List[Character]]]]) -> List[str]:
        """
        Set up the game world using a creator function.
        
        Args:
            world_creator: Async function that creates and returns a world and player characters
            
        Returns:
            List of player character IDs
        """
        try:
            # Call the creator function
            world, player_characters = await world_creator()
            
            # Set the world
            self.world_manager.world = world
            
            # Create agents for all entities
            self.agent_manager.create_agents_for_world()
            
            return [char.id for char in player_characters]
        except Exception as e:
            logger.error(f"Error setting up world: {str(e)}")
            raise
    
    async def process_character_input(self, character_id: str, input_text: str) -> Event:
        """Process input from a player character"""
        return await self.agent_manager.process_character_input(character_id, input_text)
    
    async def update_ai_characters(self) -> None:
        """Update all AI-controlled characters"""
        # Check if it's time to update AI characters
        current_time = self.world_manager.get_world().global_time
        if current_time - self.last_ai_action_time < self.ai_action_interval:
            return
        
        # Get all AI-controlled characters
        ai_characters = [
            char for char in self.world_manager.get_world().get_all_characters()
            if char.controller_type == "AI"
        ]
        
        # Shuffle to avoid always updating in the same order
        random.shuffle(ai_characters)
        
        # Process a random subset of characters
        max_updates = min(3, len(ai_characters))
        for i in range(max_updates):
            if i < len(ai_characters):
                await self.agent_manager.process_ai_action(ai_characters[i].id)
        
        # Update last action time
        self.last_ai_action_time = current_time
    
    async def game_tick(self) -> None:
        """Perform a single game tick"""
        # Advance world time
        self.world_manager.tick()
        
        # Update AI characters
        await self.update_ai_characters()
        
        # Publish a tick event
        await self.event_bus.publish(Event(
            type=EventType.TICK,
            content=f"Game tick: {self.world_manager.get_world().global_time}",
            source_id="system"
        ))
    
    async def run_game_loop(self) -> None:
        """Run the main game loop"""
        self.running = True
        logger.info("Game loop started")
        
        try:
            while self.running:
                # Perform a game tick
                await self.game_tick()
                
                # Wait for the next tick
                await asyncio.sleep(self.tick_interval)
        except asyncio.CancelledError:
            logger.info("Game loop cancelled")
            self.running = False
        except Exception as e:
            logger.error(f"Error in game loop: {str(e)}")
            self.running = False
        finally:
            logger.info("Game loop ended")
    
    def stop(self) -> None:
        """Stop the game loop"""
        self.running = False
        logger.info("Game loop stopping")