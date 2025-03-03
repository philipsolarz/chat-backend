# app/services/auth_service.py
from typing import Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
import jwt
from datetime import datetime, timedelta

from app.database import supabase, get_db
from app.models.player import Player
from app.config import get_settings

settings = get_settings()

class AuthService:
    """Service for handling authentication using Supabase,
    integrated with our updated Player model.
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()
    
    def sign_up(
        self, 
        email: str, 
        password: str, 
        first_name: Optional[str] = None, 
        last_name: Optional[str] = None
    ) -> Tuple[Player, Dict[str, Any]]:
        """
        Register a new user with Supabase Auth and create a Player record.
        """
        try:
            # Register user with Supabase Auth
            auth_response = supabase.auth.sign_up({
                "email": email,
                "password": password
            })
            
            # Extract user ID from Supabase response
            user_id = auth_response.user.id
            
            # Create a new Player record using our updated model
            db_user = Player(
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
        """
        Sign in a user with Supabase Auth and ensure a corresponding Player record exists.
        """
        try:
            auth_response = supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            
            # Retrieve user from our database by ID
            user = self.get_user_by_id(auth_response.user.id)
            if not user:
                # Create a new Player record if one doesn't exist
                user = Player(
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
        """
        Refresh an authentication token using Supabase Auth.
        """
        try:
            response = supabase.auth.refresh_session(refresh_token)
            return {
                "access_token": response.session.access_token,
                "refresh_token": response.session.refresh_token,
                "user_id": response.user.id,
                "email": response.user.email
            }
        
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Token refresh failed: {str(e)}"
            )
    
    def sign_out(self, access_token: str) -> bool:
        """
        Sign out a user and invalidate their token.
        """
        try:
            supabase.auth.sign_out()
            return True
        
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Sign out failed: {str(e)}"
            )
    
    def verify_token(self, token: str) -> Dict[str, Any]:
        """
        Verify a JWT token using the Supabase JWT secret and return its payload.
        """
        try:
            payload = jwt.decode(
                token, 
                self.settings.SUPABASE_JWT_SECRET, 
                algorithms=["HS256"],
                audience="authenticated"
            )
            
            user_id = payload.get("sub")
            if not user_id:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token: missing subject"
                )
            
            return payload
        
        except jwt.PyJWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
    
    def get_user_by_id(self, user_id: str) -> Optional[Player]:
        """
        Retrieve a Player record by ID.
        """
        return self.db.query(Player).filter(Player.id == user_id).first()
    
    def get_user_by_email(self, email: str) -> Optional[Player]:
        """
        Retrieve a Player record by email.
        """
        return self.db.query(Player).filter(Player.email == email).first()
    
    def verify_email_token(self, token_hash: str, type: str) -> bool:
        """
        Verify an email verification token using Supabase Auth.
        """
        try:
            supabase.auth.verify_otp({
                "token_hash": token_hash,
                "type": type
            })
            return True
        
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Email verification failed: {str(e)}"
            )
    
    def resend_verification_email(self, email: str, redirect_url: Optional[str] = None) -> Dict[str, Any]:
        """
        Resend a verification email to a user.
        """
        try:
            response = supabase.auth.resend_email({
                "email": email, 
                "type": "signup",
                "options": {"redirect_to": redirect_url} if redirect_url else None
            })
            return response
        
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to send verification email: {str(e)}"
            )
