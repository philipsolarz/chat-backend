#!/usr/bin/env python
# Enhanced client.py - Console client for testing chat backend API and WebSockets
import asyncio
import json
import os
import sys
import websockets
import requests
import signal
import time
import threading
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple, Union
from urllib.parse import urlparse, parse_qs

from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.panel import Panel
from rich.text import Text
from rich.live import Live
from rich.layout import Layout
from rich.table import Table
from rich.syntax import Syntax
from rich.progress import Progress
from rich.markdown import Markdown

# Initialize Rich console
console = Console()

# Default API and WebSocket URLs
API_URL = "http://localhost:8000/api/v1"
WS_URL = "ws://localhost:8000/ws"

# Configure message display
message_buffer = []
MAX_BUFFER_SIZE = 100

# Shared state for managing input flow and authentication
# Update the State class with world and zone properties
class State:
    waiting_for_field = None
    waiting_for_prompt = None
    connected = False
    shutdown_requested = False
    current_user_id = None  # Store current user's ID
    current_character_name = None  # Store current character's name
    access_token = None
    refresh_token = None
    user_email = None
    conversation_id = None
    participant_id = None
    api_mode = False  # Flag for API testing mode
    is_premium = False
    current_world_id = None  # Store current world's ID
    current_world_name = None  # Store current world's name
    current_zone_id = None  # Store current zone's ID
    current_zone_name = None  # Store current zone's name

# Initialize state
state = State()

# ----------------------------
# Authentication Functions
# ----------------------------

def register_user() -> bool:
    """Register a new user"""
    console.print("[bold cyan]User Registration[/bold cyan]")
    email = Prompt.ask("Email")
    password = Prompt.ask("Password", password=True)
    first_name = Prompt.ask("First Name", default="")
    last_name = Prompt.ask("Last Name", default="")
    
    payload = {
        "email": email,
        "password": password,
        "first_name": first_name if first_name else None,
        "last_name": last_name if last_name else None
    }
    
    try:
        with console.status("[bold green]Registering user...[/bold green]"):
            response = requests.post(f"{API_URL}/auth/register", json=payload)
        
        if response.status_code == 201:
            data = response.json()
            state.access_token = data["access_token"]
            state.refresh_token = data["refresh_token"]
            state.current_user_id = data["user_id"]
            state.user_email = data["email"]
            console.print("[bold green]Registration successful![/bold green]")
            return True
        else:
            console.print(f"[bold red]Registration failed: {response.status_code}[/bold red]")
            try:
                error = response.json()
                console.print(f"[red]{error['detail']}[/red]")
            except:
                console.print(f"[red]{response.text}[/red]")
            return False
    except Exception as e:
        console.print(f"[bold red]Error during registration: {str(e)}[/bold red]")
        return False

def login_user() -> bool:
    """Login an existing user"""
    console.print("[bold cyan]User Login[/bold cyan]")
    email = Prompt.ask("Email")
    password = Prompt.ask("Password", password=True)
    
    payload = {
        "email": email,
        "password": password
    }
    
    try:
        with console.status("[bold green]Logging in...[/bold green]"):
            response = requests.post(f"{API_URL}/auth/login", json=payload)
        
        if response.status_code == 200:
            data = response.json()
            state.access_token = data["access_token"]
            state.refresh_token = data["refresh_token"]
            state.current_user_id = data["user_id"]
            state.user_email = data["email"]
            console.print("[bold green]Login successful![/bold green]")
            # Get premium status
            state.is_premium = check_premium_status()
            return True
        else:
            console.print(f"[bold red]Login failed: {response.status_code}[/bold red]")
            try:
                error = response.json()
                console.print(f"[red]{error['detail']}[/red]")
            except:
                console.print(f"[red]{response.text}[/red]")
            return False
    except Exception as e:
        console.print(f"[bold red]Error during login: {str(e)}[/bold red]")
        return False

def logout_user() -> bool:
    """Logout the current user"""
    if not state.access_token:
        console.print("[yellow]Not logged in[/yellow]")
        return True
    
    try:
        headers = {
            "Authorization": f"Bearer {state.access_token}"
        }
        
        with console.status("[bold green]Logging out...[/bold green]"):
            response = requests.post(f"{API_URL}/auth/logout", headers=headers)
        
        if response.status_code == 204:
            state.access_token = None
            state.refresh_token = None
            state.current_user_id = None
            state.user_email = None
            state.is_premium = False
            console.print("[bold green]Logout successful![/bold green]")
            return True
        else:
            console.print(f"[bold red]Logout failed: {response.status_code}[/bold red]")
            try:
                error = response.json()
                console.print(f"[red]{error['detail']}[/red]")
            except:
                console.print(f"[red]{response.text}[/red]")
            return False
    except Exception as e:
        console.print(f"[bold red]Error during logout: {str(e)}[/bold red]")
        return False

def refresh_token() -> bool:
    """Refresh access token"""
    if not state.refresh_token:
        console.print("[yellow]No refresh token available[/yellow]")
        return False
    
    payload = {
        "refresh_token": state.refresh_token
    }
    
    try:
        with console.status("[bold green]Refreshing token...[/bold green]"):
            response = requests.post(f"{API_URL}/auth/refresh", json=payload)
        
        if response.status_code == 200:
            data = response.json()
            state.access_token = data["access_token"]
            state.refresh_token = data["refresh_token"]
            console.print("[green]Token refreshed successfully[/green]")
            return True
        else:
            console.print(f"[bold red]Token refresh failed: {response.status_code}[/bold red]")
            try:
                error = response.json()
                console.print(f"[red]{error['detail']}[/red]")
            except:
                console.print(f"[red]{response.text}[/red]")
            return False
    except Exception as e:
        console.print(f"[bold red]Error during token refresh: {str(e)}[/bold bold]")
        return False

