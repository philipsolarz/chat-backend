# app/services/auth_service.py
from typing import Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from fastapi import Depends, HTTPException, status
import jwt
from datetime import datetime, timedelta

from app.database import supabase, get_db
from app.models.user import User
from app.config import get_settings

settings = get_settings()


class AuthService:
    """Service for handling authentication using Supabase"""
    
    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()
    
    def sign_up(self, email: str, password: str, first_name: Optional[str] = None, last_name: Optional[str] = None) -> Tuple[User, Dict[str, Any]]:
        """Register a new user with Supabase Auth and create User record"""
        try:
            # Register user with Supabase Auth
            auth_response = supabase.auth.sign_up({
                "email": email,
                "password": password
            })
            
            user_id = auth_response.user.id
            
            # Create user record in our database
            db_user = User(
                id=user_id,
                email=email,
                first_name=first_name,
                last_name=last_name
            )
            
            self.db.add(db_user)
            self.db.commit()
            self.db.refresh(db_user)
            
            return db_user, auth_response.session
        
        except Exception as e:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Registration failed: {str(e)}"
            )
    
    def sign_in(self, email: str, password: str) -> Dict[str, Any]:
        """Sign in a user with Supabase Auth"""
        try:
            # Sign in with Supabase Auth
            auth_response = supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            
            # Get user from our database
            user = self.get_user_by_id(auth_response.user.id)
            
            if not user:
                # User exists in Supabase Auth but not in our DB, create record
                user = User(
                    id=auth_response.user.id,
                    email=email
                )
                self.db.add(user)
                self.db.commit()
            
            return {
                "access_token": auth_response.session.access_token,
                "refresh_token": auth_response.session.refresh_token,
                "user_id": auth_response.user.id,
                "email": email
            }
        
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Authentication failed: {str(e)}"
            )
    
    def refresh_token(self, refresh_token: str) -> Dict[str, Any]:
        """Refresh an authentication token"""
        try:
            # Refresh token with Supabase Auth
            response = supabase.auth.refresh_session(refresh_token)
            
            return {
                "access_token": response.session.access_token,
                "refresh_token": response.session.refresh_token,
                "user_id": response.user.id
            }
        
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Token refresh failed: {str(e)}"
            )
    
    def sign_out(self, access_token: str) -> bool:
        """Sign out a user and invalidate their token"""
        try:
            # Sign out with Supabase Auth
            supabase.auth.sign_out()
            return True
        
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Sign out failed: {str(e)}"
            )
    
    def verify_token(self, token: str) -> Dict[str, Any]:
        """Verify a JWT token and return the user ID"""
        try:
            # Verify with Supabase JWT secret
            payload = jwt.decode(
                token, 
                self.settings.SUPABASE_JWT_SECRET, 
                algorithms=["HS256"]
            )
            
            # Extract user ID from payload
            user_id = payload.get("sub")
            
            if not user_id:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token"
                )
            
            return payload
        
        except jwt.PyJWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
    
    def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Get a user by ID from our database"""
        return self.db.query(User).filter(User.id == user_id).first()
    
    def get_user_by_email(self, email: str) -> Optional[User]:
        """Get a user by email from our database"""
        return self.db.query(User).filter(User.email == email).first()