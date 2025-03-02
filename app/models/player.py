# app/models/user.py
from sqlalchemy import Boolean, Column, ForeignKey, String, DateTime
from sqlalchemy.orm import relationship

from app.database import Base
from app.models.mixins import TimestampMixin


class Player(Base, TimestampMixin):
    """
    Model representing user accounts
    The id is linked to Supabase auth.users.id
    """
    __tablename__ = "players"
    
    id = Column(String(36), primary_key=True, index=True)  # Linked to Supabase auth.users.id
    first_name = Column(String(50), nullable=True)
    last_name = Column(String(50), nullable=True)
    email = Column(String(100), unique=True, index=True, nullable=False)
    is_active = Column(Boolean, default=True)
    
    # Premium status and management
    is_premium = Column(Boolean, default=False, nullable=False)
    premium_since = Column(DateTime, nullable=True)
    
    # Admin flag for special privileges
    is_admin = Column(Boolean, default=False, nullable=False)
    
    # world_id = Column(String(36), ForeignKey("worlds.id"), nullable=True)
    # zone_id = Column(String(36), ForeignKey("zones.id"), nullable=True)
    # entity_id = Column(String(36), ForeignKey("entities.id"), nullable=True)
    character_id = Column(String(36), ForeignKey("characters.id"), nullable=True)

    # world = relationship("World", back_populates="players")
    # zone = relationship("Zone", back_populates="players")
    # entity = relationship("Entity", back_populates="players")
    character = relationship("Character", back_populates="player")
    
    # User participations in conversations (as specific characters)
    conversation_participations = relationship(
        "ConversationParticipant",
        back_populates="player",
        cascade="all, delete-orphan"
    )
    
    # Subscription and usage tracking
    subscriptions = relationship("UserSubscription", back_populates="player", cascade="all, delete-orphan")
    daily_usage = relationship("UserDailyUsage", back_populates="player", cascade="all, delete-orphan")
    usage_summary = relationship("UserUsageSummary", back_populates="player", uselist=False, cascade="all, delete-orphan")
    
    # Worlds owned by this user
    owned_worlds = relationship("World", back_populates="owner", foreign_keys="World.owner_id", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User {self.id} - {self.email}>"
    
    @property
    def display_name(self):
        """Get user's display name"""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        elif self.first_name:
            return self.first_name
        else:
            return self.email.split('@')[0]  # Use part before @ in email