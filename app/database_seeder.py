# app/database_seeder.py
from sqlalchemy.orm import Session
import logging
from typing import List

from app.database import SessionLocal, engine, Base
from app.models.character import Character
from app.models.subscription import SubscriptionPlan
from app.models.agent import Agent
from app.models.world import World
from app.config import get_settings
from app.models.zone import Zone

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
        description="Basic access to the chat platform",
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
        description="Enhanced access with more characters and messages",
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
    
    # Create default agent
    default_agent = Agent(
        name="Assistant",
        description="A helpful AI assistant that can roleplay as various characters",
        system_prompt=(
            "You are a helpful AI assistant participating in a conversation. "
            "You will be assigned a character to roleplay as, with a specific name and personality. "
            "Stay in character at all times, responding as your assigned character would. "
            "Be attentive and engaging, keeping your responses appropriate for the context of the conversation."
        ),
        is_active=True
    )
    
    # Add agent to database
    db.add(default_agent)
    db.commit()
    
    logger.info("Created default agent: Assistant")
    return [default_agent]


def seed_character_templates(db: Session) -> List[Character]:
    """Seed the database with character templates"""
    
    # Check if templates already exist
    existing_templates = db.query(Character).filter(Character.is_template == True).all()
    if existing_templates:
        logger.info(f"Found {len(existing_templates)} existing character templates")
        return existing_templates
    
    # Create character templates
    templates = []
    
    # Paladin template
    paladin = Character(
        name="Sir Aldric the Valiant",
        description="A noble and chivalrous paladin devoted to justice, honor, and the protection of the innocent.",
        template="""
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
""",
        is_template=True,
        is_public=True
    )
    templates.append(paladin)
    
    # Rogue template
    rogue = Character(
        name="Selene Nightshade",
        description="A cunning rogue and master of stealth, deception, and quick wit.",
        template="""
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
""",
        is_template=True,
        is_public=True
    )
    templates.append(rogue)
    
    # Mage template
    mage = Character(
        name="Thorne Spellweaver",
        description="An eccentric and brilliant arcane mage with vast knowledge of the magical arts.",
        template="""
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
""",
        is_template=True,
        is_public=True
    )
    templates.append(mage)
    
    # Barbarian template
    barbarian = Character(
        name="Krag Skullcrusher",
        description="A mighty barbarian warrior from the northern mountains.",
        template="""
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
""",
        is_template=True,
        is_public=True
    )
    templates.append(barbarian)
    
    # Add all templates to database
    for template in templates:
        db.add(template)
    
    db.commit()
    logger.info(f"Created {len(templates)} character templates")
    
    return templates

def seed_starter_worlds(db: Session) -> List[World]:
    """Seed the database with starter worlds"""
    
    # Check if starter worlds already exist
    existing_starters = db.query(World).filter(World.is_starter == True).all()
    if existing_starters:
        logger.info(f"Found {len(existing_starters)} existing starter worlds")
        return existing_starters
    
    # Create starter worlds
    worlds = []
    
    # Fantasy world
    fantasy = World(
        name="Eldoria",
        description="A high fantasy realm of magic, dragons, and epic quests. Eldoria is home to diverse races including humans, elves, dwarves, and magical creatures.",
        genre="Fantasy",
        settings="""
{
    "magic_level": "high",
    "technology_level": "medieval",
    "races": ["humans", "elves", "dwarves", "orcs", "halflings"],
    "major_regions": ["The Northern Kingdoms", "Elven Forests", "Dwarven Mountains", "The Mystical Isles"]
}""",
        default_prompt="""
You are in Eldoria, a high fantasy realm where magic flows through the very air and epic quests await brave adventurers. 
Dragons soar through the skies, ancient ruins hide forgotten treasures, and the forces of darkness gather in the shadows.
Characters in this world should speak and act according to fantasy tropes and medieval customs.
""",
        is_starter=True,
        is_public=True
    )
    worlds.append(fantasy)
    
    # Sci-Fi world
    scifi = World(
        name="Nova Prime",
        description="A futuristic sci-fi universe with interstellar travel, advanced technology, and alien civilizations spread across the galaxy.",
        genre="Science Fiction",
        settings="""
{
    "tech_level": "advanced",
    "ftl_travel": true,
    "alien_races": 12,
    "major_factions": ["Terran Alliance", "Zorn Collective", "Free Traders Guild", "The Ancient Ones"]
}""",
        default_prompt="""
You are in Nova Prime, a vast sci-fi universe in the year 3752 CE. Humanity has spread among the stars, encountering numerous alien civilizations.
Faster-than-light travel is common, AI companions are ubiquitous, and genetic engineering has created specialized human variants.
Characters should reference advanced technology, space travel, and the complex political landscape of competing interstellar factions.
""",
        is_starter=True,
        is_public=True
    )
    worlds.append(scifi)
    
    # Post-apocalyptic world
    postapoc = World(
        name="Wasteland",
        description="A gritty post-apocalyptic world where survivors struggle to rebuild civilization after a global catastrophe.",
        genre="Post-Apocalyptic",
        settings="""
{
    "apocalypse_type": "nuclear war",
    "years_since_fall": 87,
    "radiation_zones": ["Dead Cities", "The Glowing Sea"],
    "factions": ["Survivors Union", "Raiders", "The New Government", "Mutant Collective"]
}""",
        default_prompt="""
You are in the Wasteland, 87 years after nuclear war devastated civilization. Resources are scarce, dangers lurk everywhere,
and different factions fight for control of what remains. Radiation has mutated some creatures and humans, creating new threats.
Characters should be hardened by the harsh reality of survival, referencing scavenging, makeshift weapons and armor, and the constant
struggle to find clean water, food, and supplies.
""",
        is_starter=True,
        is_public=True
    )
    worlds.append(postapoc)
    
    # Modern supernatural world
    supernatural = World(
        name="Shadow Veil",
        description="A modern world where supernatural creatures exist in the shadows of human society. Vampires run nightclubs, werewolves live in the forests, and witches practice their craft in secret.",
        genre="Urban Fantasy",
        settings="""
{
    "time_period": "modern day",
    "supernatural_types": ["vampires", "werewolves", "witches", "fae", "ghosts"],
    "magic_visibility": "hidden from most humans",
    "major_locations": ["Crescent City", "The Undermarket", "Fae Realms"]
}""",
        default_prompt="""
You are in Shadow Veil, a world identical to modern Earth but with a secret supernatural society hidden from human eyes.
Vampires control nightlife businesses, werewolves protect wilderness areas, witches form covens in urban areas, and fae creatures
slip between our world and theirs. Characters should reference modern technology alongside supernatural abilities and the
careful balance between the mundane world and the supernatural one.
""",
        is_starter=True,
        is_public=True
    )
    worlds.append(supernatural)
    
    # Add worlds to database
    for world in worlds:
        db.add(world)
    
    db.commit()
    
    logger.info(f"Created {len(worlds)} starter worlds")
    return worlds

