# app/services/player_service.py
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
from fastapi import HTTPException, status

from app.models.player import Player
from app.database import supabase


class PlayerService:
    """Service for handling player operations (renamed from UserService)"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_player(self, player_id: str) -> Optional[Player]:
        """Get a player by ID"""
        return self.db.query(Player).filter(Player.id == player_id).first()
    
    def get_player_by_email(self, email: str) -> Optional[Player]:
        """Get a player by email"""
        return self.db.query(Player).filter(Player.email == email).first()
    
    def create_player(self, player_id: str, email: str, first_name: Optional[str] = None, last_name: Optional[str] = None) -> Player:
        """
        Create a player in our database (should be called after Supabase Auth registration)
        """
        # Check if player already exists
        existing_player = self.get_player(player_id)
        if existing_player:
            return existing_player
        
        # Create new player
        player = Player(
            id=player_id,
            email=email,
            first_name=first_name,
            last_name=last_name
        )
        
        self.db.add(player)
        self.db.commit()
        self.db.refresh(player)
        
        return player
    
    def update_player(self, player_id: str, update_data: Dict[str, Any]) -> Optional[Player]:
        """Update player information"""
        player = self.get_player(player_id)
        if not player:
            return None
        
        # Update only the fields provided
        for key, value in update_data.items():
            if hasattr(player, key):
                setattr(player, key, value)
        
        self.db.commit()
        self.db.refresh(player)
        
        return player
    
    def delete_player(self, player_id: str) -> bool:
        """
        Delete a player from our database and Supabase Auth
        """
        player = self.get_player(player_id)
        if not player:
            return False
        
        try:
            # Delete from our database
            self.db.delete(player)
            self.db.commit()
            
            # Delete from Supabase Auth
            # Note: This will require admin privileges in Supabase
            supabase.auth.admin.delete_user(player_id)
            
            return True
        
        except Exception as e:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to delete player: {str(e)}"
            )
    
    def search_players(self, query: str, limit: int = 10) -> List[Player]:
        """Search for players by name or email"""
        return self.db.query(Player).filter(
            (Player.email.ilike(f"%{query}%")) |
            (Player.first_name.ilike(f"%{query}%")) |
            (Player.last_name.ilike(f"%{query}%"))
        ).limit(limit).all()
        
    def get_player_stats(self, player_id: str) -> Dict[str, Any]:
        """
        Get statistics about a player's activity
        
        Returns counts of characters, worlds, etc.
        """
        player = self.get_player(player_id)
        if not player:
            return {
                "character_count": 0,
                "world_count": 0,
                "is_premium": False
            }
        
        # Count characters
        from app.models.character import Character
        character_count = self.db.query(Character).filter(
            Character.player_id == player_id
        ).count()
        
        # Count owned worlds
        from app.models.world import World
        world_count = self.db.query(World).filter(
            World.owner_id == player_id
        ).count()
        
        # Return stats
        return {
            "character_count": character_count,
            "world_count": world_count,
            "is_premium": player.is_premium
        }