# app/api/dependencies.py
from typing import Any, Type, Callable
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.player import Player
from app.models.character import Character
from app.models.agent import Agent
from app.models.conversation import Conversation, ConversationParticipant
from app.models.entity import Entity
from app.api.auth import get_current_user
from app.services.character_service import CharacterService
from app.services.agent_service import AgentService
from app.services.conversation_service import ConversationService
from app.services.entity_service import EntityService
from app.services.world_service import WorldService
from app.services.zone_service import ZoneService
from app.services.object_service import ObjectService  # Assumed to exist

def get_service(service_class: Type) -> Callable:
    """Factory function to create service dependencies with DB injection"""
    def _get_service(db: Session = Depends(get_db)):
        return service_class(db)
    return _get_service

def get_character_owner(
    character_id: str,
    current_user: Player = Depends(get_current_user),
    character_service: CharacterService = Depends(get_service(CharacterService))
) -> Character:
    """
    Verify that a character exists and belongs to the current user.
    """
    character = character_service.get_character(character_id)
    
    if not character:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Character not found"
        )
    
    if character.player_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this character"
        )
    
    return character

def get_conversation_access(
    conversation_id: str,
    current_user: Player = Depends(get_current_user),
    conversation_service: ConversationService = Depends(get_service(ConversationService))
) -> Conversation:
    """
    Verify that the current user has access to the conversation.
    Access is granted if the user is a participant.
    """
    conversation = conversation_service.get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
    if not conversation_service.check_user_access(current_user.id, conversation_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this conversation"
        )
    
    return conversation

def get_participant_owner(
    participant_id: str,
    current_user: Player = Depends(get_current_user),
    conversation_service: ConversationService = Depends(get_service(ConversationService))
) -> ConversationParticipant:
    """
    Verify that a conversation participant exists and is owned by the current user.
    """
    participant = conversation_service.get_participant(participant_id)
    
    if not participant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Participant not found"
        )
    
    if not participant.user_id or participant.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this participant"
        )
    
    return participant

def check_entity_ownership(
    entity_id: str,
    current_user: Player = Depends(get_current_user),
    entity_service: EntityService = Depends(get_service(EntityService)),
    world_service: WorldService = Depends(get_service(WorldService)),
    zone_service: ZoneService = Depends(get_service(ZoneService))
) -> Entity:
    """
    Verify that the current user owns the world containing the entity.
    Since entities always have a zone, we check the zone’s world ownership.
    """
    entity = entity_service.get_entity(entity_id)
    if not entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entity not found"
        )
    
    # Retrieve the zone for this entity.
    zone = zone_service.get_zone(entity.zone_id)
    if not zone:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Zone not found"
        )
        
    # Retrieve the world owning that zone.
    world = world_service.get_world(zone.world_id)
    if not world or world.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the world owner can manage this entity"
        )
    
    return entity

def check_object_ownership(
    object_id: str,
    current_user: Player = Depends(get_current_user),
    object_service: ObjectService = Depends(get_service(ObjectService)),
    world_service: WorldService = Depends(get_service(WorldService)),
    zone_service: ZoneService = Depends(get_service(ZoneService))
) -> Any:
    """
    Verify that the current user owns the world containing the object.
    Objects inherit from Entity and always have a zone, so we check the zone's world.
    """
    obj = object_service.get_object(object_id)
    if not obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Object not found"
        )
    
    # Retrieve the zone for this object.
    zone = zone_service.get_zone(obj.zone_id)
    if not zone:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Zone not found"
        )
            
    # Retrieve the world owning that zone.
    world = world_service.get_world(zone.world_id)
    if not world or world.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the world owner can manage this object"
        )
    
    return obj
