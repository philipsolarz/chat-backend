# app/api/v1/users.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.api import schemas
from app.api.auth import get_current_user
from app.services.user_service import UserService
from app.api.dependencies import get_service
from app.models.player import User

router = APIRouter()


@router.get("/me", response_model=schemas.UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """
    Get information about the current authenticated user
    
    Returns the user profile
    """
    return current_user


@router.put("/me", response_model=schemas.UserResponse)
async def update_user_info(
    user_update: schemas.UserUpdate,
    current_user: User = Depends(get_current_user),
    user_service: UserService = Depends(get_service(UserService))
):
    """
    Update current user information
    
    Returns the updated user profile
    """
    # Check if email is being updated and already exists
    if user_update.email and user_update.email != current_user.email:
        existing_user = user_service.get_user_by_email(user_update.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered"
            )
    
    update_data = user_update.dict(exclude_unset=True)
    
    updated_user = user_service.update_user(current_user.id, update_data)
    if not updated_user:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user"
        )
    
    return updated_user


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_account(
    current_user: User = Depends(get_current_user),
    user_service: UserService = Depends(get_service(UserService))
):
    """
    Delete current user account
    
    Returns no content on success
    """
    try:
        user_service.delete_user(current_user.id)
        return None
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete user: {str(e)}"
        )


@router.get("/me/stats", response_model=dict)
async def get_user_stats(
    current_user: User = Depends(get_current_user),
    user_service: UserService = Depends(get_service(UserService))
):
    """
    Get statistics about the current user's activity
    
    Returns counts of characters, conversations, etc.
    """
    stats = user_service.get_user_stats(current_user.id)
    return stats