# app/services/user_service.py
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
from fastapi import HTTPException, status

from app.models.player import User
from app.database import supabase


class UserService:
    """Service for handling user operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_user(self, user_id: str) -> Optional[User]:
        """Get a user by ID"""
        return self.db.query(User).filter(User.id == user_id).first()
    
    def get_user_by_email(self, email: str) -> Optional[User]:
        """Get a user by email"""
        return self.db.query(User).filter(User.email == email).first()
    
    def create_user(self, user_id: str, email: str, first_name: Optional[str] = None, last_name: Optional[str] = None) -> User:
        """
        Create a user in our database (should be called after Supabase Auth registration)
        """
        # Check if user already exists
        existing_user = self.get_user(user_id)
        if existing_user:
            return existing_user
        
        # Create new user
        user = User(
            id=user_id,
            email=email,
            first_name=first_name,
            last_name=last_name
        )
        
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        
        return user
    
    def update_user(self, user_id: str, update_data: Dict[str, Any]) -> Optional[User]:
        """Update user information"""
        user = self.get_user(user_id)
        if not user:
            return None
        
        # Update only the fields provided
        for key, value in update_data.items():
            if hasattr(user, key):
                setattr(user, key, value)
        
        self.db.commit()
        self.db.refresh(user)
        
        return user
    
    def delete_user(self, user_id: str) -> bool:
        """
        Delete a user from our database and Supabase Auth
        """
        user = self.get_user(user_id)
        if not user:
            return False
        
        try:
            # Delete from our database
            self.db.delete(user)
            self.db.commit()
            
            # Delete from Supabase Auth
            # Note: This will require admin privileges in Supabase
            supabase.auth.admin.delete_user(user_id)
            
            return True
        
        except Exception as e:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to delete user: {str(e)}"
            )
    
    def search_users(self, query: str, limit: int = 10) -> List[User]:
        """Search for users by name or email"""
        return self.db.query(User).filter(
            (User.email.ilike(f"%{query}%")) |
            (User.first_name.ilike(f"%{query}%")) |
            (User.last_name.ilike(f"%{query}%"))
        ).limit(limit).all()