def seed_starter_zones(db: Session) -> List[Zone]:
    """Seed the database with starter zones for each starter world"""
    
    # Check if starter worlds have zones already
    existing_zones = db.query(Zone).join(World).filter(World.is_starter == True).all()
    if existing_zones:
        logger.info(f"Found {len(existing_zones)} existing zones in starter worlds")
        return existing_zones
    
    # Get all starter worlds
    starter_worlds = db.query(World).filter(World.is_starter == True).all()
    if not starter_worlds:
        logger.info("No starter worlds found to add zones to")
        return []
    
    # Creating zones for each world
    zones = []
    
    for world in starter_worlds:
        if world.name == "Eldoria": # Fantasy world
            # Create top-level zones
            capital = Zone(
                name="Eldoria Capital",
                description="The grand capital city of Eldoria, with towering spires, magical academies, and bustling markets.",
                zone_type="city",
                world_id=world.id
            )
            zones.append(capital)
            
            northern_wilds = Zone(
                name="Northern Wilds",
                description="A vast region of untamed forests, mountains, and valleys, home to dangerous creatures and hidden treasures.",
                zone_type="wilderness",
                world_id=world.id
            )
            zones.append(northern_wilds)
            
            elven_forest = Zone(
                name="Silverleaf Forest",
                description="Ancient forest realm of the elves, with trees older than human civilization and magical glades.",
                zone_type="forest",
                world_id=world.id
            )
            zones.append(elven_forest)
            
            dwarven_halls = Zone(
                name="Irondeep Mountains",
                description="Mountain range containing the legendary dwarven kingdom with vast mines and forges.",
                zone_type="mountains",
                world_id=world.id
            )
            zones.append(dwarven_halls)
            
            # Add to database to get IDs
            for zone in zones:
                db.add(zone)
            db.flush()
            
            # Create sub-zones
            zones.append(Zone(
                name="Royal Palace",
                description="Home of the human king and center of government.",
                zone_type="building",
                world_id=world.id,
                parent_zone_id=capital.id
            ))
            
            zones.append(Zone(
                name="Merchant District",
                description="Bustling commercial area with shops, markets and guilds.",
                zone_type="district",
                world_id=world.id,
                parent_zone_id=capital.id
            ))
            
            zones.append(Zone(
                name="Arcane University",
                description="Prestigious magical academy where mages study ancient arts.",
                zone_type="building",
                world_id=world.id,
                parent_zone_id=capital.id
            ))
            
            zones.append(Zone(
                name="Frost Peaks",
                description="Dangerous, snow-covered mountains home to frost giants and white dragons.",
                zone_type="mountains",
                world_id=world.id,
                parent_zone_id=northern_wilds.id
            ))
            
            zones.append(Zone(
                name="Mistwood",
                description="Foggy forest where the veil between realms is thin and fae creatures appear.",
                zone_type="forest",
                world_id=world.id,
                parent_zone_id=northern_wilds.id
            ))
            
        elif world.name == "Nova Prime": # Sci-fi world
            # Create top-level zones
            central_hub = Zone(
                name="Nexus Station",
                description="Massive space station serving as the administrative center of the Terran Alliance.",
                zone_type="space_station",
                world_id=world.id
            )
            zones.append(central_hub)
            
            earth_system = Zone(
                name="Sol System",
                description="Birthplace of humanity, now a densely populated core system with Earth as its jewel.",
                zone_type="star_system",
                world_id=world.id
            )
            zones.append(earth_system)
            
            frontier = Zone(
                name="The Frontier",
                description="Newly discovered systems on the edge of known space, largely unexplored and dangerous.",
                zone_type="region",
                world_id=world.id
            )
            zones.append(frontier)
            
            alien_territory = Zone(
                name="Zorn Collective Space",
                description="Territory controlled by the technologically advanced Zorn species.",
                zone_type="region",
                world_id=world.id
            )
            zones.append(alien_territory)
            
            # Add to database to get IDs
            for zone in zones:
                db.add(zone)
            db.flush()
            
            # Create sub-zones
            zones.append(Zone(
                name="Command Section",
                description="Military and administrative heart of Nexus Station.",
                zone_type="section",
                world_id=world.id,
                parent_zone_id=central_hub.id
            ))
            
            zones.append(Zone(
                name="Trade Hub",
                description="Commercial center where merchants from across the galaxy conduct business.",
                zone_type="section",
                world_id=world.id,
                parent_zone_id=central_hub.id
            ))
            
            zones.append(Zone(
                name="Earth",
                description="Humanity's homeworld, now a carefully preserved planet with limited population.",
                zone_type="planet",
                world_id=world.id,
                parent_zone_id=earth_system.id
            ))
            
            zones.append(Zone(
                name="Mars Colony",
                description="First human settlement beyond Earth, now a thriving industrial center.",
                zone_type="planet",
                world_id=world.id,
                parent_zone_id=earth_system.id
            ))
            
        elif world.name == "Wasteland": # Post-apocalyptic world
            # Create top-level zones
            haven = Zone(
                name="Haven",
                description="The largest survivor settlement, built within the ruins of an old sports stadium.",
                zone_type="settlement",
                world_id=world.id
            )
            zones.append(haven)
            
            dead_city = Zone(
                name="Dead City",
                description="Ruins of a major pre-war metropolis, highly radioactive but filled with valuable tech.",
                zone_type="ruins",
                world_id=world.id
            )
            zones.append(dead_city)
            
            wastes = Zone(
                name="The Great Wastes",
                description="Vast desert-like region where survival is nearly impossible due to radiation and lack of water.",
                zone_type="wasteland",
                world_id=world.id
            )
            zones.append(wastes)
            
            # Add to database to get IDs
            for zone in zones:
                db.add(zone)
            db.flush()
            
            # Create sub-zones
            zones.append(Zone(
                name="Market District",
                description="Central trading area where survivors barter goods.",
                zone_type="district",
                world_id=world.id,
                parent_zone_id=haven.id
            ))
            
            zones.append(Zone(
                name="The Wall",
                description="Defensive perimeter of Haven, constantly guarded against raiders.",
                zone_type="fortification",
                world_id=world.id,
                parent_zone_id=haven.id
            ))
            
            zones.append(Zone(
                name="Downtown Ruins",
                description="Former financial district, now a labyrinth of collapsed skyscrapers.",
                zone_type="ruins",
                world_id=world.id,
                parent_zone_id=dead_city.id
            ))
            
        elif world.name == "Shadow Veil": # Urban fantasy world
            # Create top-level zones
            city = Zone(
                name="Crescent City",
                description="A modern metropolis where supernatural creatures hide in plain sight among humans.",
                zone_type="city",
                world_id=world.id
            )
            zones.append(city)
            
            otherside = Zone(
                name="The Veil",
                description="The supernatural realm that overlaps with the human world, accessible only to magical beings.",
                zone_type="realm",
                world_id=world.id
            )
            zones.append(otherside)
            
            # Add to database to get IDs
            for zone in zones:
                db.add(zone)
            db.flush()
            
            # Create sub-zones
            zones.append(Zone(
                name="Midnight District",
                description="Downtown area with high supernatural population, featuring clubs, bars, and magical shops.",
                zone_type="district",
                world_id=world.id,
                parent_zone_id=city.id
            ))
            
            zones.append(Zone(
                name="Fae Court",
                description="Magical realm within The Veil where the fae nobility resides.",
                zone_type="realm",
                world_id=world.id,
                parent_zone_id=otherside.id
            ))
            
            zones.append(Zone(
                name="Shadow Market",
                description="Hidden supernatural marketplace accessible only through secret entrances.",
                zone_type="market",
                world_id=world.id,
                parent_zone_id=city.id
            ))
    
    # Save all zones
    db.commit()
    
    total_created = len(zones)
    logger.info(f"Created {total_created} zones across {len(starter_worlds)} starter worlds")
    return zones

# Update the seed_database function to include zones
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
        seed_starter_worlds(db)
        
        # Seed starter zones
        seed_starter_zones(db)
        
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
