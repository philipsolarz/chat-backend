#!/usr/bin/env python
# Base service for API communication
import requests
from typing import Dict, Any, Optional, List, Tuple, Union
import json

from client.utils.config import config
from client.game.state import game_state


class APIError(Exception):
    """Exception raised for API errors"""
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"API Error ({status_code}): {detail}")


class BaseService:
    """Base class for API services"""
    
    def __init__(self):
        self.api_url = config.api_url
    
    def _get_headers(self) -> Dict[str, str]:
        """Get common headers for API requests"""
        headers = {
            "Content-Type": "application/json"
        }
        
        if game_state.access_token:
            headers["Authorization"] = f"Bearer {game_state.access_token}"
            
        return headers
    
    async def _handle_response(self, response: requests.Response) -> Dict[str, Any]:
        """Process API response and handle errors"""
        if response.status_code >= 200 and response.status_code < 300:
            if response.status_code == 204:  # No content
                return {}
                
            try:
                return response.json()
            except json.JSONDecodeError:
                return {"message": response.text}
        else:
            try:
                error_data = response.json()
                detail = error_data.get("detail", "Unknown error")
            except:
                detail = response.text or "Unknown error"
                
            raise APIError(response.status_code, detail)
    
    async def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make GET request to API"""
        url = f"{self.api_url}{endpoint}"
        headers = self._get_headers()
        
        try:
            response = requests.get(url, headers=headers, params=params)
            return await self._handle_response(response)
        except APIError:
            # Re-raise API errors
            raise
        except Exception as e:
            raise APIError(500, f"Request failed: {str(e)}")
    
    async def post(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Make POST request to API"""
        url = f"{self.api_url}{endpoint}"
        headers = self._get_headers()
        
        try:
            response = requests.post(url, headers=headers, json=data)
            return await self._handle_response(response)
        except APIError:
            # Re-raise API errors
            raise
        except Exception as e:
            raise APIError(500, f"Request failed: {str(e)}")
    
    async def put(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Make PUT request to API"""
        url = f"{self.api_url}{endpoint}"
        headers = self._get_headers()
        
        try:
            response = requests.put(url, headers=headers, json=data)
            return await self._handle_response(response)
        except APIError:
            # Re-raise API errors
            raise
        except Exception as e:
            raise APIError(500, f"Request failed: {str(e)}")
    
    async def delete(self, endpoint: str) -> Dict[str, Any]:
        """Make DELETE request to API"""
        url = f"{self.api_url}{endpoint}"
        headers = self._get_headers()
        
        try:
            response = requests.delete(url, headers=headers)
            return await self._handle_response(response)
        except APIError:
            # Re-raise API errors
            raise
        except Exception as e:
            raise APIError(500, f"Request failed: {str(e)}")