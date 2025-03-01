#!/usr/bin/env python
# Authentication views with login and registration screens
import asyncio
from typing import Optional, Tuple, Dict, Any

from client.auth.auth_service import AuthService
from client.game.state import game_state
from client.ui.console import console, clear_screen, show_title, show_error, show_success
from client.ui.console import prompt_input, confirm_action, create_menu, display_loading


class AuthView:
    """User interface for authentication"""
    
    def __init__(self):
        self.auth_service = AuthService()
    
    async def show_auth_menu(self) -> bool:
        """Display authentication menu and handle user choice"""
        options = [
            ("login", "Login with existing account"),
            ("register", "Register new account"),
            ("auto", "Auto login with saved credentials")
        ]
        
        choice = create_menu("Welcome to RPG Chat", options, "Please select an option to continue:")
        
        if choice == "login":
            return await self.login_screen()
        elif choice == "register":
            return await self.registration_screen()
        elif choice == "auto":
            return await self.auto_login()
        else:
            return False
    
    async def login_screen(self) -> bool:
        """Show login form and process login"""
        show_title("Login", "Enter your account details to log in")
        
        email = prompt_input("Email", "Enter your email address:")
        password = prompt_input("Password", "Enter your password:", password=True)
        
        result = await display_loading(
            "Logging in...",
            self.auth_service.login(email, password)
        )
        
        if result:
            show_success(f"Successfully logged in as {email}")
            await asyncio.sleep(1)  # Pause to show the message
            return True
        else:
            show_error("Login failed. Please check your credentials and try again.")
            
            if confirm_action("Would you like to try again?"):
                return await self.login_screen()
            else:
                return False
    
    async def registration_screen(self) -> bool:
        """Show registration form and process registration"""
        show_title("Register New Account", "Create a new account to join the adventure")
        
        email = prompt_input("Email", "Enter your email address:")
        password = prompt_input("Password", "Create a password (min 8 characters):", password=True)
        confirm_password = prompt_input("Confirm", "Confirm your password:", password=True)
        
        if password != confirm_password:
            show_error("Passwords do not match. Please try again.")
            await asyncio.sleep(1)
            return await self.registration_screen()
        
        first_name = prompt_input("FirstName", "Enter your first name (optional):", default="")
        last_name = prompt_input("LastName", "Enter your last name (optional):", default="")
        
        result = await display_loading(
            "Creating account...",
            self.auth_service.register(email, password, first_name, last_name)
        )
        
        if result:
            show_success(f"Account created successfully for {email}")
            await asyncio.sleep(1)  # Pause to show the message
            return True
        else:
            show_error("Registration failed. The email may already be in use.")
            
            if confirm_action("Would you like to try again?"):
                return await self.registration_screen()
            else:
                return False
    
    async def auto_login(self) -> bool:
        """Try to login with saved credentials"""
        result = await display_loading(
            "Attempting auto-login...",
            self.auth_service.try_auto_login()
        )
        
        if result:
            show_success(f"Automatically logged in as {game_state.user_email}")
            await asyncio.sleep(1)  # Pause to show the message
            return True
        else:
            show_error("Auto-login failed. Please log in manually.")
            
            if confirm_action("Would you like to log in manually?"):
                return await self.login_screen()
            else:
                return False
    
    async def logout(self) -> bool:
        """Log out the current user"""
        if not game_state.is_authenticated():
            return True
            
        result = await display_loading(
            "Logging out...",
            self.auth_service.logout()
        )
        
        if result:
            show_success("Successfully logged out")
            return True
        else:
            show_error("Logout failed")
            return False
    
    async def show_account_menu(self) -> Optional[str]:
        """Display account management menu"""
        if not game_state.is_authenticated():
            show_error("Not logged in")
            return None
            
        premium_status = "Premium" if game_state.is_premium else "Free"
        subtitle = f"Logged in as: {game_state.user_email} ({premium_status})"
        
        options = [
            ("profile", "View profile"),
            ("premium", "Upgrade to Premium" if not game_state.is_premium else "Manage Premium subscription"),
            ("logout", "Logout"),
            ("back", "Back to main menu")
        ]
        
        return create_menu("Account Management", options, subtitle)