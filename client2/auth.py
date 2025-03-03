# Authentication functions for RPG Client
import asyncio
from typing import Dict, Any, Optional

from client2 import api, ui
from client2.config import config
from client2.state import game_state

async def login_flow() -> bool:
    """Handle user login"""
    email = ui.prompt("Email")
    password = ui.prompt("Password", password=True)
    
    ui.show_info("Logging in...")
    result = api.login(email, password)
    
    if result:
        # Store auth data
        game_state.set_auth(result)
        
        # Save auth for later
        config.save_auth({
            "access_token": game_state.access_token,
            "refresh_token": game_state.refresh_token,
            "user_id": game_state.user_id,
            "email": game_state.user_email
        })
        
        ui.show_success(f"Successfully logged in as {email}")
        return True
    
    return False

async def register_flow() -> bool:
    """Handle user registration"""
    email = ui.prompt("Email")
    password = ui.prompt("Password", password=True)
    confirm_pwd = ui.prompt("Confirm Password", password=True)
    
    if password != confirm_pwd:
        ui.show_error("Passwords do not match")
        return False
    
    first_name = ui.prompt("First Name (optional)", required=False)
    last_name = ui.prompt("Last Name (optional)", required=False)
    
    ui.show_info("Creating account...")
    result = api.register(email, password, first_name, last_name)
    
    if result:
        # Store auth data
        game_state.set_auth(result)
        
        # Save auth for later
        config.save_auth({
            "access_token": game_state.access_token,
            "refresh_token": game_state.refresh_token,
            "user_id": game_state.user_id,
            "email": game_state.user_email
        })
        
        ui.show_success(f"Account created successfully for {email}")
        return True
    
    return False

async def auto_login() -> bool:
    """Try to login with saved credentials"""
    auth_data = config.load_auth()
    
    if not auth_data:
        return False
    
    # Set auth data in state
    game_state.set_auth(auth_data)
    
    # Test if token is valid with user info endpoint
    try:
        me_response = api.get_character(auth_data.get("user_id", ""))
        if me_response:
            ui.show_success(f"Automatically logged in as {game_state.user_email}")
            return True
    except:
        pass
    
    # Try to refresh token if direct validation failed
    if api.refresh_token():
        ui.show_success(f"Session refreshed for {game_state.user_email}")
        return True
    
    # Clear invalid auth data
    game_state.clear_auth()
    config.clear_auth()
    return False

async def logout() -> bool:
    """Log out current user"""
    if not game_state.is_authenticated():
        return True
    
    # Clear local auth data
    game_state.clear_auth()
    config.clear_auth()
    
    ui.show_success("Logged out successfully")
    return True

async def authenticate() -> bool:
    """Main authentication flow"""
    # Try auto-login first if not disabled
    args = config.parse_args()
    
    if not args.no_auto_login:
        if await auto_login():
            return True
    
    # Show authentication menu
    auth_options = [
        "Login with existing account",
        "Create new account"
    ]
    
    while True:
        choice = ui.show_menu("Authentication", auth_options, "Welcome to RPG Chat")
        
        if not choice:
            return False
        
        if choice == "1":  # Login
            if await login_flow():
                return True
        elif choice == "2":  # Register
            if await register_flow():
                return True
                
        # Ask if they want to try again or exit
        if not ui.confirm("Would you like to try again?"):
            return False