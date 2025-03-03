# app/database_seeder.py
import uuid
import logging
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional

from app.database import SessionLocal, engine, Base
from app.models.character import Character, CharacterType
from app.models.subscription import SubscriptionPlan
from app.models.agent import Agent
from app.models.world import World
from app.models.zone import Zone
from app.models.player import Player
from app.models.enums import EntityType
from app.models.object import Object, ObjectType
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

def seed_subscription_plans(db: Session) -> List[SubscriptionPlan]:
    """Create basic subscription plans."""
    existing_plans = db.query(SubscriptionPlan).all()
    if existing_plans:
        logger.info(f"Found {len(existing_plans)} existing subscription plans")
        return existing_plans

    free_plan = SubscriptionPlan(
        name="Free",
        description="Basic access to the platform",
        stripe_price_id="price_free",  # Placeholder
        price_amount=0,
        price_currency="usd",
        interval="month",
        messages_per_day=settings.FREE_MESSAGES_PER_DAY,
        max_conversations=settings.FREE_CONVERSATIONS_LIMIT,
        max_characters=settings.FREE_CHARACTERS_LIMIT,
        can_make_public_characters=False
    )

    premium_plan = SubscriptionPlan(
        name="Premium",
        description="Enhanced access with more characters and worlds",
        stripe_price_id=settings.STRIPE_PREMIUM_PRICE_ID,
        price_amount=999,  # $9.99
        price_currency="usd",
        interval="month",
        messages_per_day=settings.PREMIUM_MESSAGES_PER_DAY,
        max_conversations=settings.PREMIUM_CONVERSATIONS_LIMIT,
        max_characters=settings.PREMIUM_CHARACTERS_LIMIT,
        can_make_public_characters=True
    )

    db.add(free_plan)
    db.add(premium_plan)
    db.commit()

    logger.info("Created subscription plans: Free and Premium")
    return [free_plan, premium_plan]

