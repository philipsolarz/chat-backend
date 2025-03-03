# app/database_seeder.py
import uuid
from sqlalchemy import func
from sqlalchemy.orm import Session
import logging
from typing import List, Dict, Any

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
    """Seed the database with subscription plans."""
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


def seed_default_agents(db: Session) -> List[Agent]:
    """Seed the database with default AI agents."""
    existing_agents = db.query(Agent).all()
    if existing_agents:
        logger.info(f"Found {len(existing_agents)} existing agents")
        return existing_agents

    default_agent = Agent(
        name="Assistant",
        description="A helpful AI assistant that can roleplay as various characters",
        tier=1
    )

    db.add(default_agent)
    db.commit()

    logger.info("Created default agent: Assistant")
    return [default_agent]


def seed_worlds(db: Session):
    """Seed the database with initial world data."""
    world_count = db.query(func.count(World.id)).scalar() or 0
    if world_count > 0:
        return

    admin = db.query(Player).filter_by(email="admin@example.com").first()
    if not admin:
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

    worlds = [
        World(
            name="Fantasy World",
            description="A magical world filled with fantasy creatures and landscapes",
            properties={"theme": "medieval", "magic_level": "high", "genre": "Fantasy"},
            tier=1,
            owner_id=admin.id,
            is_official=True,
            is_private=False
        ),
        World(
            name="Sci-Fi Universe",
            description="A futuristic universe with advanced technology and space exploration",
            properties={"theme": "futuristic", "technology_level": "advanced", "genre": "Science Fiction", "space_travel": True},
            tier=2,
            owner_id=admin.id,
            is_official=True,
            is_private=False
        ),
        World(
            name="Post-Apocalyptic Wasteland",
            description="A harsh world devastated by nuclear war and environmental collapse",
            properties={"theme": "wasteland", "radiation_level": "high", "genre": "Post-Apocalyptic", "survival_difficulty": "extreme"},
            tier=1,
            owner_id=admin.id,
            is_official=True,
            is_private=False
        )
    ]

    for world in worlds:
        db.add(world)

    db.commit()
    seed_zones(db)


def seed_zones(db: Session):
    """Seed the database with initial zone data."""
    zone_count = db.query(func.count(Zone.id)).scalar() or 0
    if zone_count > 0:
        return

    worlds = db.query(World).all()

    for world in worlds:
        if world.name == "Fantasy World":
            top_level_zones = [
                Zone(
                    name="Enchanted Forest",
                    description="A magical forest filled with ancient trees and mystical creatures",
                    properties={"magic_concentration": "high", "danger_level": "medium"},
                    world_id=world.id,
                    tier=1
                ),
                Zone(
                    name="Royal Kingdom",
                    description="The central kingdom with a grand castle and bustling towns",
                    properties={"population_density": "high", "technology_level": "medieval"},
                    world_id=world.id,
                    tier=1
                ),
                Zone(
                    name="Dragon Mountains",
                    description="Treacherous mountain ranges where dragons make their lairs",
                    properties={"elevation": "high", "danger_level": "extreme"},
                    world_id=world.id,
                    tier=2
                )
            ]

            for zone in top_level_zones:
                db.add(zone)

            db.commit()

            enchanted_forest = db.query(Zone).filter_by(world_id=world.id, name="Enchanted Forest").first()
            if enchanted_forest:
                sub_zones = [
                    Zone(
                        name="Fairy Glade",
                        description="A small clearing where fairies gather",
                        properties={"magic_type": "nature", "size": "small"},
                        world_id=world.id,
                        parent_zone_id=enchanted_forest.id,
                        tier=1
                    ),
                    Zone(
                        name="Ancient Heart",
                        description="The oldest part of the forest with the most ancient trees",
                        properties={"age": "ancient", "magic_concentration": "very high"},
                        world_id=world.id,
                        parent_zone_id=enchanted_forest.id,
                        tier=1
                    )
                ]
                for zone in sub_zones:
                    db.add(zone)

        elif world.name == "Sci-Fi Universe":
            top_level_zones = [
                Zone(
                    name="Alpha Space Station",
                    description="A massive space station serving as a hub for interstellar travel",
                    properties={"gravity": "artificial", "population": 50000},
                    world_id=world.id,
                    tier=2
                ),
                Zone(
                    name="New Earth Colony",
                    description="A terraformed planet with the largest human colony outside Earth",
                    properties={"atmosphere": "terraformed", "population": 10000000},
                    world_id=world.id,
                    tier=2
                ),
                Zone(
                    name="Asteroid Mining Belt",
                    description="A dangerous area of space filled with valuable mineral-rich asteroids",
                    properties={"resources": "abundant", "danger_level": "high"},
                    world_id=world.id,
                    tier=1
                )
            ]
            for zone in top_level_zones:
                db.add(zone)

        elif world.name == "Post-Apocalyptic Wasteland":
            top_level_zones = [
                Zone(
                    name="Last City",
                    description="The last major human settlement with high walls and strict rules",
                    properties={"security": "maximum", "resources": "limited"},
                    world_id=world.id,
                    tier=1
                ),
                Zone(
                    name="Radiation Zone",
                    description="A highly irradiated area filled with mutated creatures",
                    properties={"radiation": "extreme", "mutation_risk": "high"},
                    world_id=world.id,
                    tier=1
                ),
                Zone(
                    name="Abandoned Metropolis",
                    description="The ruins of a once-great city, now home to scavengers and dangers",
                    properties={"loot_quality": "high", "structural_integrity": "low"},
                    world_id=world.id,
                    tier=1
                )
            ]
            for zone in top_level_zones:
                db.add(zone)

    db.commit()


