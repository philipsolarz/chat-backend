#!/usr/bin/env python
# Configuration for RPG Chat client
import os
import json
from typing import Dict, Any, Optional
import argparse


class Config:
    """Configuration management for the RPG Chat client"""
    
    # Default values
    DEFAULT_API_URL = "http://localhost:8000/api/v1"
    DEFAULT_WS_URL = "ws://localhost:8000/ws"
    
    def __init__(self):
        self.api_url = self.DEFAULT_API_URL
        self.ws_url = self.DEFAULT_WS_URL
        self.config_file = os.path.expanduser("~/.rpgchat/config.json")
        self.auth_file = os.path.expanduser("~/.rpgchat/auth.json")
        
        # Ensure config directory exists
        os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
        
        # Load config if exists
        self.load_config()
    
    def load_config(self):
        """Load configuration from file if it exists"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    config_data = json.load(f)
                    self.api_url = config_data.get('api_url', self.DEFAULT_API_URL)
                    self.ws_url = config_data.get('ws_url', self.DEFAULT_WS_URL)
        except Exception as e:
            print(f"Error loading config: {e}")
    
    def save_config(self):
        """Save current configuration to file"""
        try:
            config_data = {
                'api_url': self.api_url,
                'ws_url': self.ws_url
            }
            with open(self.config_file, 'w') as f:
                json.dump(config_data, f, indent=2)
        except Exception as e:
            print(f"Error saving config: {e}")
    
    def load_auth(self) -> Dict[str, Any]:
        """Load saved authentication data if it exists"""
        try:
            if os.path.exists(self.auth_file):
                with open(self.auth_file, 'r') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            print(f"Error loading auth data: {e}")
            return {}
    
    def save_auth(self, auth_data: Dict[str, Any]):
        """Save authentication data for auto-login"""
        try:
            with open(self.auth_file, 'w') as f:
                json.dump(auth_data, f, indent=2)
        except Exception as e:
            print(f"Error saving auth data: {e}")
    
    def clear_auth(self):
        """Clear saved authentication data"""
        if os.path.exists(self.auth_file):
            os.remove(self.auth_file)
    
    def parse_args(self):
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