def check_premium_status() -> bool:
    """Check if user has premium status"""
    if not state.access_token:
        return False
    
    try:
        headers = {
            "Authorization": f"Bearer {state.access_token}"
        }
        
        response = requests.get(f"{API_URL}/payments/subscription", headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            is_premium = data.get("is_premium", False)
            return is_premium
        else:
            return False
    except Exception as e:
        console.print(f"[bold red]Error checking premium status: {str(e)}[/bold red]")
        return False

# ----------------------------
# World API Functions
# ----------------------------

def get_worlds() -> List[Dict[str, Any]]:
    """Get list of accessible worlds"""
    if not state.access_token:
        console.print("[yellow]Not logged in[/yellow]")
        return []
    
    try:
        headers = {
            "Authorization": f"Bearer {state.access_token}"
        }
        
        with console.status("[bold green]Getting worlds...[/bold green]"):
            response = requests.get(f"{API_URL}/worlds/", headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            return data.get("items", [])
        else:
            console.print(f"[bold red]Failed to get worlds: {response.status_code}[/bold red]")
            try:
                error = response.json()
                console.print(f"[red]{error['detail']}[/red]")
            except:
                console.print(f"[red]{response.text}[/red]")
            return []
    except Exception as e:
        console.print(f"[bold red]Error getting worlds: {str(e)}[/bold red]")
        return []

def get_starter_worlds() -> List[Dict[str, Any]]:
    """Get list of starter worlds"""
    if not state.access_token:
        console.print("[yellow]Not logged in[/yellow]")
        return []
    
    try:
        headers = {
            "Authorization": f"Bearer {state.access_token}"
        }
        
        with console.status("[bold green]Getting starter worlds...[/bold green]"):
            response = requests.get(f"{API_URL}/worlds/starter", headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            return data.get("items", [])
        else:
            console.print(f"[bold red]Failed to get starter worlds: {response.status_code}[/bold red]")
            try:
                error = response.json()
                console.print(f"[red]{error['detail']}[/red]")
            except:
                console.print(f"[red]{response.text}[/red]")
            return []
    except Exception as e:
        console.print(f"[bold red]Error getting starter worlds: {str(e)}[/bold red]")
        return []

def create_world(name: str, description: str = None, genre: str = None, is_public: bool = False) -> Optional[Dict[str, Any]]:
    """Create a new world"""
    if not state.access_token:
        console.print("[yellow]Not logged in[/yellow]")
        return None
    
    try:
        headers = {
            "Authorization": f"Bearer {state.access_token}"
        }
        
        payload = {
            "name": name,
            "description": description,
            "genre": genre,
            "is_public": is_public,
            "is_premium": False  # Regular creation
        }
        
        with console.status("[bold green]Creating world...[/bold green]"):
            response = requests.post(f"{API_URL}/worlds/", json=payload, headers=headers)
        
        if response.status_code == 201:
            data = response.json()
            console.print(f"[bold green]World {name} created successfully![/bold green]")
            return data
        else:
            console.print(f"[bold red]Failed to create world: {response.status_code}[/bold red]")
            try:
                error = response.json()
                console.print(f"[red]{error['detail']}[/red]")
            except:
                console.print(f"[red]{response.text}[/red]")
            return None
    except Exception as e:
        console.print(f"[bold red]Error creating world: {str(e)}[/bold red]")
        return None

def get_world(world_id: str) -> Optional[Dict[str, Any]]:
    """Get details of a specific world"""
    if not state.access_token:
        console.print("[yellow]Not logged in[/yellow]")
        return None
    
    try:
        headers = {
            "Authorization": f"Bearer {state.access_token}"
        }
        
        with console.status("[bold green]Getting world details...[/bold green]"):
            response = requests.get(f"{API_URL}/worlds/{world_id}", headers=headers)
        
        if response.status_code == 200:
            return response.json()
        else:
            console.print(f"[bold red]Failed to get world: {response.status_code}[/bold red]")
            try:
                error = response.json()
                console.print(f"[red]{error['detail']}[/red]")
            except:
                console.print(f"[red]{response.text}[/red]")
            return None
    except Exception as e:
        console.print(f"[bold red]Error getting world: {str(e)}[/bold red]")
        return None

def purchase_premium_world(name: str, description: str = None, genre: str = None) -> Optional[Dict[str, str]]:
    """Start premium world purchase process"""
    if not state.access_token:
        console.print("[yellow]Not logged in[/yellow]")
        return None
    
    try:
        headers = {
            "Authorization": f"Bearer {state.access_token}"
        }
        
        payload = {
            "name": name,
            "description": description,
            "genre": genre,
            "success_url": "http://localhost:8000/premium-world-success",
            "cancel_url": "http://localhost:8000/premium-world-cancel"
        }
        
        with console.status("[bold green]Initiating premium world purchase...[/bold green]"):
            response = requests.post(f"{API_URL}/worlds/premium", json=payload, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            console.print(f"[bold green]Premium world purchase initiated![/bold green]")
            return data
        else:
            console.print(f"[bold red]Failed to initiate premium world purchase: {response.status_code}[/bold red]")
            try:
                error = response.json()
                console.print(f"[red]{error['detail']}[/red]")
            except:
                console.print(f"[red]{response.text}[/red]")
            return None
    except Exception as e:
        console.print(f"[bold red]Error initiating premium world purchase: {str(e)}[/bold red]")
        return None

# ----------------------------
# Zone API Functions
# ----------------------------

def get_zones(world_id: str, parent_zone_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Get zones for a world, optionally filtered by parent zone"""
    if not state.access_token:
        console.print("[yellow]Not logged in[/yellow]")
        return []
    
    try:
        headers = {
            "Authorization": f"Bearer {state.access_token}"
        }
        
        params = {
            "world_id": world_id
        }
        
        if parent_zone_id is not None:
            params["parent_zone_id"] = parent_zone_id
        
        with console.status("[bold green]Getting zones...[/bold green]"):
            response = requests.get(f"{API_URL}/zones/", params=params, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            return data.get("items", [])
        else:
            console.print(f"[bold red]Failed to get zones: {response.status_code}[/bold red]")
            try:
                error = response.json()
                console.print(f"[red]{error['detail']}[/red]")
            except:
                console.print(f"[red]{response.text}[/red]")
            return []
    except Exception as e:
        console.print(f"[bold red]Error getting zones: {str(e)}[/bold red]")
        return []

def get_zone_hierarchy(world_id: str) -> List[Dict[str, Any]]:
    """Get zone hierarchy for a world"""
    if not state.access_token:
        console.print("[yellow]Not logged in[/yellow]")
        return []
    
    try:
        headers = {
            "Authorization": f"Bearer {state.access_token}"
        }
        
        params = {
            "world_id": world_id
        }
        
        with console.status("[bold green]Getting zone hierarchy...[/bold green]"):
            response = requests.get(f"{API_URL}/zones/hierarchy", params=params, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            return data.get("zones", [])
        else:
            console.print(f"[bold red]Failed to get zone hierarchy: {response.status_code}[/bold red]")
            try:
                error = response.json()
                console.print(f"[red]{error['detail']}[/red]")
            except:
                console.print(f"[red]{response.text}[/red]")
            return []
    except Exception as e:
        console.print(f"[bold red]Error getting zone hierarchy: {str(e)}[/bold red]")
        return []

def get_zone(zone_id: str) -> Optional[Dict[str, Any]]:
    """Get details of a specific zone"""
    if not state.access_token:
        console.print("[yellow]Not logged in[/yellow]")
        return None
    
    try:
        headers = {
            "Authorization": f"Bearer {state.access_token}"
        }
        
        with console.status("[bold green]Getting zone details...[/bold green]"):
            response = requests.get(f"{API_URL}/zones/{zone_id}", headers=headers)
        
        if response.status_code == 200:
            return response.json()
        else:
            console.print(f"[bold red]Failed to get zone: {response.status_code}[/bold red]")
            try:
                error = response.json()
                console.print(f"[red]{error['detail']}[/red]")
            except:
                console.print(f"[red]{response.text}[/red]")
            return None
    except Exception as e:
        console.print(f"[bold red]Error getting zone: {str(e)}[/bold red]")
        return None

def create_zone(world_id: str, name: str, description: str, zone_type: Optional[str] = None, parent_zone_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Create a new zone"""
    if not state.access_token:
        console.print("[yellow]Not logged in[/yellow]")
        return None
    
    try:
        headers = {
            "Authorization": f"Bearer {state.access_token}"
        }
        
        payload = {
            "world_id": world_id,
            "name": name,
            "description": description,
            "zone_type": zone_type,
            "parent_zone_id": parent_zone_id
        }
        
        with console.status("[bold green]Creating zone...[/bold green]"):
            response = requests.post(f"{API_URL}/zones/", json=payload, headers=headers)
        
        if response.status_code == 201:
            data = response.json()
            console.print(f"[bold green]Zone {name} created successfully![/bold green]")
            return data
        else:
            console.print(f"[bold red]Failed to create zone: {response.status_code}[/bold red]")
            try:
                error = response.json()
                console.print(f"[red]{error['detail']}[/red]")
            except:
                console.print(f"[red]{response.text}[/red]")
            return None
    except Exception as e:
        console.print(f"[bold red]Error creating zone: {str(e)}[/bold red]")
        return None

def purchase_zone_upgrade(world_id: str) -> Optional[Dict[str, str]]:
    """Purchase a zone limit upgrade for a world"""
    if not state.access_token:
        console.print("[yellow]Not logged in[/yellow]")
        return None
    
    try:
        headers = {
            "Authorization": f"Bearer {state.access_token}"
        }
        
        payload = {
            "world_id": world_id,
            "success_url": "http://localhost:8000/zone-upgrade-success",
            "cancel_url": "http://localhost:8000/zone-upgrade-cancel"
        }
        
        with console.status("[bold green]Initiating zone upgrade purchase...[/bold green]"):
            response = requests.post(f"{API_URL}/zones/zone-upgrade-checkout", json=payload, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            console.print(f"[bold green]Zone upgrade purchase initiated![/bold green]")
            return data
        else:
            console.print(f"[bold red]Failed to initiate zone upgrade purchase: {response.status_code}[/bold red]")
            try:
                error = response.json()
                console.print(f"[red]{error['detail']}[/red]")
            except:
                console.print(f"[red]{response.text}[/red]")
            return None
    except Exception as e:
        console.print(f"[bold red]Error initiating zone upgrade purchase: {str(e)}[/bold red]")
        return None

def get_zone_characters(zone_id: str) -> List[Dict[str, Any]]:
    """Get all characters in a zone"""
    if not state.access_token:
        console.print("[yellow]Not logged in[/yellow]")
        return []
    
    try:
        headers = {
            "Authorization": f"Bearer {state.access_token}"
        }
        
        with console.status("[bold green]Getting characters in zone...[/bold green]"):
            response = requests.get(f"{API_URL}/zones/{zone_id}/characters", headers=headers)
        
        if response.status_code == 200:
            return response.json()
        else:
            console.print(f"[bold red]Failed to get characters in zone: {response.status_code}[/bold red]")
            try:
                error = response.json()
                console.print(f"[red]{error['detail']}[/red]")
            except:
                console.print(f"[red]{response.text}[/red]")
            return []
    except Exception as e:
        console.print(f"[bold red]Error getting characters in zone: {str(e)}[/bold red]")
        return []

def get_zone_agents(zone_id: str) -> List[Dict[str, Any]]:
    """Get all agents (NPCs) in a zone"""
    if not state.access_token:
        console.print("[yellow]Not logged in[/yellow]")
        return []
    
    try:
        headers = {
            "Authorization": f"Bearer {state.access_token}"
        }
        
        with console.status("[bold green]Getting agents in zone...[/bold green]"):
            response = requests.get(f"{API_URL}/zones/{zone_id}/agents", headers=headers)
        
        if response.status_code == 200:
            return response.json()
        else:
            console.print(f"[bold red]Failed to get agents in zone: {response.status_code}[/bold red]")
            try:
                error = response.json()
                console.print(f"[red]{error['detail']}[/red]")
            except:
                console.print(f"[red]{response.text}[/red]")
            return []
    except Exception as e:
        console.print(f"[bold red]Error getting agents in zone: {str(e)}[/bold red]")
        return []

def move_character_to_zone(character_id: str, zone_id: str) -> Optional[Dict[str, Any]]:
    """Move a character to a different zone"""
    if not state.access_token:
        console.print("[yellow]Not logged in[/yellow]")
        return None
    
    try:
        headers = {
            "Authorization": f"Bearer {state.access_token}"
        }
        
        payload = {
            "zone_id": zone_id
        }
        
        with console.status("[bold green]Moving character to zone...[/bold green]"):
            response = requests.post(f"{API_URL}/zones/characters/{character_id}/move", json=payload, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            console.print(f"[bold green]Character moved successfully![/bold green]")
            return data
        else:
            console.print(f"[bold red]Failed to move character: {response.status_code}[/bold red]")
            try:
                error = response.json()
                console.print(f"[red]{error['detail']}[/red]")
            except:
                console.print(f"[red]{response.text}[/red]")
            return None
    except Exception as e:
        console.print(f"[bold red]Error moving character: {str(e)}[/bold red]")
        return None

def get_agent_limits(zone_id: str) -> Optional[Dict[str, Any]]:
    """Get agent limit information for a zone"""
    if not state.access_token:
        console.print("[yellow]Not logged in[/yellow]")
        return None
    
    try:
        headers = {
            "Authorization": f"Bearer {state.access_token}"
        }
        
        with console.status("[bold green]Getting agent limits...[/bold green]"):
            response = requests.get(f"{API_URL}/zones/{zone_id}/agent-limits", headers=headers)
        
        if response.status_code == 200:
            return response.json()
        else:
            console.print(f"[bold red]Failed to get agent limits: {response.status_code}[/bold red]")
            try:
                error = response.json()
                console.print(f"[red]{error['detail']}[/red]")
            except:
                console.print(f"[red]{response.text}[/red]")
            return None
    except Exception as e:
        console.print(f"[bold red]Error getting agent limits: {str(e)}[/bold red]")
        return None

def purchase_agent_limit_upgrade(zone_id: str) -> Optional[Dict[str, str]]:
    """Purchase an agent limit upgrade for a zone"""
    if not state.access_token:
        console.print("[yellow]Not logged in[/yellow]")
        return None
    
    try:
        headers = {
            "Authorization": f"Bearer {state.access_token}"
        }
        
        payload = {
            "zone_id": zone_id,
            "success_url": "http://localhost:8000/agent-limit-success",
            "cancel_url": "http://localhost:8000/agent-limit-cancel"
        }
        
        with console.status("[bold green]Initiating agent limit upgrade purchase...[/bold green]"):
            response = requests.post(f"{API_URL}/zones/agent-limit-upgrade-checkout", json=payload, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            console.print(f"[bold green]Agent limit upgrade purchase initiated![/bold green]")
            return data
        else:
            console.print(f"[bold red]Failed to initiate agent limit upgrade purchase: {response.status_code}[/bold red]")
            try:
                error = response.json()
                console.print(f"[red]{error['detail']}[/red]")
            except:
                console.print(f"[red]{response.text}[/red]")
            return None
    except Exception as e:
        console.print(f"[bold red]Error initiating agent limit upgrade purchase: {str(e)}[/bold red]")
        return None

def show_agent_limit_menu(zone_id: str):
    """Show menu for agent limit management"""
    zone = get_zone(zone_id)
    
    if not zone:
        console.print("[yellow]Zone not found[/yellow]")
        return
    
    # Get agent limits
    limits = get_agent_limits(zone_id)
    if not limits:
        console.print("[yellow]Failed to get agent limits[/yellow]")
        return
    
    console.print(Panel(
        f"[bold]Agent Limits for {zone['name']}[/bold]\n\n"
        f"Current Agent Count: {limits['agent_count']}\n"
        f"Base Agent Limit: {limits['base_limit']}\n"
        f"Agent Upgrades Purchased: {limits['upgrades_purchased']}\n"
        f"Total Agent Limit: {limits['total_limit']}\n"
        f"Remaining Capacity: {limits['remaining_capacity']}\n\n"
        f"Each agent upgrade costs $9.99 and increases your\n"
        f"agent limit by 10 additional agents.",
        title="Agent Limits", border_style="cyan"
    ))
    
    if limits['remaining_capacity'] < 5:
        console.print("[yellow]WARNING: You are approaching your agent limit![/yellow]")
    
    # Check if user can purchase upgrades
    if limits.get('can_purchase_upgrade', False):
        if Confirm.ask("Would you like to purchase an agent limit upgrade?", default=False):
            result = purchase_agent_limit_upgrade(zone_id)
            if result and "checkout_url" in result:
                console.print(f"[bold green]Agent limit upgrade purchase initiated![/bold green]")
                console.print(f"[green]Please complete your purchase at: {result['checkout_url']}[/green]")
                console.print("[green]After payment, your agent limit will increase automatically.[/green]")
        else:
            console.print("[yellow]Agent limit upgrade purchase cancelled[/yellow]")
    else:
        console.print("[yellow]Only the world owner can purchase agent limit upgrades[/yellow]")

# ----------------------------
# World & Zone Interactive Menus
# ----------------------------

def show_worlds():
    """Show user's accessible worlds"""
    worlds = get_worlds()
    
    if not worlds:
        console.print("[yellow]No accessible worlds found[/yellow]")
        return
    
    table = Table(title="Your Accessible Worlds")
    table.add_column("ID", style="dim")
    table.add_column("Name", style="green")
    table.add_column("Genre", style="blue")
    table.add_column("Description", style="cyan")
    table.add_column("Type", style="magenta")
    
    for world in worlds:
        # Determine world type
        world_type = ""
        if world.get("is_premium", False):
            world_type = "Premium"
        elif world.get("is_starter", False):
            world_type = "Starter"
        else:
            world_type = "Standard"
            
        table.add_row(
            world["id"],
            world["name"],
            world.get("genre", ""),
            world.get("description", "").strip()[:30] + "..." if world.get("description", "") and len(world.get("description", "")) > 30 else world.get("description", ""),
            world_type
        )
    
    console.print(table)

def show_world_details(world_id: str):
    """Show detailed information about a world"""
    world = get_world(world_id)
    
    if not world:
        console.print("[yellow]World not found[/yellow]")
        return
    
    # Calculate zone information
    zones = get_zones(world_id)
    zone_count = len(zones)
    zone_limit = world.get("zone_limit", 100)
    zone_upgrades = world.get("zone_limit_upgrades", 0)
    total_limit = zone_limit + (zone_upgrades * 100)
    
    # Create rich formatted details
    details = [
        f"[bold cyan]ID:[/bold cyan] {world['id']}",
        f"[bold cyan]Name:[/bold cyan] {world['name']}",
        f"[bold cyan]Genre:[/bold cyan] {world.get('genre', 'N/A')}",
        f"[bold cyan]Description:[/bold cyan] {world.get('description', 'N/A')}",
        f"[bold cyan]Type:[/bold cyan] {'Premium' if world.get('is_premium', False) else 'Starter' if world.get('is_starter', False) else 'Standard'}",
        f"[bold cyan]Public:[/bold cyan] {'Yes' if world.get('is_public', False) else 'No'}",
        f"[bold cyan]Zone Count:[/bold cyan] {zone_count} / {total_limit}",
        f"[bold cyan]Zone Upgrades:[/bold cyan] {zone_upgrades}",
        f"[bold cyan]Owner:[/bold cyan] {'You' if world.get('owner_id') == state.current_user_id else 'System' if world.get('is_starter', False) else 'Other User'}"
    ]
    
    console.print(Panel("\n".join(details), title=f"World: {world['name']}", border_style="green"))

def interactive_create_world():
    """Interactive world creation"""
    console.print("[bold cyan]Create World[/bold cyan]")
    name = Prompt.ask("World Name")
    description = Prompt.ask("Description (optional)", default="")
    genre = Prompt.ask("Genre (optional)", default="")
    is_public = Confirm.ask("Make public?", default=False)
    
    world = create_world(name, description, genre, is_public)
    if world:
        console.print(f"[bold green]World created:[/bold green]")
        for key, value in world.items():
            console.print(f"[cyan]{key}:[/cyan] {value}")
        
        # Set as current world
        state.current_world_id = world["id"]
        state.current_world_name = world["name"]
        console.print(f"[green]Set current world to: {world['name']}[/green]")

def interactive_premium_world():
    """Interactive premium world creation (purchase flow)"""
    console.print("[bold cyan]Create Premium World[/bold cyan]")
    console.print("[bold yellow]This will initiate a purchase for $249.99[/bold yellow]")
    
    if not Confirm.ask("Continue with premium world purchase?", default=False):
        console.print("[yellow]Premium world purchase cancelled[/yellow]")
        return
    
    name = Prompt.ask("World Name")
    description = Prompt.ask("Description (optional)", default="")
    genre = Prompt.ask("Genre (optional)", default="")
    
    result = purchase_premium_world(name, description, genre)
    if result and "checkout_url" in result:
        console.print(f"[bold green]Premium world purchase initiated![/bold green]")
        console.print(f"[green]Please complete your purchase at: {result['checkout_url']}[/green]")
        console.print("[green]After payment, your premium world will be created automatically.[/green]")

def select_world():
    """Select a world to use"""
    worlds = get_worlds()
    
    if not worlds:
        console.print("[yellow]No accessible worlds found[/yellow]")
        return False
    
    console.print("[bold]Your Accessible Worlds:[/bold]")
    for i, world in enumerate(worlds):
        world_type = ""
        if world.get("is_premium", False):
            world_type = "[magenta](Premium)[/magenta]"
        elif world.get("is_starter", False):
            world_type = "[blue](Starter)[/blue]"
            
        console.print(f"[cyan]{i+1}.[/cyan] {world['name']} {world_type}")
    
    choice = Prompt.ask("Select world (number)", default="1")
    try:
        index = int(choice) - 1
        if 0 <= index < len(worlds):
            selected_world = worlds[index]
            state.current_world_id = selected_world["id"]
            state.current_world_name = selected_world["name"]
            console.print(f"[green]Selected world: {selected_world['name']}[/green]")
            
            # Reset zone selection when world changes
            state.current_zone_id = None
            state.current_zone_name = None
            
            return True
        else:
            console.print("[yellow]Invalid selection[/yellow]")
            return False
    except ValueError:
        console.print("[yellow]Invalid input[/yellow]")
        return False

def show_zones(world_id: str, parent_zone_id: Optional[str] = None):
    """Show zones in a world, optionally filtered by parent zone"""
    zones = get_zones(world_id, parent_zone_id)
    
    if not zones:
        if parent_zone_id:
            parent_zone = get_zone(parent_zone_id)
            parent_name = parent_zone.get("name", "Unknown") if parent_zone else "Unknown"
            console.print(f"[yellow]No sub-zones found in {parent_name}[/yellow]")
        else:
            console.print(f"[yellow]No zones found in this world[/yellow]")
        return
    
    title = "Zones"
    if parent_zone_id:
        parent_zone = get_zone(parent_zone_id)
        if parent_zone:
            title = f"Sub-zones of {parent_zone['name']}"
    
    table = Table(title=title)
    table.add_column("ID", style="dim")
    table.add_column("Name", style="green")
    table.add_column("Type", style="blue")
    table.add_column("Description", style="cyan")
    table.add_column("Sub-zones", style="magenta")
    
    for zone in zones:
        # Get count of sub-zones
        sub_zones = get_zones(world_id, zone["id"])
        sub_zone_count = len(sub_zones)
        
        table.add_row(
            zone["id"],
            zone["name"],
            zone.get("zone_type", "general"),
            zone.get("description", "").strip()[:30] + "..." if zone.get("description", "") and len(zone.get("description", "")) > 30 else zone.get("description", ""),
            str(sub_zone_count)
        )
    
    console.print(table)

def interactive_create_zone(world_id: str, parent_zone_id: Optional[str] = None):
    """Interactive zone creation"""
    console.print("[bold cyan]Create Zone[/bold cyan]")
    
    # Show parent zone info if available
    if parent_zone_id:
        parent_zone = get_zone(parent_zone_id)
        if parent_zone:
            console.print(f"[blue]Parent Zone: {parent_zone['name']}[/blue]")
    
    name = Prompt.ask("Zone Name")
    description = Prompt.ask("Description (optional)", default="")
    
    # Suggest some zone types
    zone_types = [
        "city", "town", "village", "forest", "mountains", "plains", 
        "desert", "ocean", "dungeon", "castle", "ruin", "cave"
    ]
    
    console.print("\n[bold]Suggested Zone Types:[/bold]")
    for i, zone_type in enumerate(zone_types, 1):
        console.print(f"[cyan]{i}.[/cyan] {zone_type}")
    console.print("[cyan]0.[/cyan] Custom type")
    
    type_choice = Prompt.ask("Select zone type (number or enter custom)", default="0")
    if type_choice.isdigit():
        choice = int(type_choice)
        if 1 <= choice <= len(zone_types):
            zone_type = zone_types[choice - 1]
        else:
            zone_type = Prompt.ask("Enter custom zone type", default="general")
    else:
        zone_type = type_choice
    
    zone = create_zone(world_id, name, description, zone_type, parent_zone_id)
    if zone:
        console.print(f"[bold green]Zone created:[/bold green]")
        for key, value in zone.items():
            if key in ["id", "name", "description", "zone_type"]:
                console.print(f"[cyan]{key}:[/cyan] {value}")
        
        # Set as current zone
        state.current_zone_id = zone["id"]
        state.current_zone_name = zone["name"]
        console.print(f"[green]Set current zone to: {zone['name']}[/green]")

def navigate_zones(world_id: str):
    """Interactive zone navigation for a world"""
    current_parent_id = None  # Start at top level
    
    while True:
        console.clear()
        console.print(f"[bold cyan]Zone Navigation - World: {state.current_world_name}[/bold cyan]")
        
        # Show breadcrumb navigation
        breadcrumb = ["Top Level"]
        if current_parent_id:
            # Build the path
            zone_path = []
            parent_id = current_parent_id
            while parent_id:
                parent_zone = get_zone(parent_id)
                if parent_zone:
                    zone_path.insert(0, parent_zone["name"])
                    parent_id = parent_zone.get("parent_zone_id")
                else:
                    break
            breadcrumb.extend(zone_path)
        
        console.print(" > ".join(f"[blue]{crumb}[/blue]" for crumb in breadcrumb))
        console.print()
        
        # Show zones at current level
        zones = get_zones(world_id, current_parent_id)
        
        if not zones:
            console.print("[yellow]No zones found at this level[/yellow]")
        else:
            for i, zone in enumerate(zones, 1):
                has_subzones = len(get_zones(world_id, zone["id"])) > 0
                subzone_indicator = " [blue](has sub-zones)[/blue]" if has_subzones else ""
                console.print(f"[cyan]{i}.[/cyan] {zone['name']} ({zone.get('zone_type', 'general')}){subzone_indicator}")
        
        # Show options
        console.print("\n[bold]Options:[/bold]")
        console.print("[cyan]C.[/cyan] Create new zone at this level")
        if current_parent_id:
            console.print("[cyan]U.[/cyan] Go up a level")
        console.print("[cyan]S.[/cyan] Select a zone")
        console.print("[cyan]B.[/cyan] Back to world menu")
        
        choice = Prompt.ask("Select option", default="S")
        
        if choice.upper() == 'C':
            interactive_create_zone(world_id, current_parent_id)
        elif choice.upper() == 'U' and current_parent_id:
            # Go up a level
            parent_zone = get_zone(current_parent_id)
            current_parent_id = parent_zone.get("parent_zone_id") if parent_zone else None
        elif choice.upper() == 'S':
            # Select a zone
            if not zones:
                console.print("[yellow]No zones to select[/yellow]")
                continue
                
            zone_num = Prompt.ask("Enter zone number to select", default="1")
            try:
                index = int(zone_num) - 1
                if 0 <= index < len(zones):
                    selected_zone = zones[index]
                    
                    # Ask what to do with the selected zone
                    console.print(f"\n[bold]Selected: {selected_zone['name']}[/bold]")
                    action = Prompt.ask(
                        "What would you like to do?", 
                        choices=["details", "navigate", "select", "agents", "cancel"], 
                        default="details"
                    )
                    
                    if action == "details":
                        # Show zone details
                        zone_details = get_zone(selected_zone["id"])
                        if zone_details:
                            details = [
                                f"[bold cyan]ID:[/bold cyan] {zone_details['id']}",
                                f"[bold cyan]Name:[/bold cyan] {zone_details['name']}",
                                f"[bold cyan]Type:[/bold cyan] {zone_details.get('zone_type', 'general')}",
                                f"[bold cyan]Description:[/bold cyan] {zone_details.get('description', 'N/A')}",
                                f"[bold cyan]Characters:[/bold cyan] {zone_details.get('character_count', 0)}",
                                f"[bold cyan]NPCs:[/bold cyan] {zone_details.get('agent_count', 0)}",
                                f"[bold cyan]Sub-zones:[/bold cyan] {zone_details.get('sub_zone_count', 0)}"
                            ]
                            console.print(Panel("\n".join(details), title=f"Zone: {zone_details['name']}", border_style="green"))
                            Prompt.ask("Press Enter to continue")
                    
                    elif action == "agents":
                        # Show agent limit management menu
                        show_agent_limit_menu(selected_zone["id"])
                        Prompt.ask("Press Enter to continue")
                        
                    elif action == "navigate":
                        # Navigate to this zone's sub-zones
                        current_parent_id = selected_zone["id"]
                        
                    elif action == "select":
                        # Set as current zone
                        state.current_zone_id = selected_zone["id"]
                        state.current_zone_name = selected_zone["name"]
                        console.print(f"[green]Set current zone to: {selected_zone['name']}[/green]")
                        Prompt.ask("Press Enter to continue")
                else:
                    console.print("[yellow]Invalid selection[/yellow]")
            except ValueError:
                console.print("[yellow]Invalid input[/yellow]")
        
        elif choice.upper() == 'B':
            break

def zone_upgrade_menu(world_id: str):
    """Menu for purchasing zone limit upgrades"""
    world = get_world(world_id)
    
    if not world:
        console.print("[yellow]World not found[/yellow]")
        return
    
    # Only the owner can purchase upgrades
    if world.get("owner_id") != state.current_user_id:
        console.print("[yellow]Only the world owner can purchase zone upgrades[/yellow]")
        return
    
    # Get zone count and limits
    zones = get_zones(world_id)
    zone_count = len(zones)
    zone_limit = world.get("zone_limit", 100)
    zone_upgrades = world.get("zone_limit_upgrades", 0)
    total_limit = zone_limit + (zone_upgrades * 100)
    
    console.print(Panel(
        f"[bold]Zone Limits for {world['name']}[/bold]\n\n"
        f"Current Zone Count: {zone_count}\n"
        f"Base Zone Limit: {zone_limit}\n"
        f"Zone Upgrades Purchased: {zone_upgrades}\n"
        f"Total Zone Limit: {total_limit}\n"
        f"Remaining Capacity: {total_limit - zone_count}\n\n"
        f"Each zone upgrade costs $49.99 and increases your\n"
        f"zone limit by 100 additional zones.",
        title="Zone Upgrades", border_style="cyan"
    ))
    
    if zone_count >= total_limit - 20:
        console.print("[yellow]WARNING: You are approaching your zone limit![/yellow]")
    
    if Confirm.ask("Would you like to purchase a zone upgrade?", default=False):
        result = purchase_zone_upgrade(world_id)
        if result and "checkout_url" in result:
            console.print(f"[bold green]Zone upgrade purchase initiated![/bold green]")
            console.print(f"[green]Please complete your purchase at: {result['checkout_url']}[/green]")
            console.print("[green]After payment, your zone limit will increase automatically.[/green]")
    else:
        console.print("[yellow]Zone upgrade purchase cancelled[/yellow]")

def world_menu():
    """Main world menu"""
    if not state.current_world_id:
        if not select_world():
            console.print("[yellow]No world selected. Creating a default world...[/yellow]")
            interactive_create_world()
            if not state.current_world_id:
                console.print("[red]Failed to create or select a world.[/red]")
                return
    
    while True:
        console.clear()
        console.print(f"[bold cyan]World: {state.current_world_name}[/bold cyan]")
        
        # Show current zone if available
        if state.current_zone_id:
            console.print(f"[bold blue]Current Zone: {state.current_zone_name}[/bold blue]")
        
        console.print("\n[bold]World Options:[/bold]")
        console.print("[cyan]1.[/cyan] View World Details")
        console.print("[cyan]2.[/cyan] Change World")
        console.print("[cyan]3.[/cyan] Create New World")
        if state.is_premium:
            console.print("[cyan]4.[/cyan] Create Premium World")
        
        console.print("\n[bold]Zone Options:[/bold]")
        console.print("[cyan]5.[/cyan] View Zones")
        console.print("[cyan]6.[/cyan] Navigate Zones")
        console.print("[cyan]7.[/cyan] Create Zone")
        console.print("[cyan]8.[/cyan] Zone Limits & Upgrades")
        
        console.print("\n[cyan]B.[/cyan] Back to Main Menu")
        
        choice = Prompt.ask("Select option", default="1")
        
        if choice == "1":
            # View world details
            show_world_details(state.current_world_id)
            Prompt.ask("Press Enter to continue")
            
        elif choice == "2":
            # Change world
            if select_world():
                console.print(f"[green]Changed current world to: {state.current_world_name}[/green]")
            
        elif choice == "3":
            # Create new world
            interactive_create_world()
            
        elif choice == "4" and state.is_premium:
            # Create premium world
            interactive_premium_world()
            
        elif choice == "5":
            # View zones
            parent_id = None
            
            # If we have a current zone, ask if we want to view its sub-zones
            if state.current_zone_id:
                view_choice = Prompt.ask(
                    "View zones", 
                    choices=["all", "current", "sub"], 
                    default="all"
                )
                
                if view_choice == "current":
                    # Show the current zone details
                    zone = get_zone(state.current_zone_id)
                    if zone:
                        details = [
                            f"[bold cyan]ID:[/bold cyan] {zone['id']}",
                            f"[bold cyan]Name:[/bold cyan] {zone['name']}",
                            f"[bold cyan]Type:[/bold cyan] {zone.get('zone_type', 'general')}",
                            f"[bold cyan]Description:[/bold cyan] {zone.get('description', 'N/A')}",
                            f"[bold cyan]Characters:[/bold cyan] {zone.get('character_count', 0)}",
                            f"[bold cyan]NPCs:[/bold cyan] {zone.get('agent_count', 0)}",
                            f"[bold cyan]Sub-zones:[/bold cyan] {zone.get('sub_zone_count', 0)}"
                        ]
                        console.print(Panel("\n".join(details), title=f"Zone: {zone['name']}", border_style="green"))
                    Prompt.ask("Press Enter to continue")
                    continue
                    
                elif view_choice == "sub":
                    parent_id = state.current_zone_id
            
            show_zones(state.current_world_id, parent_id)
            Prompt.ask("Press Enter to continue")
            
        elif choice == "6":
            # Navigate zones
            navigate_zones(state.current_world_id)
            
        elif choice == "7":
            # Create zone
            parent_id = None
            
            # If we have a current zone, ask if we want to create a sub-zone
            if state.current_zone_id:
                create_choice = Prompt.ask(
                    "Create zone", 
                    choices=["top", "sub"], 
                    default="sub"
                )
                
                if create_choice == "sub":
                    parent_id = state.current_zone_id
            
            interactive_create_zone(state.current_world_id, parent_id)
            Prompt.ask("Press Enter to continue")
            
        elif choice == "8":
            # Zone limits & upgrades
            zone_upgrade_menu(state.current_world_id)
            Prompt.ask("Press Enter to continue")
            
        elif choice.upper() == "B":
            break
# ----------------------------
# API Testing Functions
# ----------------------------

def get_characters() -> List[Dict[str, Any]]:
    """Get list of user's characters"""
    if not state.access_token:
        console.print("[yellow]Not logged in[/yellow]")
        return []
    
    try:
        headers = {
            "Authorization": f"Bearer {state.access_token}"
        }
        
        with console.status("[bold green]Getting characters...[/bold green]"):
            response = requests.get(f"{API_URL}/characters/", headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            return data.get("items", [])
        else:
            console.print(f"[bold red]Failed to get characters: {response.status_code}[/bold red]")
            try:
                error = response.json()
                console.print(f"[red]{error['detail']}[/red]")
            except:
                console.print(f"[red]{response.text}[/red]")
            return []
    except Exception as e:
        console.print(f"[bold red]Error getting characters: {str(e)}[/bold red]")
        return []

def get_public_characters() -> List[Dict[str, Any]]:
    """Get list of public characters"""
    if not state.access_token:
        console.print("[yellow]Not logged in[/yellow]")
        return []
    
    try:
        headers = {
            "Authorization": f"Bearer {state.access_token}"
        }
        
        with console.status("[bold green]Getting public characters...[/bold green]"):
            response = requests.get(f"{API_URL}/characters/public", headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            return data.get("items", [])
        else:
            console.print(f"[bold red]Failed to get public characters: {response.status_code}[/bold red]")
            try:
                error = response.json()
                console.print(f"[red]{error['detail']}[/red]")
            except:
                console.print(f"[red]{response.text}[/red]")
            return []
    except Exception as e:
        console.print(f"[bold red]Error getting public characters: {str(e)}[/bold red]")
        return []

def create_character(name: str, description: str = None, is_public: bool = False) -> Optional[Dict[str, Any]]:
    """Create a new character"""
    if not state.access_token:
        console.print("[yellow]Not logged in[/yellow]")
        return None
    
    try:
        headers = {
            "Authorization": f"Bearer {state.access_token}"
        }
        
        payload = {
            "name": name,
            "description": description,
            "is_public": is_public
        }
        
        with console.status("[bold green]Creating character...[/bold green]"):
            response = requests.post(f"{API_URL}/characters/", json=payload, headers=headers)
        
        if response.status_code == 201:
            data = response.json()
            console.print(f"[bold green]Character {name} created successfully![/bold green]")
            return data
        else:
            console.print(f"[bold red]Failed to create character: {response.status_code}[/bold red]")
            try:
                error = response.json()
                console.print(f"[red]{error['detail']}[/red]")
            except:
                console.print(f"[red]{response.text}[/red]")
            return None
    except Exception as e:
        console.print(f"[bold red]Error creating character: {str(e)}[/bold red]")
        return None

def get_conversations() -> List[Dict[str, Any]]:
    """Get list of user's conversations"""
    if not state.access_token:
        console.print("[yellow]Not logged in[/yellow]")
        return []
    
    try:
        headers = {
            "Authorization": f"Bearer {state.access_token}"
        }
        
        with console.status("[bold green]Getting conversations...[/bold green]"):
            response = requests.get(f"{API_URL}/conversations/", headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            return data.get("items", [])
        else:
            console.print(f"[bold red]Failed to get conversations: {response.status_code}[/bold red]")
            try:
                error = response.json()
                console.print(f"[red]{error['detail']}[/red]")
            except:
                console.print(f"[red]{response.text}[/red]")
            return []
    except Exception as e:
        console.print(f"[bold red]Error getting conversations: {str(e)}[/bold red]")
        return []

def create_conversation(title: str, character_id: str, agent_character_ids: List[str] = None) -> Optional[Dict[str, Any]]:
    """Create a new conversation"""
    if not state.access_token:
        console.print("[yellow]Not logged in[/yellow]")
        return None
    
    # Ensure we have a world_id
    if not state.current_world_id:
        console.print("[yellow]No world selected. Select a world first.[/yellow]")
        return None
    
    try:
        headers = {
            "Authorization": f"Bearer {state.access_token}"
        }
        
        payload = {
            "title": title,
            "user_character_ids": [character_id],
            "agent_character_ids": agent_character_ids or [],
            "user_id": state.current_user_id,
            "world_id": state.current_world_id  # Include the world ID
        }
        
        with console.status("[bold green]Creating conversation...[/bold green]"):
            response = requests.post(f"{API_URL}/conversations/", json=payload, headers=headers)
        
        if response.status_code == 201:
            data = response.json()
            console.print(f"[bold green]Conversation {title} created successfully![/bold green]")
            
            # Find the user participant
            participants = data.get("participants", [])
            for participant in participants:
                if participant.get("user_id") == state.current_user_id:
                    state.participant_id = participant.get("id")
                    break
            
            return data
        else:
            console.print(f"[bold red]Failed to create conversation: {response.status_code}[/bold red]")
            try:
                error = response.json()
                console.print(f"[red]{error['detail']}[/red]")
            except:
                console.print(f"[red]{response.text}[/red]")
            return None
    except Exception as e:
        console.print(f"[bold red]Error creating conversation: {str(e)}[/bold red]")
        return None

def get_conversation_messages(conversation_id: str) -> List[Dict[str, Any]]:
    """Get messages in a conversation"""
    if not state.access_token:
        console.print("[yellow]Not logged in[/yellow]")
        return []
    
    try:
        headers = {
            "Authorization": f"Bearer {state.access_token}"
        }
        
        with console.status("[bold green]Getting messages...[/bold green]"):
            response = requests.get(f"{API_URL}/messages/conversations/{conversation_id}", headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            return data.get("items", [])
        else:
            console.print(f"[bold red]Failed to get messages: {response.status_code}[/bold red]")
            try:
                error = response.json()
                console.print(f"[red]{error['detail']}[/red]")
            except:
                console.print(f"[red]{response.text}[/red]")
            return []
    except Exception as e:
        console.print(f"[bold red]Error getting messages: {str(e)}[/bold red]")
        return []

def send_message(conversation_id: str, participant_id: str, content: str) -> Optional[Dict[str, Any]]:
    """Send a message in a conversation"""
    if not state.access_token:
        console.print("[yellow]Not logged in[/yellow]")
        return None
    
    try:
        headers = {
            "Authorization": f"Bearer {state.access_token}"
        }
        
        payload = {
            "content": content,
            "participant_id": participant_id
        }
        
        with console.status("[bold green]Sending message...[/bold green]"):
            response = requests.post(
                f"{API_URL}/messages/conversations/{conversation_id}", 
                json=payload, 
                headers=headers
            )
        
        if response.status_code == 201:
            data = response.json()
            return data
        else:
            console.print(f"[bold red]Failed to send message: {response.status_code}[/bold red]")
            try:
                error = response.json()
                console.print(f"[red]{error['detail']}[/red]")
            except:
                console.print(f"[red]{response.text}[/red]")
            return None
    except Exception as e:
        console.print(f"[bold red]Error sending message: {str(e)}[/bold red]")
        return None

def test_generic_endpoint():
    """Test any API endpoint with custom parameters"""
    if not state.access_token:
        console.print("[yellow]Not logged in[/yellow]")
        return
    
    console.print("[bold cyan]Generic API Endpoint Test[/bold cyan]")
    method = Prompt.ask("HTTP Method", choices=["GET", "POST", "PUT", "DELETE"], default="GET")
    endpoint = Prompt.ask("Endpoint (without /api/v1)", default="/users/me")
    
    # Check if endpoint starts with a slash
    if not endpoint.startswith("/"):
        endpoint = f"/{endpoint}"
    
    # Build full URL
    url = f"{API_URL}{endpoint}"
    
    # Ask for JSON payload if needed
    payload = None
    if method in ["POST", "PUT"]:
        payload_str = Prompt.ask("JSON Payload (optional)", default="{}")
        try:
            payload = json.loads(payload_str)
        except json.JSONDecodeError:
            console.print("[bold red]Invalid JSON payload. Using empty payload.[/bold red]")
            payload = {}
    
    # Build headers
    headers = {
        "Authorization": f"Bearer {state.access_token}",
        "Content-Type": "application/json"
    }
    
    try:
        with console.status(f"[bold green]Sending {method} request to {url}...[/bold green]"):
            if method == "GET":
                response = requests.get(url, headers=headers)
            elif method == "POST":
                response = requests.post(url, json=payload, headers=headers)
            elif method == "PUT":
                response = requests.put(url, json=payload, headers=headers)
            elif method == "DELETE":
                response = requests.delete(url, headers=headers)
        
        console.print(f"[bold cyan]Status Code:[/bold cyan] {response.status_code}")
        
        if response.status_code < 300:
            console.print("[bold green]Request successful![/bold green]")
        else:
            console.print("[bold red]Request failed![/bold red]")
        
        # Try to parse JSON response
        try:
            json_data = response.json()
            formatted_json = json.dumps(json_data, indent=2)
            console.print(Syntax(formatted_json, "json", theme="monokai"))
        except:
            # If not JSON, print raw text
            console.print(response.text)
    
    except Exception as e:
        console.print(f"[bold red]Error sending request: {str(e)}[/bold red]")

# ----------------------------
# WebSocket Client Functions
# ----------------------------

def get_input(shared_state, websocket_ref):
    """Run in a separate thread to get user input without blocking the event loop"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    while not shared_state.shutdown_requested:
        try:
            if shared_state.waiting_for_field:
                message = input(f"{shared_state.waiting_for_prompt}: ")
                
                # Store the character name if we're creating a character
                if shared_state.waiting_for_field == "name":
                    shared_state.current_character_name = message
                
                async def send_response():
                    websocket = websocket_ref[0]
                    if websocket and shared_state.connected:
                        await websocket.send(message)
                        shared_state.waiting_for_field = None
                        shared_state.waiting_for_prompt = None
                
                loop.run_until_complete(send_response())
            else:
                message = input("> ")
                
                if message.strip().lower() in ['exit', 'quit']:
                    shared_state.shutdown_requested = True
                    os._exit(0)  # Force exit
                
                # Check for special commands
                if message.strip().lower() == '/api':
                    shared_state.api_mode = True
                    print("[yellow]Switching to API testing mode. Type '/chat' to return to chat mode.[/yellow]")
                    show_api_menu()
                    continue
                
                if message.strip().lower() == '/chat':
                    shared_state.api_mode = False
                    print("[yellow]Switching to chat mode.[/yellow]")
                    continue
                
                if shared_state.api_mode:
                    handle_api_command(message.strip())
                    continue
                
                # In chat mode, send the message via WebSocket
                async def send_message():
                    websocket = websocket_ref[0]
                    if websocket and shared_state.connected:
                        try:
                            await websocket.send(json.dumps({
                                "type": "message",
                                "content": message
                            }))
                        except Exception as e:
                            print(f"[red]Error sending message: {e}[/red]")
                
                loop.run_until_complete(send_message())
            
            # Small pause to prevent CPU overuse
            time.sleep(0.1)
            
        except Exception as e:
            print(f"Input error: {e}")
    
    loop.close()

def handle_api_command(command: str):
    """Handle API testing commands"""
    if command.startswith('/'):
        cmd_parts = command[1:].split(' ')
        cmd = cmd_parts[0].lower()
        
        # Existing commands
        if cmd == 'help':
            show_api_menu()
        
        elif cmd == 'login':
            login_user()
        
        elif cmd == 'register':
            register_user()
        
        elif cmd == 'logout':
            logout_user()
        
        elif cmd == 'refresh':
            refresh_token()
        
        elif cmd == 'characters':
            show_characters()
        
        elif cmd == 'conversations':
            show_conversations()
        
        elif cmd == 'create_character':
            interactive_create_character()
        
        elif cmd == 'create_conversation':
            interactive_create_conversation()
        
        elif cmd == 'endpoint':
            test_generic_endpoint()
        
        elif cmd == 'status':
            show_auth_status()
            
        elif cmd == 'premium':
            premium_status = check_premium_status()
            console.print(f"Premium status: [{'green' if premium_status else 'red'}]{premium_status}[/{'green' if premium_status else 'red'}]")
        
        # New world commands
        elif cmd == 'worlds':
            show_worlds()
        
        elif cmd == 'create_world':
            interactive_create_world()
        
        elif cmd == 'select_world':
            select_world()
        
        elif cmd == 'world_details':
            if state.current_world_id:
                show_world_details(state.current_world_id)
            else:
                console.print("[yellow]No world selected. Use /select_world first.[/yellow]")
        
        # New zone commands
        elif cmd == 'zones':
            if state.current_world_id:
                show_zones(state.current_world_id)
            else:
                console.print("[yellow]No world selected. Use /select_world first.[/yellow]")
        
        elif cmd == 'create_zone':
            if state.current_world_id:
                interactive_create_zone(state.current_world_id)
            else:
                console.print("[yellow]No world selected. Use /select_world first.[/yellow]")
        
        elif cmd == 'navigate_zones':
            if state.current_world_id:
                navigate_zones(state.current_world_id)
            else:
                console.print("[yellow]No world selected. Use /select_world first.[/yellow]")
        
        elif cmd == 'zone_upgrade':
            if state.current_world_id:
                zone_upgrade_menu(state.current_world_id)
            else:
                console.print("[yellow]No world selected. Use /select_world first.[/yellow]")
        
        else:
            console.print(f"[yellow]Unknown command: {cmd}[/yellow]")
    else:
        console.print("[yellow]Invalid command format. Commands should start with '/'[/yellow]")

def show_api_menu():
    """Show available API commands"""
    menu = Table(title="API Testing Commands")
    menu.add_column("Command", style="cyan")
    menu.add_column("Description", style="green")
    
    # Authentication commands
    menu.add_row("/help", "Show this menu")
    menu.add_row("/login", "Login with existing user")
    menu.add_row("/register", "Register new user")
    menu.add_row("/logout", "Logout current user")
    menu.add_row("/refresh", "Refresh authentication token")
    menu.add_row("/status", "Show authentication status")
    menu.add_row("/premium", "Check premium status")
    
    # World commands
    menu.add_row("/worlds", "List your accessible worlds")
    menu.add_row("/create_world", "Create a new world")
    menu.add_row("/select_world", "Select a world to use")
    menu.add_row("/world_details", "Show details of current world")
    
    # Zone commands
    menu.add_row("/zones", "List zones in current world")
    menu.add_row("/create_zone", "Create a new zone")
    menu.add_row("/navigate_zones", "Navigate zone hierarchy")
    menu.add_row("/zone_upgrade", "Purchase zone limit upgrade")
    
    # Character commands
    menu.add_row("/characters", "List your characters")
    menu.add_row("/create_character", "Create a new character")
    
    # Conversation commands
    menu.add_row("/conversations", "List your conversations")
    menu.add_row("/create_conversation", "Create a new conversation")
    
    # Other commands
    menu.add_row("/endpoint", "Test any API endpoint")
    menu.add_row("/chat", "Return to chat mode")
    
    console.print(menu)

def interactive_create_character():
    """Interactive character creation"""
    console.print("[bold cyan]Create Character[/bold cyan]")
    name = Prompt.ask("Character Name")
    description = Prompt.ask("Description (optional)", default="")
    is_public = Confirm.ask("Make public?", default=False)
    
    character = create_character(name, description, is_public)
    if character:
        console.print(f"[bold green]Character created:[/bold green]")
        for key, value in character.items():
            console.print(f"[cyan]{key}:[/cyan] {value}")

def interactive_create_conversation():
    """Interactive conversation creation"""
    console.print("[bold cyan]Create Conversation[/bold cyan]")
    
    # Check if world and zone are selected
    if not state.current_world_id:
        console.print("[yellow]No world selected. Please select a world first.[/yellow]")
        if not select_world():
            return
    
    console.print(f"[blue]Creating conversation in world: {state.current_world_name}[/blue]")
    if state.current_zone_id:
        console.print(f"[blue]Current zone: {state.current_zone_name}[/blue]")
    
    title = Prompt.ask("Conversation Title", default="New Conversation")
    
    # Show available characters
    characters = get_characters()
    
    if not characters:
        console.print("[yellow]No characters available. Create a character first.[/yellow]")
        return
    
    console.print("[bold]Your Characters:[/bold]")
    for i, char in enumerate(characters):
        console.print(f"[cyan]{i+1}.[/cyan] {char['name']} (ID: {char['id']})")
    
    char_index = int(Prompt.ask("Select character (number)", default="1")) - 1
    if char_index < 0 or char_index >= len(characters):
        console.print("[yellow]Invalid selection[/yellow]")
        return
    
    character_id = characters[char_index]["id"]
    
    # Ask if user wants AI participants
    include_ai = Confirm.ask("Include AI participants?", default=True)
    agent_character_ids = []
    
    if include_ai:
        # Show available public characters
        public_chars = get_public_characters()
        
        if public_chars:
            console.print("[bold]Available AI Characters:[/bold]")
            for i, char in enumerate(public_chars):
                console.print(f"[cyan]{i+1}.[/cyan] {char['name']} (ID: {char['id']})")
            
            # Allow multiple selections
            selected = Prompt.ask("Select AI characters (comma-separated numbers)", default="1")
            try:
                indices = [int(x.strip()) - 1 for x in selected.split(",")]
                for idx in indices:
                    if idx >= 0 and idx < len(public_chars):
                        agent_character_ids.append(public_chars[idx]["id"])
            except:
                console.print("[yellow]Invalid selection, skipping AI characters[/yellow]")
    
    # Create the conversation
    conversation = create_conversation(title, character_id, agent_character_ids)
    
    if conversation:
        state.conversation_id = conversation["id"]
        console.print(f"[bold green]Conversation created! ID: {state.conversation_id}[/bold green]")
        
        # Find the user participant
        participants = conversation.get("participants", [])
        for participant in participants:
            if participant.get("user_id") == state.current_user_id:
                state.participant_id = participant.get("id")
                console.print(f"[green]Your participant ID: {state.participant_id}[/green]")
                break

def show_characters():
    """Show user's characters"""
    characters = get_characters()
    
    if not characters:
        console.print("[yellow]No characters found[/yellow]")
        return
    
    table = Table(title="Your Characters")
    table.add_column("ID", style="dim")
    table.add_column("Name", style="green")
    table.add_column("Description", style="cyan")
    table.add_column("Public", style="magenta")
    
    for char in characters:
        table.add_row(
            char["id"],
            char["name"],
            char.get("description", "").strip()[:30] + "..." if char.get("description", "") and len(char.get("description", "")) > 30 else char.get("description", ""),
            "✓" if char.get("is_public", False) else "✗"
        )
    
    console.print(table)

def show_conversations():
    """Show user's conversations"""
    conversations = get_conversations()
    
    if not conversations:
        console.print("[yellow]No conversations found[/yellow]")
        return
    
    table = Table(title="Your Conversations")
    table.add_column("ID", style="dim")
    table.add_column("Title", style="green")
    table.add_column("Created", style="blue")
    table.add_column("Updated", style="cyan")
    
    for conv in conversations:
        table.add_row(
            conv["id"],
            conv.get("title", "Untitled"),
            conv.get("created_at", "").split("T")[0] if conv.get("created_at") else "",
            conv.get("updated_at", "").split("T")[0] if conv.get("updated_at") else ""
        )
    
    console.print(table)

def show_auth_status():
    """Show current authentication status"""
    if state.access_token:
        console.print(f"[bold green]Logged in as: {state.user_email}[/bold green]")
        console.print(f"[green]User ID: {state.current_user_id}[/green]")
        console.print(f"[green]Premium: {state.is_premium}[/green]")
        token_parts = state.access_token.split('.')
        if len(token_parts) >= 2:
            try:
                # Get the payload part (second part of JWT)
                payload = json.loads(base64_decode_padding(token_parts[1]))
                expiry = payload.get("exp", 0)
                if expiry:
                    expiry_time = datetime.fromtimestamp(expiry)
                    now = datetime.now()
                    if expiry_time > now:
                        minutes_left = (expiry_time - now).seconds // 60
                        console.print(f"[green]Token expires in: {minutes_left} minutes[/green]")
                    else:
                        console.print("[yellow]Token expired![/yellow]")
            except:
                pass
    else:
        console.print("[yellow]Not logged in[/yellow]")

def base64_decode_padding(b64_string: str) -> str:
    """Add padding to base64 string if needed"""
    import base64
    
    # Add padding
    padding = 4 - (len(b64_string) % 4)
    if padding < 4:
        b64_string += "=" * padding
    
    # Decode
    try:
        decoded = base64.b64decode(b64_string)
        return decoded.decode('utf-8')
    except:
        return "{}"  # Return empty JSON if decoding fails

# ----------------------------
# WebSocket Connection
# ----------------------------

async def keep_alive(websocket, shared_state):
    """Send periodic pings to keep the connection alive"""
    try:
        while shared_state.connected and not shared_state.shutdown_requested:
            await asyncio.sleep(20)  # Send a ping every 20 seconds
            try:
                await websocket.send(json.dumps({"type": "ping"}))
            except Exception as e:
                print(f"[red]Ping failed: {e}[/red]")
                shared_state.connected = False
                break
    except asyncio.CancelledError:
        pass
    except Exception as e:
        print(f"[red]Keep-alive error: {e}[/red]")

def format_messages():
    """Format the message buffer for display"""
    result = ""
    for msg in message_buffer[-15:]:  # Show last 15 messages
        result += msg + "\n"
    return result

async def client():
    """Main client function"""
    # Ask for authentication first if not already authenticated
    if not state.access_token:
        auth_choice = Prompt.ask(
            "Authentication", 
            choices=["login", "register", "skip"], 
            default="login"
        )
        
        if auth_choice == "login":
            if not login_user():
                return
        elif auth_choice == "register":
            if not register_user():
                return
    
    # If authenticated, show worlds and offer world/zone selection
    if state.access_token:
        # Check premium status
        state.is_premium = check_premium_status()
        
        # Choose between API testing, World management, and WebSocket chat
        mode_choice = Prompt.ask(
            "Client mode", 
            choices=["chat", "world", "api"], 
            default="world"
        )
        
        if mode_choice == "api":
            state.api_mode = True
            show_api_menu()
            
            # Start the input thread for API mode
            input_thread = threading.Thread(
                target=get_input, 
                args=(state, [None]), 
                daemon=True
            )
            input_thread.start()
            
            # Keep the main thread running
            try:
                while not state.shutdown_requested:
                    await asyncio.sleep(0.1)
            except KeyboardInterrupt:
                state.shutdown_requested = True
                print("\n[yellow]Exiting client...[/yellow]")
            
            return
            
        elif mode_choice == "world":
            # Show world management UI
            world_menu()
            
            # After world management, ask if user wants to chat
            if Confirm.ask("Would you like to enter chat mode?", default=True):
                mode_choice = "chat"
            else:
                return
    
    # If we're in chat mode, we need to first select world and zone if not already selected
    if mode_choice == "chat":
        if not state.current_world_id:
            console.print("[yellow]You need to select a world before entering chat mode.[/yellow]")
            if not select_world():
                console.print("[yellow]Creating a default world...[/yellow]")
                interactive_create_world()
                if not state.current_world_id:
                    console.print("[red]Failed to create or select a world.[/red]")
                    return
        
        if not state.current_zone_id:
            console.print("[yellow]You need to select a zone before entering chat mode.[/yellow]")
            navigate_zones(state.current_world_id)
            if not state.current_zone_id:
                console.print("[yellow]Creating a default zone...[/yellow]")
                interactive_create_zone(state.current_world_id)
                if not state.current_zone_id:
                    console.print("[red]Failed to create or select a zone.[/red]")
                    return
    
    # If in chat mode, continue with conversation selection and WebSocket connection
    # Get conversation details if we don't have them
    if not state.conversation_id or not state.participant_id:
        # Show conversations
        show_conversations()
        
        console.print("[bold cyan]Select Conversation[/bold cyan]")
        choice = Prompt.ask(
            "Options", 
            choices=["select", "create", "exit"], 
            default="create"
        )
        
        if choice == "exit":
            return
        
        if choice == "create":
            interactive_create_conversation()
        else:  # select
            conversations = get_conversations()
            if not conversations:
                console.print("[yellow]No conversations available. Creating one.[/yellow]")
                interactive_create_conversation()
            else:
                console.print("[bold]Your Conversations:[/bold]")
                for i, conv in enumerate(conversations):
                    console.print(f"[cyan]{i+1}.[/cyan] {conv.get('title', 'Untitled')} (ID: {conv['id']})")
                
                conv_index = int(Prompt.ask("Select conversation (number)", default="1")) - 1
                if conv_index < 0 or conv_index >= len(conversations):
                    console.print("[yellow]Invalid selection[/yellow]")
                    return
                
                state.conversation_id = conversations[conv_index]["id"]
                
                # Get the conversation details to find the participant ID
                headers = {"Authorization": f"Bearer {state.access_token}"}
                response = requests.get(
                    f"{API_URL}/conversations/{state.conversation_id}", 
                    headers=headers
                )
                
                if response.status_code == 200:
                    conversation = response.json()
                    participants = conversation.get("participants", [])
                    
                    user_participants = [p for p in participants if p.get("user_id") == state.current_user_id]
                    
                    if not user_participants:
                        console.print("[yellow]No participants found for you in this conversation[/yellow]")
                        return
                    
                    if len(user_participants) == 1:
                        state.participant_id = user_participants[0].get("id")
                    else:
                        console.print("[bold]Your Participants:[/bold]")
                        for i, part in enumerate(user_participants):
                            char_id = part.get("character_id")
                            char_name = "Unknown"
                            if part.get("character") and part.get("character").get("name"):
                                char_name = part.get("character").get("name")
                            console.print(f"[cyan]{i+1}.[/cyan] {char_name} (ID: {part.get('id')})")
                        
                        part_index = int(Prompt.ask("Select participant (number)", default="1")) - 1
                        if part_index < 0 or part_index >= len(user_participants):
                            console.print("[yellow]Invalid selection[/yellow]")
                            return
                        
                        state.participant_id = user_participants[part_index].get("id")
                else:
                    console.print("[yellow]Error getting conversation details[/yellow]")
                    return
    
    # Now we have conversation_id and participant_id, connect to WebSocket
    uri = f"{WS_URL}/conversations/{state.conversation_id}?participant_id={state.participant_id}&access_token={state.access_token}"
    
    try:
        # Setup signal handlers for graceful shutdown
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, lambda: asyncio.create_task(shutdown(state)))
        
        websocket_ref = [None]  # Use a list to hold the websocket reference
        
        # Start the input thread
        input_thread = threading.Thread(
            target=get_input, 
            args=(state, websocket_ref), 
            daemon=True
        )
        input_thread.start()
        
        while not state.shutdown_requested:
            try:
                async with websockets.connect(uri, ping_interval=30, ping_timeout=10) as websocket:
                    websocket_ref[0] = websocket
                    state.connected = True
                    
                    console.print("[green]Connected to chat server![/green]")
                    message_buffer.append("[green]Connected to chat server![/green]")
                    
                    # Display current world and zone information
                    console.print(f"[blue]World: {state.current_world_name} | Zone: {state.current_zone_name}[/blue]")
                    message_buffer.append(f"[blue]World: {state.current_world_name} | Zone: {state.current_zone_name}[/blue]")
                    
                    # Start keep-alive task
                    keep_alive_task = asyncio.create_task(keep_alive(websocket, state))
                    
                    # Continuously receive messages
                    try:
                        while state.connected and not state.shutdown_requested:
                            try:
                                message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                                await process_message(message)
                            except asyncio.TimeoutError:
                                # This is normal, just keep checking
                                continue
                            except websockets.exceptions.ConnectionClosed:
                                console.print("[yellow]Connection closed by server[/yellow]")
                                message_buffer.append("[yellow]Connection closed by server[/yellow]")
                                state.connected = False
                                break
                    finally:
                        # Cancel keep-alive task
                        keep_alive_task.cancel()
                        try:
                            await keep_alive_task
                        except asyncio.CancelledError:
                            pass
                
                if not state.shutdown_requested:
                    console.print("[yellow]Disconnected. Attempting to reconnect in 5 seconds...[/yellow]")
                    message_buffer.append("[yellow]Disconnected. Attempting to reconnect...[/yellow]")
                    await asyncio.sleep(5)
            
            except websockets.exceptions.ConnectionRefusedError:
                console.print("[red]Could not connect to server. Retrying in 5 seconds...[/red]")
                message_buffer.append("[red]Could not connect to server. Retrying...[/red]")
                await asyncio.sleep(5)
            
            except Exception as e:
                console.print(f"[red]Connection error: {e}. Retrying in 5 seconds...[/red]")
                message_buffer.append(f"[red]Connection error. Retrying...[/red]")
                await asyncio.sleep(5)
    
    except asyncio.CancelledError:
        console.print("[yellow]Client shutting down...[/yellow]")
    
    finally:
        state.shutdown_requested = True
        websocket_ref[0] = None

async def process_message(message):
    """Process messages received from the server"""
    try:
        data = json.loads(message)
    except json.JSONDecodeError:
        console.print(f"[red]Failed to decode message: {message}[/red]")
        return
    
    # Handle different event types
    event_type = data.get("type")
    
    if event_type == "system":
        # System message (yellow)
        formatted_msg = f"[yellow]{data.get('content')}[/yellow]"
        console.print(f"\n{formatted_msg}")
        message_buffer.append(formatted_msg)
    
    elif event_type == "message":
        # Message event
        msg = data.get("message", {})
        sender_name = msg.get("character_name", "Unknown")
        content = msg.get("content", "")
        
        # Format the message
        if msg.get("user_id") == state.current_user_id:
            formatted_msg = f"[blue italic]{sender_name}[/blue italic]: {content}"
        else:
            formatted_msg = f"[blue]{sender_name}[/blue]: {content}"
            
        console.print(f"\n{formatted_msg}")
        message_buffer.append(formatted_msg)
        
        # Print a new prompt to make it clear where to type
        console.print("> ", end="")
    
    elif event_type == "typing":
        # Typing notification
        user_id = data.get("user_id")
        participant_id = data.get("participant_id")
        is_typing = data.get("is_typing", True)
        
        # You could display typing indicators here
        pass
    
    elif event_type == "presence":
        # Presence information
        active_users = data.get("active_users", [])
        # You could display who's online here
        pass
    
    elif event_type == "usage_update" or event_type == "usage_limits":
        # Update usage info
        usage = data.get("usage", {})
        messages_remaining = usage.get("messages_remaining_today", 0)
        is_premium = usage.get("is_premium", False)
        state.is_premium = is_premium
        
        # Show usage info in compact form at bottom of console
        console.print(f"\n[dim]Messages remaining today: {messages_remaining} | Premium: {is_premium}[/dim]")
    
    elif event_type == "error":
        # Error message
        error = data.get("error", "Unknown error")
        formatted_msg = f"[red]Error: {error}[/red]"
        console.print(f"\n{formatted_msg}")
        message_buffer.append(formatted_msg)
    
    elif event_type == "pong":
        # Server responded to ping
        pass
    
    else:
        # Unknown event type - just print the raw data in dim color
        formatted_msg = f"[dim]{data}[/dim]"
        console.print(f"\n{formatted_msg}")
        message_buffer.append(formatted_msg)

async def shutdown(shared_state):
    """Handle graceful shutdown"""
    console.print("\n[yellow]Shutting down client...[/yellow]")
    shared_state.shutdown_requested = True

def display_welcome():
    """Display welcome message and instructions."""
    os.system('cls' if os.name == 'nt' else 'clear')
    
    title = Text("RPG CHAT CLIENT", style="bold cyan")
    console.print(Panel(title, expand=False))
    
    welcome_text = (
        "Welcome to the Enhanced RPG Chat Client!\n\n"
        "This client supports world navigation, zone management, and real-time chat.\n"
        "- First select or create a world where your adventure takes place\n"
        "- Then explore and navigate through different zones in your world\n"
        "- Create characters and start conversations in your chosen zones\n"
        "- In chat mode, your messages will be transformed to match your character's voice\n\n"
        "Commands:\n"
        "- Type '/api' to switch to API testing mode\n"
        "- Type '/chat' to switch back to chat mode\n"
        "- Type 'exit' or 'quit' to leave\n\n"
        "- In API mode, type '/help' for a list of available commands"
    )
    
    console.print(Panel(welcome_text, title="Welcome", border_style="blue"))

if __name__ == "__main__":
    try:
        display_welcome()
        
        # Check if URLs are provided as arguments
        if len(sys.argv) > 1:
            API_URL = sys.argv[1]
        if len(sys.argv) > 2:
            WS_URL = sys.argv[2]
        
        console.print(f"[dim]API URL: {API_URL}[/dim]")
        console.print(f"[dim]WebSocket URL: {WS_URL}[/dim]")
        
        asyncio.run(client())
    except KeyboardInterrupt:
        print("\n[yellow]Exiting client...[/yellow]")
    except Exception as e:
        print(f"[red]Error: {e}[/red]")