def seed_character_templates(db: Session) -> List[Character]:
    """Seed the database with character templates."""
    template_characters = db.query(Character).filter(Character.description.like("%template%")).all()
    if template_characters:
        logger.info(f"Found {len(template_characters)} existing character templates")
        return template_characters

    # Use a valid zone for the templates. We'll try to use "Enchanted Forest" from Fantasy World.
    zone = db.query(Zone).filter(Zone.name == "Enchanted Forest").first()
    if not zone:
        raise Exception("No valid zone found for seeding character templates.")
    zone_id = zone.id

    # Create Characters directly (joined inheritance will create an entry in entities)
    paladin = Character(
        name="Sir Aldric the Valiant",
        description="A noble and chivalrous paladin devoted to justice, honor, and the protection of the innocent. (template)",
        zone_id=zone_id,
        properties={"is_template": True},
        character_type=CharacterType.PLAYER,
        # tier=1
    )
    rogue = Character(
        name="Selene Nightshade",
        description="A cunning rogue and master of stealth, deception, and quick wit. (template)",
        zone_id=zone_id,
        properties={"is_template": True},
        character_type=CharacterType.PLAYER,
        # tier=1
    )
    mage = Character(
        name="Thorne Spellweaver",
        description="An eccentric and brilliant arcane mage with vast knowledge of the magical arts. (template)",
        zone_id=zone_id,
        properties={"is_template": True},
        character_type=CharacterType.PLAYER,
        # tier=1
    )
    barbarian = Character(
        name="Krag Skullcrusher",
        description="A mighty barbarian warrior from the northern mountains. (template)",
        zone_id=zone_id,
        properties={"is_template": True},
        character_type=CharacterType.PLAYER,
        # tier=1
    )

    templates = [paladin, rogue, mage, barbarian]
    for template in templates:
        db.add(template)

    db.commit()
    logger.info(f"Created {len(templates)} character templates")
    return templates


def seed_starter_objects(db: Session) -> List[Object]:
    """Seed the database with starter objects for the zones."""
    existing_objects = db.query(Object).all()
    if existing_objects:
        logger.info(f"Found {len(existing_objects)} existing objects")
        return existing_objects

    world = db.query(World).filter(World.name == "Fantasy World").first()
    if not world:
        logger.info("Fantasy World not found, skipping object creation")
        return []

    enchanted_forest = db.query(Zone).filter(Zone.name == "Enchanted Forest", Zone.world_id == world.id).first()
    royal_kingdom = db.query(Zone).filter(Zone.name == "Royal Kingdom", Zone.world_id == world.id).first()
    if not enchanted_forest or not royal_kingdom:
        logger.info("Required zones not found, skipping object creation")
        return []

    # Create starter objects directly.
    magical_tree = Object(
        name="Ancient Whispering Tree",
        description="A massive, ancient tree whose leaves shimmer with magical energy and whose bark shifts when not observed.",
        zone_id=enchanted_forest.id,
        properties={"magic_type": "nature", "magical_properties": ["healing", "wisdom"]},
        object_type=ObjectType.GENERIC,
        tier=1
    )
    fountain = Object(
        name="Mystic Fountain",
        description="A small fountain carved from luminescent crystal that flows with water glowing in moonlight.",
        zone_id=enchanted_forest.id,
        properties={"magic_type": "water", "magical_properties": ["healing", "clarity"]},
        object_type=ObjectType.GENERIC,
        tier=1
    )
    castle = Object(
        name="Royal Castle",
        description="A grand castle with towering spires and massive walls, the seat of power for the kingdom.",
        zone_id=royal_kingdom.id,
        properties={"building_type": "castle", "contains_npcs": True},
        object_type=ObjectType.GENERIC,
        tier=1
    )
    market = Object(
        name="Grand Market",
        description="A bustling market square with vendors selling exotic foods and rare magical items.",
        zone_id=royal_kingdom.id,
        properties={"building_type": "market", "contains_npcs": True},
        object_type=ObjectType.GENERIC,
        tier=1
    )

    objects = [magical_tree, fountain, castle, market]
    for obj in objects:
        db.add(obj)

    db.commit()
    logger.info(f"Created {len(objects)} starter objects")
    return objects


def seed_database():
    """Seed the database with initial data."""
    logger.info("Starting database seeding...")
    db = SessionLocal()
    try:
        Base.metadata.create_all(bind=engine)
        seed_subscription_plans(db)
        seed_default_agents(db)
        seed_worlds(db)
        seed_zones(db)
        seed_character_templates(db)
        seed_starter_objects(db)
        logger.info("Database seeding completed successfully")
    except Exception as e:
        logger.error(f"Error seeding database: {str(e)}")
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    seed_database()
