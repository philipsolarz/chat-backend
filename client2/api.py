# API client for RPG Client
import requests
from typing import Dict, Any, List, Optional

from client2.state import game_state
from client2.config import config
from client2 import ui

class APIError(Exception):
    """Exception raised for API errors"""
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"API Error ({status_code}): {detail}")

def get_headers() -> Dict[str, str]:
    """Get common headers for API requests"""
    headers = {
        "Content-Type": "application/json"
    }
    
    if game_state.access_token:
        headers["Authorization"] = f"Bearer {game_state.access_token}"
        
    return headers

def handle_response(response: requests.Response) -> Dict[str, Any]:
    """Process API response and handle errors"""
    if response.status_code >= 200 and response.status_code < 300:
        if response.status_code == 204:  # No content
            return {}
            
        try:
            return response.json()
        except:
            return {"message": response.text}
    else:
        try:
            error_data = response.json()
            detail = error_data.get("detail", "Unknown error")
        except:
            detail = response.text or "Unknown error"
            
        raise APIError(response.status_code, detail)

# Authentication API

def login(email: str, password: str) -> Optional[Dict[str, Any]]:
    """Login with email and password"""
    try:
        payload = {
            "email": email,
            "password": password
        }
        
        response = requests.post(f"{config.api_url}/auth/login", json=payload)
        data = handle_response(response)
        return data
    except APIError as e:
        ui.show_error(f"Login failed: {e.detail}")
        return None
    except Exception as e:
        ui.show_error(f"Login error: {str(e)}")
        return None

