# app/models/usage.py
from sqlalchemy import Column, String, Integer, Date, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import date
from app.database import Base
from app.models.mixins import TimestampMixin, generate_uuid

class UserDailyUsage(Base, TimestampMixin):
    __tablename__ = "user_daily_usage"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("players.id"), nullable=False, index=True)
    date = Column(Date, default=date.today, nullable=False)
    
    message_count = Column(Integer, default=0, nullable=False)
    ai_response_count = Column(Integer, default=0, nullable=False)
    
    player = relationship("Player", back_populates="daily_usage")
    
    __table_args__ = (
        UniqueConstraint('user_id', 'date', name='uix_user_daily_usage'),
    )
    
    def __repr__(self):
        return f"<UserDailyUsage {self.id} - User: {self.user_id} - Date: {self.date}>"

class UserUsageSummary(Base, TimestampMixin):
    __tablename__ = "user_usage_summary"
    
    user_id = Column(String(36), ForeignKey("players.id"), primary_key=True)
    
    total_messages = Column(Integer, default=0, nullable=False)
    total_ai_responses = Column(Integer, default=0, nullable=False)
    total_conversations = Column(Integer, default=0, nullable=False)
    total_characters = Column(Integer, default=0, nullable=False)
    active_conversations = Column(Integer, default=0, nullable=False)
    active_characters = Column(Integer, default=0, nullable=False)
    
    player = relationship("Player", back_populates="usage_summary")
    
    def __repr__(self):
        return f"<UserUsageSummary - User: {self.user_id}>"
