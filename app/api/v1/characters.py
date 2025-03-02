# app/api/v1/characters.py
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database import get_db
from app.api import schemas
from app.api.auth import get_current_user
from app.api.dependencies import get_service, get_character_owner
from app.api.premium import require_premium, check_character_limit, check_public_character_permission
from app.services.character_service import CharacterService
from app.services.usage_service import UsageService
from app.models.player import User
from app.models.character import Character

router = APIRouter()


@router.post("/", response_model=schemas.CharacterResponse, status_code=status.HTTP_201_CREATED)
async def create_character(
    character: schemas.CharacterCreate,
    user_with_capacity: User = Depends(check_character_limit),
    character_service: CharacterService = Depends(get_service(CharacterService)),
    usage_service: UsageService = Depends(get_service(UsageService))
):
    """
    Create a new character for the current user
    
    This endpoint checks character limits before creating
    Returns the created character
    """
    # If trying to make public, check if user has premium
    if character.is_public and not usage_service.can_make_character_public(user_with_capacity.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Making characters public is a premium feature"
        )
    
    # Track character creation for usage metrics
    usage_service.track_character_created(user_with_capacity.id)
    
    # Create the character
    return character_service.create_character(
        user_id=user_with_capacity.id,
        name=character.name,
        description=character.description,
        is_public=character.is_public
    )


@router.get("/", response_model=schemas.CharacterList)
async def list_characters(
    name: Optional[str] = None,
    is_public: Optional[bool] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = Query("name"),
    sort_desc: bool = Query(False),
    current_user: User = Depends(get_current_user),
    character_service: CharacterService = Depends(get_service(CharacterService))
):
    """
    Get all characters belonging to the current user with pagination and filtering
    
    Returns a paginated list of characters
    """
    filters = {'user_id': current_user.id}
    
    if name:
        filters['name'] = name
    
    if is_public is not None:
        filters['is_public'] = is_public
    
    characters, total_count, total_pages = character_service.get_characters(
        filters=filters,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_desc=sort_desc
    )
    
    return {
        "items": characters,
        "total": total_count,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages
    }


@router.get("/public", response_model=schemas.CharacterList)
async def list_public_characters(
    name: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = Query("name"),
    sort_desc: bool = Query(False),
    current_user: User = Depends(get_current_user),
    character_service: CharacterService = Depends(get_service(CharacterService))
):
    """
    Get all public characters available for agents
    
    Returns a paginated list of public characters
    """
    filters = {'is_public': True}
    
    if name:
        filters['name'] = name
    
    characters, total_count, total_pages = character_service.get_characters(
        filters=filters,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_desc=sort_desc
    )
    
    return {
        "items": characters,
        "total": total_count,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages
    }


@router.get("/{character_id}", response_model=schemas.CharacterResponse)
async def get_character(
    character_id: str = Path(..., title="The ID of the character to get"),
    current_user: User = Depends(get_current_user),
    character_service: CharacterService = Depends(get_service(CharacterService))
):
    """
    Get a specific character by ID
    
    If the character is public, any user can access it.
    If it's private, only the owner can access it.
    """
    character = character_service.get_character(character_id)
    
    if not character:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Character not found"
        )
    
    # Check access permissions
    if not character.is_public and character.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to view this character"
        )
    
    return character


@router.put("/{character_id}", response_model=schemas.CharacterResponse)
async def update_character(
    character_update: schemas.CharacterUpdate,
    character: Character = Depends(get_character_owner),
    character_service: CharacterService = Depends(get_service(CharacterService)),
    usage_service: UsageService = Depends(get_service(UsageService))
):
    """
    Update a character belonging to the current user
    
    Returns the updated character
    """
    # Check if trying to make public and has permission
    if character_update.is_public is not None and character_update.is_public and not character.is_public:
        if not usage_service.can_make_character_public(character.user_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Making characters public is a premium feature"
            )
    
    update_data = character_update.dict(exclude_unset=True)
    
    updated_character = character_service.update_character(character.id, update_data)
    if not updated_character:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update character"
        )
    
    return updated_character


@router.delete("/{character_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_character(
    character: Character = Depends(get_character_owner),
    character_service: CharacterService = Depends(get_service(CharacterService))
):
    """
    Delete a character belonging to the current user
    
    Returns no content on success
    """
    success = character_service.delete_character(character.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete character"
        )
    
    return None


@router.get("/search/", response_model=schemas.CharacterList)
async def search_characters(
    query: str = Query(..., min_length=1),
    include_public: bool = Query(False, title="Include public characters in results"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    character_service: CharacterService = Depends(get_service(CharacterService))
):
    """
    Search for characters by name or description
    
    Returns a paginated list of matching characters
    """
    characters, total_count, total_pages = character_service.search_characters(
        query=query,
        include_public=include_public,
        user_id=current_user.id,
        page=page,
        page_size=page_size
    )
    
    return {
        "items": characters,
        "total": total_count,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages
    }


@router.post("/{character_id}/public", response_model=schemas.CharacterResponse)
async def make_character_public(
    character: Character = Depends(get_character_owner),
    premium_user: User = Depends(check_public_character_permission), # This checks premium status
    character_service: CharacterService = Depends(get_service(CharacterService))
):
    """
    Make a character publicly available for agents (Premium Feature)
    
    Returns the updated character
    """
    updated_character = character_service.make_character_public(character.id)
    if not updated_character:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update character"
        )
    
    return updated_character


@router.post("/{character_id}/private", response_model=schemas.CharacterResponse)
async def make_character_private(
    character: Character = Depends(get_character_owner),
    character_service: CharacterService = Depends(get_service(CharacterService))
):
    """
    Make a character private (only for owner)
    
    Returns the updated character
    """
    updated_character = character_service.make_character_private(character.id)
    if not updated_character:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update character"
        )
    
    return updated_character