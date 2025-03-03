# app/api/auth.py
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.services.auth_service import AuthService
from app.models.player import Player

# Setup security scheme
security = HTTPBearer()

async def get_access_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> str:
    """
    Dependency to extract and optionally verify the access token.
    Here we verify the token using the AuthService.
    """
    auth_service = AuthService(db)
    try:
        # Verify token; if invalid, an exception will be raised.
        auth_service.verify_token(credentials.credentials)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid access token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"}
        )
    return credentials.credentials

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security), 
    db: Session = Depends(get_db)
) -> Player:
    """
    Dependency to get the current authenticated user from a JWT token.
    Uses Supabase authentication.
    """
    auth_service = AuthService(db)
    
    try:
        # Verify token using AuthService
        payload = auth_service.verify_token(credentials.credentials)
        
        # Extract user ID from payload
        user_id = payload.get("sub")
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials"
            )
        
        # Retrieve user from database
        user = auth_service.get_user_by_id(user_id)
        
        if not user:
            # Create the user record if it doesn't exist,
            # which can occur if the user exists in Supabase but not locally.
            user_email = payload.get("email")
            if not user_email:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid user data in token"
                )
            
            user = Player(id=user_id, email=user_email)
            db.add(user)
            db.commit()
            db.refresh(user)
        
        return user
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"}
        )
