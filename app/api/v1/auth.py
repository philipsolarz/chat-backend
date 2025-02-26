# app/api/v1/auth.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.api import schemas
from app.services.auth_service import AuthService
from app.api.dependencies import get_service

router = APIRouter()


@router.post("/register", response_model=schemas.TokenResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    request: schemas.SignUpRequest,
    auth_service: AuthService = Depends(get_service(AuthService))
):
    """
    Register a new user with Supabase Auth
    
    Returns a token response including access_token and refresh_token
    """
    try:
        user, session = auth_service.sign_up(
            email=request.email,
            password=request.password,
            first_name=request.first_name,
            last_name=request.last_name
        )
        
        return {
            "access_token": session.access_token,
            "refresh_token": session.refresh_token,
            "user_id": user.id,
            "email": user.email
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Registration failed: {str(e)}"
        )


@router.post("/login", response_model=schemas.TokenResponse)
async def login_user(
    request: schemas.SignInRequest,
    auth_service: AuthService = Depends(get_service(AuthService))
):
    """
    Sign in an existing user
    
    Returns a token response including access_token and refresh_token
    """
    try:
        response = auth_service.sign_in(
            email=request.email,
            password=request.password
        )
        
        return response
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {str(e)}"
        )


@router.post("/refresh", response_model=schemas.TokenResponse)
async def refresh_token(
    request: schemas.RefreshTokenRequest,
    auth_service: AuthService = Depends(get_service(AuthService))
):
    """
    Refresh an authentication token
    
    Returns a new token response
    """
    try:
        response = auth_service.refresh_token(request.refresh_token)
        
        return response
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token refresh failed: {str(e)}"
        )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout_user(
    auth_service: AuthService = Depends(get_service(AuthService))
):
    """
    Sign out and invalidate the token
    
    Returns no content on success
    """
    try:
        auth_service.sign_out()
        return None
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Sign out failed: {str(e)}"
        )