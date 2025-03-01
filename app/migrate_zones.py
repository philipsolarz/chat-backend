#!/usr/bin/env python
# migrate_zones.py - Script to migrate existing data to include the new Zone model
import logging
from sqlalchemy.orm import Session
import sys

from app.database import SessionLocal, engine, Base
from app.models.zone import Zone
from app.models.world import World
from app.models.character import Character
from app.models.agent import Agent
from app.database_seeder import seed_starter_zones

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("migration")

def migrate_data():
    """Migrate existing data to include zones"""
    logger.info("Starting migration to add zones...")
    
    # Create database session
    db = SessionLocal()
    
    try:
        # Ensure the tables exist
        Base.metadata.create_all(bind=engine)
        
        # Add zone_limit and zone_limit_upgrades to worlds
        migrate_world_zone_limits(db)
        
        # Seed starter zones
        starter_zones = seed_starter_zones(db)
        
        if not starter_zones:
            logger.error("Failed to create starter zones")
            return False
        
        # For each world, create a default zone if none exists
        migrate_world_zones(db)
        
        # Migrate characters to zones
        migrate_characters_to_zones(db)
        
        # Migrate agents to zones
        migrate_agents_to_zones(db)
        
        logger.info("Migration completed successfully")
        return True
    
    except Exception as e:
        db.rollback()
        logger.error(f"Error during migration: {str(e)}")
        return False
    
    finally:
        db.close()

def migrate_world_zone_limits(db: Session):
    """Add zone limit fields to existing worlds"""
    # Check if any worlds are missing zone_limit
    worlds_without_limits = db.query(World).filter(World.zone_limit.is_(None)).all()
    
    logger.info(f"Migrating {len(worlds_without_limits)} worlds to add zone limits")
    
    for world in worlds_without_limits:
        world.zone_limit = 100
        world.zone_limit_upgrades = 0
    
    if worlds_without_limits:
        db.commit()
        logger.info(f"Added zone limits to {len(worlds_without_limits)} worlds")

def migrate_world_zones(db: Session):
    """Create a default zone for worlds without zones"""
    # Get all worlds
    worlds = db.query(World).all()
    
    worlds_updated = 0
    
    for world in worlds:
        # Check if world has any zones
        zone_count = db.query(Zone).filter(Zone.world_id == world.id).count()
        
        if zone_count == 0:
            # Create a default zone for this world
            zone = Zone(
                name="Main Area",
                description=f"Primary zone for {world.name}",
                zone_type="general",
                world_id=world.id
            )
            
            db.add(zone)
            worlds_updated += 1
    
    if worlds_updated > 0:
        db.commit()
        logger.info(f"Created default zones for {worlds_updated} worlds")

def migrate_characters_to_zones(db: Session):
    """Assign characters to zones"""
    # Get characters without a zone
    characters = db.query(Character).filter(Character.zone_id.is_(None)).all()
    
    logger.info(f"Migrating {len(characters)} characters to zones")
    
    for character in characters:
        if not character.world_id:
            # Skip characters without a world
            continue
            
        # Find a zone in this world (preferably a top-level zone)
        zone = db.query(Zone).filter(
            Zone.world_id == character.world_id,
            Zone.parent_zone_id.is_(None)
        ).first()
        
        if not zone:
            # If no top-level zone, get any zone in this world
            zone = db.query(Zone).filter(Zone.world_id == character.world_id).first()
        
        if zone:
            character.zone_id = zone.id
    
    if characters:
        db.commit()
        logger.info(f"Assigned {len(characters)} characters to zones")

def migrate_agents_to_zones(db: Session):
    """Assign agents (NPCs) to zones"""
    # Get agents without a zone
    agents = db.query(Agent).filter(Agent.zone_id.is_(None)).all()
    
    logger.info(f"Migrating {len(agents)} agents to zones")
    
    worlds_with_agents = set()
    for agent in agents:
        # Since agents don't have a direct world relationship, we'll place them
        # in a random zone of starter worlds
        if not worlds_with_agents:
            # Populate cache of worlds with zones
            worlds = db.query(World).filter(World.is_starter == True).all()
            for world in worlds:
                zone_count = db.query(Zone).filter(Zone.world_id == world.id).count()
                if zone_count > 0:
                    worlds_with_agents.add(world.id)
        
        if worlds_with_agents:
            # Get any world with zones
            world_id = next(iter(worlds_with_agents))
            
            # Find a zone in this world
            zone = db.query(Zone).filter(Zone.world_id == world_id).first()
            
            if zone:
                agent.zone_id = zone.id
    
    if agents:
        db.commit()
        logger.info(f"Assigned {len(agents)} agents to zones")

if __name__ == "__main__":
    logger.info("Running Zone migration script")
    
    if migrate_data():
        logger.info("Migration completed successfully")
        sys.exit(0)
    else:
        logger.error("Migration failed")
        sys.exit(1)