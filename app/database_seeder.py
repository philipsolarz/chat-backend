# app/database_seeder.py
import uuid
from sqlalchemy import func
from sqlalchemy.orm import Session
import logging
from typing import List, Dict, Any, Optional

from app.database import SessionLocal, engine, Base
from app.models.character import Character, CharacterType
from app.models.subscription import SubscriptionPlan
from app.models.agent import Agent
from app.models.world import World
from app.models.zone import Zone
from app.models.player import Player
from app.models.entity import Entity, EntityType
from app.models.object import Object, ObjectType
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def seed_subscription_plans(db: Session) -> List[SubscriptionPlan]:
    """Seed the database with subscription plans"""
    
    # Check if plans already exist
    existing_plans = db.query(SubscriptionPlan).all()
    if existing_plans:
        logger.info(f"Found {len(existing_plans)} existing subscription plans")
        return existing_plans
    
    # Create subscription plans
    free_plan = SubscriptionPlan(
        name="Free",
        description="Basic access to the platform",
        stripe_price_id="price_free",  # Placeholder, not used for payments
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
    
    # Add plans to database
    db.add(free_plan)
    db.add(premium_plan)
    db.commit()
    
    logger.info("Created subscription plans: Free and Premium")
    return [free_plan, premium_plan]


def seed_default_agents(db: Session) -> List[Agent]:
    """Seed the database with default AI agents"""
    
    # Check if agents already exist
    existing_agents = db.query(Agent).all()
    if existing_agents:
        logger.info(f"Found {len(existing_agents)} existing agents")
        return existing_agents
    
    # First create an entity for the agent
    # default_agent_entity = Entity(
    #     name="Assistant",
    #     description="A helpful AI assistant that can roleplay as various characters",
    #     type=EntityType.AGENT,
    #     tier=1
    # )
    
    # db.add(default_agent_entity)
    # db.flush()  # Get the ID without fully committing
    
    # Create default agent
    default_agent = Agent(
        name="Assistant",
        description="A helpful AI assistant that can roleplay as various characters",
        # system_prompt=(
        #     "You are a helpful AI assistant participating in a conversation. "
        #     "You will be assigned a character to roleplay as, with a specific name and personality. "
        #     "Stay in character at all times, responding as your assigned character would. "
        #     "Be attentive and engaging, keeping your responses appropriate for the context of the conversation."
        # ),
        # is_active=True,
        # entity_id=default_agent_entity.id,
        tier=1
    )
    
    # Add agent to database
    db.add(default_agent)
    db.commit()
    
    logger.info("Created default agent: Assistant")
    return [default_agent]


def seed_character_templates(db: Session) -> List[Character]:
    """Seed the database with character templates"""
    
    # Check if templates already exist - checking for template-like data in properties
    template_characters = db.query(Character).filter(Character.description.like("%template%")).all()
    if template_characters:
        logger.info(f"Found {len(template_characters)} existing character templates")
        return template_characters
    
    # Create character templates
    templates = []
    
    # Create entities first
    paladin_entity = Entity(
        name="Sir Aldric the Valiant",
        description="A noble and chivalrous paladin devoted to justice, honor, and the protection of the innocent.",
        type=EntityType.CHARACTER,
        # tier=1
    )
    
    rogue_entity = Entity(
        name="Selene Nightshade",
        description="A cunning rogue and master of stealth, deception, and quick wit.",
        type=EntityType.CHARACTER,
        # tier=1
    )
    
    mage_entity = Entity(
        name="Thorne Spellweaver",
        description="An eccentric and brilliant arcane mage with vast knowledge of the magical arts.",
        type=EntityType.CHARACTER,
        # tier=1
    )
    
    barbarian_entity = Entity(
        name="Krag Skullcrusher",
        description="A mighty barbarian warrior from the northern mountains.",
        type=EntityType.CHARACTER,
        # tier=1
    )
    
    # Add entities to db to get IDs
    db.add_all([paladin_entity, rogue_entity, mage_entity, barbarian_entity])
    db.flush()
    
    # Paladin template
    paladin_template = """
You are Sir Aldric the Valiant, a noble and chivalrous paladin devoted to justice, honor, and the protection of the innocent. You uphold the highest ideals of righteousness, always speaking with eloquence, wisdom, and unwavering morality. Your speech is formal, respectful, and infused with a sense of duty and virtue.

### Role and Speech Guidelines:
- **Chivalrous and Honorable** – Always uphold justice and fairness, treating all with respect.
- **Eloquent and Formal** – Use structured, knightly speech with words like 'honor,' 'valiant,' 'forsooth,' and 'henceforth.'
- **Protective and Wise** – Offer guidance, encouragement, and strategic thinking in battle.
- **Humble but Resolute** – Avoid arrogance but stand firm in your beliefs.

### Translation Style:
When responding, translate the given input into how Sir Aldric would speak. Maintain a tone of nobility and wisdom while ensuring clarity in your message.

Example Translations:
- Input: "Let's fight together!"  
  → "Stand firm, brave comrade! Together, we shall vanquish the darkness!"
  
- Input: "That was a great move!"  
  → "A most commendable strike! Truly, the light favors our cause this day."

- Input: "I need your help!"  
  → "Fear not, for I shall lend thee my strength! No evil shall prevail while I stand!"

Remain in character at all times, shaping responses as Sir Aldric would. Let honor guide your words and actions.
"""
    
    paladin = Character(
        name="Sir Aldric the Valiant",
        description="A noble and chivalrous paladin devoted to justice, honor, and the protection of the innocent.",
        type=CharacterType.PLAYER,
        # properties={
        #     "is_template": True,
        #     "is_public": True,
        #     "template": paladin_template
        # },
        entity_id=paladin_entity.id,
        tier=1
    )
    templates.append(paladin)
    
    # Rogue template
    rogue_template = """
You are Selene Nightshade, a cunning rogue and master of stealth, deception, and quick wit. You speak with a sly, confident, and often sarcastic tone, always keeping an air of mystery and pragmatism. Your words are sharp, playful, and calculated, but you never shy away from a well-placed threat or a bit of mischief.

### Role and Speech Guidelines:
- **Witty and Sarcastic** – You use sharp humor and a casual, almost teasing tone.
- **Street-Smart and Cunning** – Always think two steps ahead, questioning everything.
- **Pragmatic but Loyal** – You won't sacrifice yourself for heroics, but you protect your own.
- **Mysterious and Flirtatious** – You keep your true thoughts hidden, sometimes using charm or intimidation.

### Translation Style:
Translate the input into how Selene Nightshade would speak—smooth, snarky, and full of rogue-like confidence.

Example Translations:
- Input: "Let's fight together!"  
  → "Oh, sticking together, huh? Fine. Just don't slow me down, alright?"

- Input: "That was a great move!"  
  → "Not bad… for an amateur. Keep that up, and you might actually impress me."

- Input: "I need your help!"  
  → "Ugh, fine. But you owe me for this one. And trust me, I collect my debts."

Stay in character at all times. Every word should carry Selene's cunning, charm, and roguish attitude.
"""
    
    rogue = Character(
        name="Selene Nightshade",
        description="A cunning rogue and master of stealth, deception, and quick wit.",
        type=CharacterType.PLAYER,
        # properties={
        #     "is_template": True,
        #     "is_public": True,
        #     "template": rogue_template
        # },
        entity_id=rogue_entity.id,
        tier=1
    )
    templates.append(rogue)
    
    # Mage template
    mage_template = """
You are Thorne Spellweaver, an eccentric and brilliant arcane mage with vast knowledge of the magical arts. Your speech is filled with arcane terminology, scholarly references, and occasional bursts of excitement when discussing magical theory. You're thoughtful, analytical, and sometimes aloof, viewing the world through the lens of magical potential.

### Role and Speech Guidelines:
- **Scholarly and Analytical** – You use precise, academic language and often reference magical theories.
- **Eccentric and Enthusiastic** – You become animated when discussing magic, sometimes losing track of social norms.
- **Mysterious and Cryptic** – You occasionally speak in riddles or metaphors, especially about powerful magic.
- **Curious and Observant** – You're fascinated by unusual phenomena and constantly seeking knowledge.

### Translation Style:
Transform the input into how Thorne would speak—intellectual, slightly detached, and peppered with arcane references.

Example Translations:
- Input: "Let's fight together!"  
  → "Yes, our combined arcane signatures should create a fascinating synergy! I'll prepare a thaumaturgical barrier while you channel offensive energies!"

- Input: "That was a great move!"  
  → "A most elegant application of force! The resonance pattern was nearly perfect—reminds me of the Third Principle of Evocation."

- Input: "I need your help!"  
  → "Ah, requiring mystical assistance? *adjusts spectacles* I have several theoretical approaches that might prove applicable to your predicament..."

Every response should convey Thorne's magical expertise, intellectual curiosity, and slightly disconnected perspective on mundane matters.
"""
    
    mage = Character(
        name="Thorne Spellweaver",
        description="An eccentric and brilliant arcane mage with vast knowledge of the magical arts.",
        type=CharacterType.PLAYER,
        # properties={
        #     "is_template": True,
        #     "is_public": True,
        #     "template": mage_template
        # },
        entity_id=mage_entity.id,
        tier=1
    )
    templates.append(mage)
    
    # Barbarian template
    barbarian_template = """
You are Krag Skullcrusher, a mighty barbarian warrior from the northern mountains. Your speech is direct, blunt, and often loud, with simple sentence structure and forceful expressions. You value strength, courage, and loyalty above all, and have little patience for weakness or complicated plans.

### Role and Speech Guidelines:
- **Direct and Forceful** – Use short, powerful sentences with simple words.
- **Passionate and Loud** – Express emotions strongly, especially anger, joy, and battle-lust.
- **Honor-Bound** – Speak often of strength, courage, and the warrior's way.
- **Impatient with Complexity** – Show frustration with long-winded explanations or subtle plans.

### Translation Style:
Convert the input into Krag's straightforward, powerful manner of speaking.

Example Translations:
- Input: "Let's fight together!"  
  → "YES! KRAG FIGHT WITH YOU! WE CRUSH ENEMIES TOGETHER!"

- Input: "That was a great move!"  
  → "GOOD KILL! YOU STRONG WARRIOR! ANCESTORS SMILE ON YOUR AXE!"

- Input: "I need your help!"  
  → "KRAG HELP! TELL KRAG WHO NEEDS SMASHING! POINT WAY TO BATTLE!"

Each response should emphasize Krag's physical strength, direct approach to problems, and tribal warrior worldview. Use occasional third-person self-reference for emphasis.
"""
    
    barbarian = Character(
        name="Krag Skullcrusher",
        description="A mighty barbarian warrior from the northern mountains.",
        type=CharacterType.PLAYER,
        # properties={
        #     "is_template": True,
        #     "is_public": True,
        #     "template": barbarian_template
        # },
        entity_id=barbarian_entity.id,
        tier=1
    )
    templates.append(barbarian)
    
    # Add all templates to database
    for template in templates:
        db.add(template)
    
    db.commit()
    logger.info(f"Created {len(templates)} character templates")
    
    return templates


def seed_worlds(db: Session):
    """Seed the database with initial world data"""
    
    # Check if worlds already exist
    world_count = db.query(func.count(World.id)).scalar() or 0
    if world_count > 0:
        return
    
    # Create admin user if not exists
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
    
    # Create some initial worlds
    worlds = [
        World(
            name="Fantasy World",
            description="A magical world filled with fantasy creatures and landscapes",
            properties={"theme": "medieval", "magic_level": "high", "genre": "Fantasy"},
            tier=1,
            owner_id=admin.id
        ),
        World(
            name="Sci-Fi Universe",
            description="A futuristic universe with advanced technology and space exploration",
            properties={"theme": "futuristic", "technology_level": "advanced", "genre": "Science Fiction", "space_travel": True},
            tier=2,
            owner_id=admin.id
        ),
        World(
            name="Post-Apocalyptic Wasteland",
            description="A harsh world devastated by nuclear war and environmental collapse",
            properties={"theme": "wasteland", "radiation_level": "high", "genre": "Post-Apocalyptic", "survival_difficulty": "extreme"},
            tier=1,
            owner_id=admin.id
        )
    ]
    
    for world in worlds:
        db.add(world)
    
    db.commit()
    
    # Seed zones for these worlds
    seed_zones(db)


def seed_zones(db: Session):
    """Seed the database with initial zone data"""
    
    # Check if zones already exist
    zone_count = db.query(func.count(Zone.id)).scalar() or 0
    if zone_count > 0:
        return
    
    # Get worlds
    worlds = db.query(World).all()
    
    for world in worlds:
        # Create top-level zones for each world
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
            
            # Add top-level zones
            for zone in top_level_zones:
                db.add(zone)
            
            db.commit()
            
            # Add sub-zones to Enchanted Forest
            enchanted_forest = db.query(Zone).filter_by(
                world_id=world.id, name="Enchanted Forest"
            ).first()
            
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


def seed_starter_objects(db: Session) -> List[Object]:
    """Seed the database with starter objects for the zones"""
    
    # Check if objects already exist
    existing_objects = db.query(Object).all()
    if existing_objects:
        logger.info(f"Found {len(existing_objects)} existing objects")
        return existing_objects
    
    # Get fantasy world to add objects to
    world = db.query(World).filter(World.name == "Fantasy World").first()
    if not world:
        logger.info("Fantasy world not found, skipping object creation")
        return []
    
    # Find zones
    enchanted_forest = db.query(Zone).filter(
        Zone.name == "Enchanted Forest",
        Zone.world_id == world.id
    ).first()
    
    royal_kingdom = db.query(Zone).filter(
        Zone.name == "Royal Kingdom",
        Zone.world_id == world.id
    ).first()
    
    if not enchanted_forest or not royal_kingdom:
        logger.info("Required zones not found, skipping object creation")
        return []
    
    # Create objects
    objects = []
    
    # Create entities for objects
    magical_tree_entity = Entity(
        name="Ancient Whispering Tree",
        description="A massive, ancient tree whose leaves shimmer with magical energy and whose bark seems to shift patterns when not directly observed.",
        type=EntityType.OBJECT,
        properties={"magic_type": "nature", "magical_properties": ["healing", "wisdom"]},
        # tier=1,
        # world_id=world.id,
        zone_id=enchanted_forest.id
    )
    
    fountain_entity = Entity(
        name="Mystic Fountain",
        description="A small fountain carved from luminescent crystal that flows with water that glows softly in the moonlight.",
        type=EntityType.OBJECT,
        properties={"magic_type": "water", "magical_properties": ["healing", "clarity"]},
        # tier=1,
        # world_id=world.id,
        zone_id=enchanted_forest.id
    )
    
    castle_entity = Entity(
        name="Royal Castle",
        description="A grand castle with towering spires and massive walls, the seat of power for the kingdom.",
        type=EntityType.OBJECT,
        properties={"building_type": "castle", "contains_npcs": True},
        # tier=1,
        # world_id=world.id,
        zone_id=royal_kingdom.id
    )
    
    market_entity = Entity(
        name="Grand Market",
        description="A bustling market square filled with vendors selling everything from exotic foods to rare magical items.",
        type=EntityType.OBJECT,
        properties={"building_type": "market", "contains_npcs": True},
        # tier=1,
        # world_id=world.id,
        zone_id=royal_kingdom.id
    )
    
    db.add_all([magical_tree_entity, fountain_entity, castle_entity, market_entity])
    db.flush()
    
    # Create objects with their entities
    magical_tree = Object(
        name="Ancient Whispering Tree",
        description="A massive, ancient tree whose leaves shimmer with magical energy and whose bark seems to shift patterns when not directly observed.",
        type=ObjectType.GENERIC,
        properties={"is_interactive": True, "magic_type": "nature", "magical_properties": ["healing", "wisdom"]},
        # world_id=world.id,
        # zone_id=enchanted_forest.id,
        entity_id=magical_tree_entity.id,
        tier=1
    )
    objects.append(magical_tree)
    
    fountain = Object(
        name="Mystic Fountain",
        description="A small fountain carved from luminescent crystal that flows with water that glows softly in the moonlight.",
        type=ObjectType.GENERIC,
        properties={"is_interactive": True, "magic_type": "water", "magical_properties": ["healing", "clarity"]},
        # world_id=world.id,
        # zone_id=enchanted_forest.id,
        entity_id=fountain_entity.id,
        tier=1
    )
    objects.append(fountain)
    
    castle = Object(
        name="Royal Castle",
        description="A grand castle with towering spires and massive walls, the seat of power for the kingdom.",
        type=ObjectType.GENERIC,
        properties={"is_interactive": True, "building_type": "castle", "contains_npcs": True},
        # world_id=world.id,
        # zone_id=royal_kingdom.id,
        entity_id=castle_entity.id,
        tier=1
    )
    objects.append(castle)
    
    market = Object(
        name="Grand Market",
        description="A bustling market square filled with vendors selling everything from exotic foods to rare magical items.",
        type=ObjectType.GENERIC,
        properties={"is_interactive": True, "building_type": "market", "contains_npcs": True},
        # world_id=world.id,
        # zone_id=royal_kingdom.id,
        entity_id=market_entity.id,
        tier=1
    )
    objects.append(market)
    
    # Add objects to database
    for obj in objects:
        db.add(obj)
    
    db.commit()
    logger.info(f"Created {len(objects)} starter objects")
    return objects


# Update the seed_database function to include starter objects
def seed_database():
    """Seed the database with initial data"""
    logger.info("Starting database seeding...")
    
    # Create database session
    db = SessionLocal()
    
    try:
        # Create tables if they don't exist
        Base.metadata.create_all(bind=engine)
        
        # Seed subscription plans
        seed_subscription_plans(db)
        
        # Seed default agents
        seed_default_agents(db)
        
        # Seed character templates
        seed_character_templates(db)
        
        # Seed starter worlds
        seed_worlds(db)
        
        # Seed starter zones
        seed_zones(db)
        
        # Seed starter objects
        seed_starter_objects(db)
        
        logger.info("Database seeding completed successfully")
    
    except Exception as e:
        logger.error(f"Error seeding database: {str(e)}")
    
    finally:
        db.close()


if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Run seeder
    seed_database()