# app/models/message.py
from sqlalchemy import Column, String, Text, ForeignKey, Index
from sqlalchemy.orm import relationship
from app.database import Base
from app.models.mixins import TimestampMixin, generate_uuid

class Message(Base, TimestampMixin):
    __tablename__ = "messages"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    content = Column(Text, nullable=False)
    
    conversation_id = Column(String(36), ForeignKey("conversations.id"), nullable=False, index=True)
    participant_id = Column(String(36), ForeignKey("conversation_participants.id"), nullable=False)
    
    conversation = relationship("Conversation", back_populates="messages")
    participant = relationship("ConversationParticipant")
    
    __table_args__ = (
        Index('ix_messages_conversation_created', "conversation_id", "created_at"),
    )
    
    def __repr__(self):
        return f"<Message {self.id} in Conversation {self.conversation_id}>"
