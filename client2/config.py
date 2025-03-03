# Configuration management for RPG Client
import os
import json
import argparse
from typing import Dict, Any, Optional

# Default configuration
DEFAULT_API_URL = "http://localhost:8000/api/v1"
DEFAULT_WS_URL = "ws://localhost:8000/ws"

class Config:
    """Configuration management for the RPG Chat client"""
    
    def __init__(self):
        # Default settings
        self.api_url = DEFAULT_API_URL
        self.ws_url = DEFAULT_WS_URL
        
        # Config paths
        self.config_dir = os.path.expanduser("~/.rpgclient")
        self.config_file = os.path.join(self.config_dir, "config.json")
        self.auth_file = os.path.join(self.config_dir, "auth.json")
        
        # Ensure config directory exists
        os.makedirs(self.config_dir, exist_ok=True)
        
        # Load existing configuration
        self.load_config()
    
    def load_config(self) -> None:
        """Load configuration from file if it exists"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    config_data = json.load(f)
                    self.api_url = config_data.get("api_url", self.api_url)
                    self.ws_url = config_data.get("ws_url", self.ws_url)
        except Exception as e:
            print(f"Error loading config: {e}")
    
    def save_config(self) -> None:
        """Save current configuration to file"""
        try:
            config_data = {
                "api_url": self.api_url,
                "ws_url": self.ws_url
            }
            
            with open(self.config_file, 'w') as f:
                json.dump(config_data, f, indent=2)
        except Exception as e:
            print(f"Error saving config: {e}")
    
    def load_auth(self) -> Optional[Dict[str, Any]]:
        """Load saved authentication data if it exists"""
        try:
            if os.path.exists(self.auth_file):
                with open(self.auth_file, 'r') as f:
                    return json.load(f)
            return None
        except Exception as e:
            print(f"Error loading auth data: {e}")
            return None
    
    def save_auth(self, auth_data: Dict[str, Any]) -> None:
        """Save authentication data for auto-login"""
        try:
            with open(self.auth_file, 'w') as f:
                json.dump(auth_data, f, indent=2)
        except Exception as e:
            print(f"Error saving auth data: {e}")
    
    def clear_auth(self) -> None:
        """Clear saved authentication data"""
        if os.path.exists(self.auth_file):
            try:
                os.remove(self.auth_file)
            except Exception as e:
                print(f"Error removing auth file: {e}")
    
    def parse_args(self) -> argparse.Namespace:
        """Parse command line arguments"""
        parser = argparse.ArgumentParser(description='RPG Chat Client')
        parser.add_argument('--api-url', help='API URL', default=self.api_url)
        parser.add_argument('--ws-url', help='WebSocket URL', default=self.ws_url)
        parser.add_argument('--no-auto-login', action='store_true', help='Disable auto-login')
        
        args = parser.parse_args()
        
        # Update config with command line values
        self.api_url = args.api_url
        self.ws_url = args.ws_url
        
        # Save updated config
        self.save_config()
        
        return args

# Global config instance
config = Config()