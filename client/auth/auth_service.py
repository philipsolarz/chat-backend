#!/usr/bin/env python
# Authentication service handling user login, registration, and token management
from typing import Dict, Any, Optional, Tuple
import json
import time
from datetime import datetime

from client.api.base_service import BaseService, APIError
from client.game.state import game_state
from client.utils.config import config


class AuthService(BaseService):
    """Service for authentication-related API operations"""
    
    async def login(self, email: str, password: str) -> bool:
        """Log in with email and password"""
        try:
            payload = {
                "email": email,
                "password": password
            }
            
            response = await self.post("/auth/login", payload)
            
            # Store tokens and user info in game state
            game_state.access_token = response.get("access_token")
            game_state.refresh_token = response.get("refresh_token")
            game_state.current_user_id = response.get("user_id")
            game_state.user_email = response.get("email")
            
            # Save auth data for auto-login
            auth_data = {
                "access_token": game_state.access_token,
                "refresh_token": game_state.refresh_token,
                "user_id": game_state.current_user_id,
                "email": game_state.user_email,
                "timestamp": time.time()
            }
            config.save_auth(auth_data)
            
            # Get premium status
            await self.check_premium_status()
            
            return True
            
        except APIError as e:
            print(f"Login failed: {e.detail}")
            return False
        except Exception as e:
            print(f"Login error: {str(e)}")
            return False
    
    async def register(self, email: str, password: str, first_name: Optional[str] = None, last_name: Optional[str] = None) -> bool:
        """Register a new user"""
        try:
            payload = {
                "email": email,
                "password": password,
                "first_name": first_name,
                "last_name": last_name
            }
            
            response = await self.post("/auth/register", payload)
            
            # Store tokens and user info in game state
            game_state.access_token = response.get("access_token")
            game_state.refresh_token = response.get("refresh_token")
            game_state.current_user_id = response.get("user_id")
            game_state.user_email = response.get("email")
            
            # Save auth data for auto-login
            auth_data = {
                "access_token": game_state.access_token,
                "refresh_token": game_state.refresh_token,
                "user_id": game_state.current_user_id,
                "email": game_state.user_email,
                "timestamp": time.time()
            }
            config.save_auth(auth_data)
            
            # Get premium status
            await self.check_premium_status()
            
            return True
            
        except APIError as e:
            print(f"Registration failed: {e.detail}")
            return False
        except Exception as e:
            print(f"Registration error: {str(e)}")
            return False
    
    async def logout(self) -> bool:
        """Log out current user and clear tokens"""
        if not game_state.access_token:
            return True  # Already logged out
            
        try:
            await self.post("/auth/logout", {})
            
            # Clear auth data
            game_state.clear_auth()
            config.clear_auth()
            
            return True
            
        except APIError as e:
            print(f"Logout failed: {e.detail}")
            # Still clear local auth even if API call fails
            game_state.clear_auth()
            config.clear_auth()
            return True
        except Exception as e:
            print(f"Logout error: {str(e)}")
            # Still clear local auth even if API call fails
            game_state.clear_auth()
            config.clear_auth()
            return True
    
    async def refresh_token(self) -> bool:
        """Refresh the access token using the refresh token"""
        if not game_state.refresh_token:
            return False
            
        try:
            payload = {
                "refresh_token": game_state.refresh_token
            }
            
            response = await self.post("/auth/refresh", payload)
            
            # Update tokens in game state
            game_state.access_token = response.get("access_token")
            game_state.refresh_token = response.get("refresh_token")
            
            # Update saved auth data
            auth_data = config.load_auth()
            auth_data["access_token"] = game_state.access_token
            auth_data["refresh_token"] = game_state.refresh_token
            auth_data["timestamp"] = time.time()
            config.save_auth(auth_data)
            
            return True
            
        except APIError as e:
            print(f"Token refresh failed: {e.detail}")
            return False
        except Exception as e:
            print(f"Token refresh error: {str(e)}")
            return False
    
    async def check_premium_status(self) -> bool:
        """Check if current user has premium status"""
        if not game_state.access_token:
            game_state.is_premium = False
            return False
            
        try:
            response = await self.get("/payments/subscription")
            is_premium = response.get("is_premium", False)
            game_state.is_premium = is_premium
            return is_premium
            
        except Exception as e:
            print(f"Error checking premium status: {str(e)}")
            game_state.is_premium = False
            return False
    
    async def try_auto_login(self) -> bool:
        """Try to login using saved credentials"""
        auth_data = config.load_auth()
        
        if not auth_data or "refresh_token" not in auth_data:
            return False
            
        # Check if the saved token is recent (less than 7 days old)
        timestamp = auth_data.get("timestamp", 0)
        current_time = time.time()
        if current_time - timestamp > 7 * 24 * 60 * 60:  # 7 days
            return False
            
        # Use refresh token for auto-login
        game_state.refresh_token = auth_data.get("refresh_token")
        game_state.user_email = auth_data.get("email")
        game_state.current_user_id = auth_data.get("user_id")
        
        return await self.refresh_token()