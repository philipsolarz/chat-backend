# app/models/world.py
from sqlalchemy import Column, Integer, String, Text, Boolean, ForeignKey, Float, Table
from sqlalchemy.orm import relationship

from app.database import Base
from app.models.mixins import TimestampMixin, generate_uuid


# Association table for world members
world_members = Table(
    'world_members',
    Base.metadata,
    Column('world_id', String(36), ForeignKey('worlds.id'), primary_key=True),
    Column('user_id', String(36), ForeignKey('users.id'), primary_key=True)
)


class World(Base, TimestampMixin):
    """
    Model representing a game world where characters, conversations, and quests exist
    """
    __tablename__ = "worlds"
    
    id = Column(String(36), primary_key=True, default=generate_uuid, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    
    # Type of world (fantasy, sci-fi, etc)
    genre = Column(String(50), nullable=True)
    
    # World rules and configuration (could be JSON in a real implementation)
    settings = Column(Text, nullable=True)

    zone_limit = Column(Integer, default=100)
    zone_limit_upgrades = Column(Integer, default=0)

    # Add relationship to zones (already created in the Zone model):
    zones = relationship("Zone", back_populates="world", cascade="all, delete-orphan")

    # Default prompt addition for AI agents in this world
    default_prompt = Column(Text, nullable=True)
    
    # Whether this is a featured/starter world available to all users
    is_starter = Column(Boolean, default=False)
    
    # Whether this world is public or private
    is_public = Column(Boolean, default=False)
    
    # Premium worlds
    is_premium = Column(Boolean, default=False)
    price = Column(Float, nullable=True)  # Price in USD
    
    # Creator/owner of the world
    owner_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    
    # Relationships
    owner = relationship("User", back_populates="owned_worlds", foreign_keys=[owner_id])
    
    # Many-to-many relationship with users (members who can access this world)
    members = relationship(
        "User",
        secondary=world_members,
        back_populates="joined_worlds"
    )
    
    # One-to-many relationships
    characters = relationship("Character", back_populates="world")
    conversations = relationship("Conversation", back_populates="world")
    
    def __repr__(self):
        return f"<World {self.id} - {self.name}>"
    
    @property
    def total_zone_limit(self):
        """Calculate total zone limit with upgrades"""
        return self.zone_limit + (self.zone_limit_upgrades * 100)