#!/usr/bin/env python
# migrate_worlds.py - Script to migrate existing data to include the new World model
import logging
from sqlalchemy.orm import Session
import sys

from app.database import SessionLocal, engine, Base
from app.models.world import World
from app.models.character import Character
from app.models.conversation import Conversation
from app.database_seeder import seed_starter_worlds

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("migration")

def migrate_data():
    """Migrate existing data to include worlds"""
    logger.info("Starting migration to add worlds...")
    
    # Create database session
    db = SessionLocal()
    
    try:
        # Ensure the table exists
        Base.metadata.create_all(bind=engine)
        
        # First, seed starter worlds
        starter_worlds = seed_starter_worlds(db)
        
        if not starter_worlds:
            logger.error("Failed to create starter worlds")
            return False
        
        # Get the default fantasy world to use as fallback
        default_world = next((world for world in starter_worlds if world.name == "Eldoria"), starter_worlds[0])
        
        # Migrate characters
        migrate_characters(db, default_world)
        
        # Migrate conversations
        migrate_conversations(db, default_world)
        
        logger.info("Migration completed successfully")
        return True
    
    except Exception as e:
        db.rollback()
        logger.error(f"Error during migration: {str(e)}")
        return False
    
    finally:
        db.close()

def migrate_characters(db: Session, default_world: World):
    """Migrate existing characters to be associated with a world"""
    # Get characters without a world
    characters = db.query(Character).filter(Character.world_id.is_(None)).all()
    
    logger.info(f"Migrating {len(characters)} characters to default world")
    
    for character in characters:
        character.world_id = default_world.id
    
    if characters:
        db.commit()
        logger.info(f"Migrated {len(characters)} characters to world: {default_world.name}")

def migrate_conversations(db: Session, default_world: World):
    """Migrate existing conversations to be associated with a world"""
    # Get conversations without a world
    conversations = db.query(Conversation).filter(Conversation.world_id.is_(None)).all()
    
    logger.info(f"Migrating {len(conversations)} conversations to default world")
    
    for conversation in conversations:
        conversation.world_id = default_world.id
    
    if conversations:
        db.commit()
        logger.info(f"Migrated {len(conversations)} conversations to world: {default_world.name}")

if __name__ == "__main__":
    logger.info("Running World migration script")
    
    if migrate_data():
        logger.info("Migration completed successfully")
        sys.exit(0)
    else:
        logger.error("Migration failed")
        sys.exit(1)