def seed_admin(db: Session) -> Player:
    """Create an admin user if one doesn't exist."""
    admin = db.query(Player).filter_by(email="admin@example.com").first()
    if admin:
        logger.info("Admin user already exists")
        return admin
    
    admin = Player(
        id=str(uuid.uuid4()),
        email="admin@example.com",
        first_name="Admin",
        last_name="User",
        is_active=True,
        is_admin=True
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    
    logger.info("Created admin user")
    return admin

def seed_worlds(db: Session) -> List[World]:
    """Create a fantasy world."""
    worlds = db.query(World).all()
    if worlds:
        logger.info(f"Found {len(worlds)} existing worlds")
        return worlds
    
    admin = seed_admin(db)
    
    fantasy_world = World(
        name="Fantasy World",
        description="A magical world filled with fantasy creatures and landscapes",
        properties={"theme": "medieval", "magic_level": "high", "genre": "Fantasy"},
        tier=1,
        owner_id=admin.id,
        is_official=True,
        is_private=False
    )
    
    db.add(fantasy_world)
    db.commit()
    db.refresh(fantasy_world)
    
    logger.info(f"Created world: {fantasy_world.name}")
    return [fantasy_world]

def seed_zones(db: Session) -> List[Zone]:
    """Create zones within the fantasy world."""
    zones = db.query(Zone).all()
    if zones:
        logger.info(f"Found {len(zones)} existing zones")
        return zones
    
    world = db.query(World).filter(World.name == "Fantasy World").first()
    if not world:
        logger.error("Fantasy World not found, cannot create zones")
        return []
    
    # Create top-level zones
    enchanted_forest = Zone(
        name="Enchanted Forest",
        description="A magical forest filled with ancient trees and mystical creatures",
        properties={"magic_concentration": "high", "danger_level": "medium"},
        world_id=world.id,
        tier=1
    )
    
    royal_kingdom = Zone(
        name="Royal Kingdom",
        description="The central kingdom with a grand castle and bustling towns",
        properties={"population_density": "high", "technology_level": "medieval"},
        world_id=world.id,
        tier=1
    )
    
    dragon_mountains = Zone(
        name="Dragon Mountains",
        description="Treacherous mountain ranges where dragons make their lairs",
        properties={"elevation": "high", "danger_level": "extreme"},
        world_id=world.id,
        tier=2
    )
    
    # Create and commit top-level zones first
    zones_to_add = [enchanted_forest, royal_kingdom, dragon_mountains]
    for zone in zones_to_add:
        db.add(zone)
    
    db.commit()
    for zone in zones_to_add:
        db.refresh(zone)
    
    # Create sub-zones
    fairy_glade = Zone(
        name="Fairy Glade",
        description="A small clearing where fairies gather",
        properties={"magic_type": "nature", "size": "small"},
        world_id=world.id,
        parent_zone_id=enchanted_forest.id,
        tier=1
    )
    
    ancient_heart = Zone(
        name="Ancient Heart",
        description="The oldest part of the forest with the most ancient trees",
        properties={"age": "ancient", "magic_concentration": "very high"},
        world_id=world.id,
        parent_zone_id=enchanted_forest.id,
        tier=1
    )
    
    # Add and commit sub-zones
    db.add(fairy_glade)
    db.add(ancient_heart)
    db.commit()
    
    # Get all zones and return them
    all_zones = db.query(Zone).all()
    logger.info(f"Created {len(all_zones)} zones")
    return all_zones

def seed_objects(db: Session) -> List[Object]:
    """Create objects in the fantasy world zones."""
    objects = db.query(Object).all()
    if objects:
        logger.info(f"Found {len(objects)} existing objects")
        return objects
    
    # Get zones to place objects in
    enchanted_forest = db.query(Zone).filter(Zone.name == "Enchanted Forest").first()
    royal_kingdom = db.query(Zone).filter(Zone.name == "Royal Kingdom").first()
    fairy_glade = db.query(Zone).filter(Zone.name == "Fairy Glade").first()
    
    if not enchanted_forest or not royal_kingdom or not fairy_glade:
        logger.error("Required zones not found, cannot create objects")
        return []
    
    objects_to_create = [
        # Enchanted Forest objects
        Object(
            name="Ancient Whispering Tree",
            description="A massive, ancient tree whose leaves shimmer with magical energy and whose bark shifts when not observed.",
            zone_id=enchanted_forest.id,
            properties={"magic_type": "nature", "magical_properties": ["healing", "wisdom"]},
            object_type=ObjectType.GENERIC,
            tier=1
        ),
        Object(
            name="Mystic Fountain",
            description="A small fountain carved from luminescent crystal that flows with water glowing in moonlight.",
            zone_id=enchanted_forest.id,
            properties={"magic_type": "water", "magical_properties": ["healing", "clarity"]},
            object_type=ObjectType.GENERIC,
            tier=1
        ),
        
        # Royal Kingdom objects
        Object(
            name="Royal Castle",
            description="A grand castle with towering spires and massive walls, the seat of power for the kingdom.",
            zone_id=royal_kingdom.id,
            properties={"building_type": "castle", "contains_npcs": True},
            object_type=ObjectType.GENERIC,
            tier=1
        ),
        Object(
            name="Grand Market",
            description="A bustling market square with vendors selling exotic foods and rare magical items.",
            zone_id=royal_kingdom.id,
            properties={"building_type": "market", "contains_npcs": True},
            object_type=ObjectType.GENERIC,
            tier=1
        ),
        
        # Fairy Glade objects
        Object(
            name="Fairy Circle",
            description="A perfect circle of mushrooms where fairies dance under moonlight.",
            zone_id=fairy_glade.id,
            properties={"magic_type": "fey", "active_time": "night"},
            object_type=ObjectType.GENERIC,
            tier=1
        ),
        Object(
            name="Wishing Well",
            description="A small well adorned with sparkling crystals that grants wishes to the pure of heart.",
            zone_id=fairy_glade.id,
            properties={"magic_type": "wish", "uses_per_day": 1},
            object_type=ObjectType.GENERIC,
            tier=1
        )
    ]
    
    for obj in objects_to_create:
        db.add(obj)
    
    db.commit()
    
    all_objects = db.query(Object).all()
    logger.info(f"Created {len(all_objects)} objects")
    return all_objects

def seed_agents(db: Session) -> List[Agent]:
    """Create AI agents."""
    agents = db.query(Agent).all()
    if agents:
        logger.info(f"Found {len(agents)} existing agents")
        return agents
    
    agents_to_create = [
        Agent(
            name="Assistant",
            description="A helpful AI assistant that can roleplay as various characters",
            tier=1
        ),
        Agent(
            name="Game Master",
            description="An AI agent that manages quests and narratives",
            tier=2
        ),
        Agent(
            name="Merchant",
            description="An AI agent that manages shops and trading",
            tier=1
        )
    ]
    
    for agent in agents_to_create:
        db.add(agent)
    
    db.commit()
    
    all_agents = db.query(Agent).all()
    logger.info(f"Created {len(all_agents)} agents")
    return all_agents

def seed_agent_characters(db: Session) -> List[Character]:
    """Create agent-controlled characters."""
    agent_characters = db.query(Character).filter(Character.character_type == CharacterType.AGENT).all()
    if agent_characters:
        logger.info(f"Found {len(agent_characters)} existing agent characters")
        return agent_characters
    
    # Get agents
    assistant_agent = db.query(Agent).filter(Agent.name == "Assistant").first()
    gm_agent = db.query(Agent).filter(Agent.name == "Game Master").first()
    merchant_agent = db.query(Agent).filter(Agent.name == "Merchant").first()
    
    if not assistant_agent or not gm_agent or not merchant_agent:
        logger.error("Required agents not found, cannot create agent characters")
        return []
    
    # Get zones
    enchanted_forest = db.query(Zone).filter(Zone.name == "Enchanted Forest").first()
    royal_kingdom = db.query(Zone).filter(Zone.name == "Royal Kingdom").first()
    fairy_glade = db.query(Zone).filter(Zone.name == "Fairy Glade").first()
    
    if not enchanted_forest or not royal_kingdom or not fairy_glade:
        logger.error("Required zones not found, cannot create agent characters")
        return []
    
    characters_to_create = [
        # Assistant agent characters
        Character(
            name="Sir Aldric the Valiant",
            description="A noble and chivalrous paladin devoted to justice, honor, and the protection of the innocent.",
            zone_id=royal_kingdom.id,
            character_type=CharacterType.AGENT,
            agent_id=assistant_agent.id
        ),
        Character(
            name="Selene Nightshade",
            description="A cunning rogue and master of stealth, deception, and quick wit.",
            zone_id=enchanted_forest.id,
            character_type=CharacterType.AGENT,
            agent_id=assistant_agent.id
        ),
        
        # Game Master agent characters
        Character(
            name="Elder Elyndra",
            description="An ancient and wise elven sage who guides adventurers on their quests.",
            zone_id=fairy_glade.id,
            character_type=CharacterType.AGENT,
            agent_id=gm_agent.id
        ),
        
        # Merchant agent characters
        Character(
            name="Thadius Coinpurse",
            description="A jovial merchant with connections throughout the kingdom and a knack for finding rare items.",
            zone_id=royal_kingdom.id,
            character_type=CharacterType.AGENT,
            agent_id=merchant_agent.id
        )
    ]
    
    for character in characters_to_create:
        db.add(character)
    
    db.commit()
    
    all_agent_characters = db.query(Character).filter(Character.character_type == CharacterType.AGENT).all()
    logger.info(f"Created {len(all_agent_characters)} agent characters")
    return all_agent_characters

def seed_database():
    """Seed the database with initial data in a logical order."""
    logger.info("Starting database seeding...")
    db = SessionLocal()
    try:
        Base.metadata.create_all(bind=engine)
        
        # Create data in logical order
        seed_subscription_plans(db)
        worlds = seed_worlds(db)
        zones = seed_zones(db)
        objects = seed_objects(db)
        agents = seed_agents(db)
        agent_characters = seed_agent_characters(db)
        
        logger.info("Database seeding completed successfully")
    except Exception as e:
        logger.error(f"Error seeding database: {str(e)}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    seed_database()