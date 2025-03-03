# app/models/player.py
from sqlalchemy import Column, String, Boolean, DateTime
from sqlalchemy.orm import relationship
from app.database import Base
from app.models.mixins import TimestampMixin

class Player(Base, TimestampMixin):
    __tablename__ = "players"
    
    id = Column(String(36), primary_key=True, index=True)
    first_name = Column(String(50), nullable=True)
    last_name = Column(String(50), nullable=True)
    email = Column(String(100), unique=True, index=True, nullable=False)
    is_active = Column(Boolean, default=True)
    is_premium = Column(Boolean, default=False, nullable=False)
    premium_since = Column(DateTime, nullable=True)
    is_admin = Column(Boolean, default=False, nullable=False)
    
    # Relationships
    character = relationship("Character", back_populates="player", uselist=False)
    owned_worlds = relationship("World", back_populates="owner", cascade="all, delete-orphan")
    subscriptions = relationship("UserSubscription", back_populates="player", cascade="all, delete-orphan")
    daily_usage = relationship("UserDailyUsage", back_populates="player", cascade="all, delete-orphan")
    usage_summary = relationship("UserUsageSummary", back_populates="player", uselist=False, cascade="all, delete-orphan")
    conversation_participations = relationship("ConversationParticipant", back_populates="player", cascade="all, delete-orphan")
    
    @property
    def display_name(self):
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        elif self.first_name:
            return self.first_name
        else:
            return self.email.split('@')[0]
    
    def __repr__(self):
        return f"<Player {self.id} - {self.email}>"
