# app/ai/schemas.py
from typing import List, Dict, Any, Optional, Union
from pydantic import BaseModel, Field
from datetime import datetime


class Message(BaseModel):
    """Base message schema for API communication"""
    role: str
    content: str


class MessageHistory(BaseModel):
    """Schema for message history"""
    messages: List[Message]


class AIResponse(BaseModel):
    """Schema for AI-generated responses"""
    content: str
    reasoning: Optional[str] = None


class CharacterTransformation(BaseModel):
    """Schema for character voice transformations"""
    original_content: str
    transformed_content: str
    character_id: str
    character_name: str


class QuestInfo(BaseModel):
    """Schema for RPG quest information"""
    quest_id: str
    title: str
    description: str
    status: str = "active"
    progress: Optional[float] = 0.0


class DialogOptions(BaseModel):
    """Schema for dialog options in RPG mode"""
    dialog_id: str
    options: List[Dict[str, str]]
    prompt: str


class CharacterProfile(BaseModel):
    """Schema for character profiles used in agent context"""
    id: str
    name: str
    description: Optional[str] = None
    template: Optional[str] = None
    personality_traits: List[str] = Field(default_factory=list)
    

class ConversationContext(BaseModel):
    """Schema for conversation context"""
    conversation_id: str
    character_profiles: List[CharacterProfile]
    active_quests: List[QuestInfo] = Field(default_factory=list)
    recent_events: List[str] = Field(default_factory=list)
    

class AgentFunctionResult(BaseModel):
    """Schema for results from agent function calls"""
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None