def register(email: str, password: str, first_name: Optional[str] = None, last_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Register a new user"""
    try:
        payload = {
            "email": email,
            "password": password
        }
        
        if first_name:
            payload["first_name"] = first_name
            
        if last_name:
            payload["last_name"] = last_name
        
        response = requests.post(f"{config.api_url}/auth/register", json=payload)
        data = handle_response(response)
        return data
    except APIError as e:
        ui.show_error(f"Registration failed: {e.detail}")
        return None
    except Exception as e:
        ui.show_error(f"Registration error: {str(e)}")
        return None

def refresh_token() -> bool:
    """Refresh the access token"""
    if not game_state.refresh_token:
        return False
        
    try:
        payload = {
            "refresh_token": game_state.refresh_token
        }
        
        response = requests.post(f"{config.api_url}/auth/refresh", json=payload)
        data = handle_response(response)
        
        if "access_token" in data:
            game_state.access_token = data["access_token"]
            if "refresh_token" in data:
                game_state.refresh_token = data["refresh_token"]
            return True
        return False
    except APIError:
        return False
    except Exception:
        return False

# World API

def get_worlds() -> List[Dict[str, Any]]:
    """Get list of accessible worlds"""
    try:
        response = requests.get(f"{config.api_url}/worlds/", headers=get_headers())
        data = handle_response(response)
        return data.get("items", [])
    except APIError as e:
        ui.show_error(f"Failed to get worlds: {e.detail}")
        return []
    except Exception as e:
        ui.show_error(f"Error getting worlds: {str(e)}")
        return []

def get_starter_worlds() -> List[Dict[str, Any]]:
    """Get list of starter worlds"""
    try:
        response = requests.get(f"{config.api_url}/worlds/starter", headers=get_headers())
        data = handle_response(response)
        return data.get("items", [])
    except APIError as e:
        ui.show_error(f"Failed to get starter worlds: {e.detail}")
        return []
    except Exception as e:
        ui.show_error(f"Error getting starter worlds: {str(e)}")
        return []

def create_world(name: str, description: Optional[str] = None, genre: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Create a new world"""
    try:
        payload = {
            "name": name,
            "is_public": False
        }
        
        if description:
            payload["description"] = description
            
        if genre:
            payload["genre"] = genre
        
        response = requests.post(f"{config.api_url}/worlds/", json=payload, headers=get_headers())
        return handle_response(response)
    except APIError as e:
        ui.show_error(f"Failed to create world: {e.detail}")
        return None
    except Exception as e:
        ui.show_error(f"Error creating world: {str(e)}")
        return None

def get_world(world_id: str) -> Optional[Dict[str, Any]]:
    """Get details of a specific world"""
    try:
        response = requests.get(f"{config.api_url}/worlds/{world_id}", headers=get_headers())
        return handle_response(response)
    except APIError as e:
        ui.show_error(f"Failed to get world: {e.detail}")
        return None
    except Exception as e:
        ui.show_error(f"Error getting world: {str(e)}")
        return None

# Character API

def get_characters() -> List[Dict[str, Any]]:
    """Get list of user's characters"""
    try:
        response = requests.get(f"{config.api_url}/characters/", headers=get_headers())
        data = handle_response(response)
        return data.get("items", [])
    except APIError as e:
        ui.show_error(f"Failed to get characters: {e.detail}")
        return []
    except Exception as e:
        ui.show_error(f"Error getting characters: {str(e)}")
        return []

def create_character(name: str, world_id: str, description: Optional[str] = None, zone_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Create a new character"""
    try:
        payload = {
            "name": name,
            "world_id": world_id
        }
        
        if description:
            payload["description"] = description
            
        if zone_id:
            payload["zone_id"] = zone_id
        
        response = requests.post(f"{config.api_url}/characters/", json=payload, headers=get_headers())
        return handle_response(response)
    except APIError as e:
        ui.show_error(f"Failed to create character: {e.detail}")
        return None
    except Exception as e:
        ui.show_error(f"Error creating character: {str(e)}")
        return None

def get_character(character_id: str) -> Optional[Dict[str, Any]]:
    """Get details of a specific character"""
    try:
        response = requests.get(f"{config.api_url}/characters/{character_id}", headers=get_headers())
        return handle_response(response)
    except APIError as e:
        ui.show_error(f"Failed to get character: {e.detail}")
        return None
    except Exception as e:
        ui.show_error(f"Error getting character: {str(e)}")
        return None

# Zone API

def get_zones(world_id: str) -> List[Dict[str, Any]]:
    """Get zones for a world"""
    try:
        params = {"world_id": world_id}
        response = requests.get(f"{config.api_url}/zones/", params=params, headers=get_headers())
        data = handle_response(response)
        return data.get("items", [])
    except APIError as e:
        ui.show_error(f"Failed to get zones: {e.detail}")
        return []
    except Exception as e:
        ui.show_error(f"Error getting zones: {str(e)}")
        return []

def get_zone(zone_id: str) -> Optional[Dict[str, Any]]:
    """Get details of a specific zone"""
    try:
        response = requests.get(f"{config.api_url}/zones/{zone_id}", headers=get_headers())
        return handle_response(response)
    except APIError as e:
        ui.show_error(f"Failed to get zone: {e.detail}")
        return None
    except Exception as e:
        ui.show_error(f"Error getting zone: {str(e)}")
        return None

def create_zone(world_id: str, name: str, description: str, zone_type: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Create a new zone"""
    try:
        payload = {
            "world_id": world_id,
            "name": name,
            "description": description
        }
        
        if zone_type:
            payload["zone_type"] = zone_type
        
        response = requests.post(f"{config.api_url}/zones/", json=payload, headers=get_headers())
        return handle_response(response)
    except APIError as e:
        ui.show_error(f"Failed to create zone: {e.detail}")
        return None
    except Exception as e:
        ui.show_error(f"Error creating zone: {str(e)}")
        return None

def move_character_to_zone(character_id: str, zone_id: str) -> bool:
    """Move a character to a different zone"""
    try:
        payload = {
            "zone_id": zone_id
        }
        
        response = requests.post(
            f"{config.api_url}/zones/characters/{character_id}/move", 
            json=payload, 
            headers=get_headers()
        )
        handle_response(response)
        return True
    except APIError as e:
        ui.show_error(f"Failed to move character: {e.detail}")
        return False
    except Exception as e:
        ui.show_error(f"Error moving character: {str(e)}")
        return False