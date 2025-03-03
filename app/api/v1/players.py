# app/api/v1/players.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Dict

from app.database import get_db
from app.schemas import PlayerBase, PlayerCreate, PlayerResponse, PlayerUpdate
from app.schemas import WorldList  # Assumed to be defined elsewhere
from app.schemas import CharacterList  # Assumed to be defined elsewhere
from app.api.auth import get_current_user
from app.services.player_service import PlayerService
from app.api.dependencies import get_service
from app.models.player import Player  # Our updated Player model

router = APIRouter()


@router.get("/me", response_model=PlayerResponse)
async def get_current_player_info(
    current_user: Player = Depends(get_current_user)
):
    """
    Get information about the current authenticated player.
    Returns the player's profile.
    """
    return current_user


@router.put("/me", response_model=PlayerResponse)
async def update_player_info(
    player_update: PlayerUpdate,
    current_user: Player = Depends(get_current_user),
    player_service: PlayerService = Depends(get_service(PlayerService))
):
    """
    Update current player information.
    Returns the updated player's profile.
    """
    # Check if the email is being updated and ensure it is not already registered
    if player_update.email and player_update.email != current_user.email:
        existing_player = player_service.get_player_by_email(player_update.email)
        if existing_player:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered"
            )
    
    update_data = player_update.dict(exclude_unset=True)
    updated_player = player_service.update_player(current_user.id, update_data)
    if not updated_player:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update player"
        )
    
    return updated_player


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_player_account(
    current_user: Player = Depends(get_current_user),
    player_service: PlayerService = Depends(get_service(PlayerService))
):
    """
    Delete the current player account.
    Returns no content on success.
    """
    try:
        player_service.delete_player(current_user.id)
        return None
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete player: {str(e)}"
        )


@router.get("/me/stats", response_model=Dict)
async def get_player_stats(
    current_user: Player = Depends(get_current_user),
    player_service: PlayerService = Depends(get_service(PlayerService))
):
    """
    Get statistics about the current player's activity.
    Returns counts of characters, worlds, etc.
    """
    stats = player_service.get_player_stats(current_user.id)
    return stats


@router.get("/me/worlds", response_model=WorldList)
async def get_player_worlds(
    current_user: Player = Depends(get_current_user),
    world_service = Depends(get_service("WorldService"))  # Inject WorldService dynamically
):
    """
    Get all worlds owned by the current player.
    Returns a list of the player's worlds.
    """
    worlds, total_count, total_pages = world_service.get_worlds(
        filters={'owner_id': current_user.id},
        page=1,
        page_size=100  # Get all (up to 100)
    )
    
    return {
        "items": worlds,
        "total": total_count,
        "page": 1,
        "page_size": 100,
        "total_pages": total_pages
    }


@router.get("/me/characters", response_model=CharacterList)
async def get_player_characters(
    current_user: Player = Depends(get_current_user),
    character_service = Depends(get_service("CharacterService"))  # Inject CharacterService dynamically
):
    """
    Get all characters owned by the current player.
    Returns a list of the player's characters.
    """
    characters, total_count, total_pages = character_service.get_characters(
        filters={'player_id': current_user.id},
        page=1,
        page_size=100  # Get all (up to 100)
    )
    
    return {
        "items": characters,
        "total": total_count,
        "page": 1,
        "page_size": 100,
        "total_pages": total_pages
    }
