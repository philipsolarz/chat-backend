# app/api/auth.py
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.services.auth_service import AuthService
from app.models.user import User

# Setup security scheme
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security), 
    db: Session = Depends(get_db)
) -> User:
    """
    Dependency to get the current authenticated user from a JWT token
    Uses Supabase authentication
    """
    auth_service = AuthService(db)
    
    try:
        # Verify token with Supabase
        payload = auth_service.verify_token(credentials.credentials)
        
        # Extract user ID
        user_id = payload.get("sub")
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials"
            )
        
        # Get user from database
        user = auth_service.get_user_by_id(user_id)
        
        if not user:
            # Create user record if it doesn't exist but token is valid
            # This can happen if the user was created through Supabase Auth but not in our DB
            user_email = payload.get("email")
            if not user_email:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid user data in token"
                )
            
            user = User(id=user_id, email=user_email)
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