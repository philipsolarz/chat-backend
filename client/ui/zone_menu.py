#!/usr/bin/env python
# Zone navigation and management menu
import asyncio
from typing import Dict, Any, Optional, List, Tuple

from client.api.zone_service import ZoneService
from client.api.world_service import WorldService
from client.game.state import game_state
from client.ui.console import (
    console, clear_screen, show_title, show_error, show_success, show_warning, show_info,
    prompt_input, confirm_action, create_menu, display_loading, display_table,
    prompt_select_item, show_details
)


class ZoneMenu:
    """User interface for zone navigation and management"""
    
    def __init__(self):
        self.zone_service = ZoneService()
        self.world_service = WorldService()
        self.current_parent_id = None  # For zone navigation
    
    async def show_zone_selection(self) -> bool:
        """Show zone selection screen for the current world"""
        if not game_state.current_world_id:
            show_error("No world selected. Please select a world first.")
            return False
            
        # First load available zones
        zones = await display_loading(
            "Loading zones...",
            self.zone_service.get_zones(game_state.current_world_id)
        )
        
        show_title(f"Zone Selection - {game_state.current_world_name}", 
                   "Select a zone to enter or create your own")
        
        if not zones:
            show_warning("No zones found in this world. You can create a new zone.")
            
            # Prompt to create a new zone
            if confirm_action("Would you like to create a new zone?", default=True):
                return await self.create_zone()
            else:
                return False
        
        # Display zones in a table
        display_table(
            "Available Zones",
            zones,
            [
                ("id", "ID", "dim"),
                ("name", "Name", "green"),
                ("zone_type", "Type", "blue"),
                ("description", "Description", "cyan")
            ]
        )
        
        # Show options menu
        options = [
            ("select", "Select a zone to enter"),
            ("navigate", "Navigate zone hierarchy"),
            ("create", "Create a new zone"),
            ("back", "Back to world menu")
        ]
        
        choice = create_menu("Zone Options", options)
        
        if choice == "select":
            return await self.select_zone(zones)
        elif choice == "navigate":
            return await self.navigate_zones()
        elif choice == "create":
            return await self.create_zone()
        elif choice == "back":
            return False
        else:
            return False
    
    async def select_zone(self, zones: List[Dict[str, Any]] = None) -> bool:
        """Select a zone from the list"""
        if not zones:
            # If zones were not provided, fetch them
            if not game_state.current_world_id:
                show_error("No world selected. Please select a world first.")
                return False
                
            zones = await display_loading(
                "Loading zones...",
                self.zone_service.get_zones(game_state.current_world_id, self.current_parent_id)
            )
            
            if not zones:
                if self.current_parent_id:
                    parent_zone = await self.zone_service.get_zone(self.current_parent_id)
                    parent_name = parent_zone.get("name", "Unknown") if parent_zone else "Unknown"
                    show_warning(f"No sub-zones found in {parent_name}")
                else:
                    show_warning("No zones found in this world")
                return False
        
        zone_id = prompt_select_item(
            zones,
            id_key="id",
            name_key="name",
            prompt_text="Select zone",
            extra_info_key="zone_type"
        )
        
        if not zone_id:
            show_warning("No zone selected")
            return False
        
        # Get full zone details
        zone = await display_loading(
            f"Loading zone details...",
            self.zone_service.get_zone(zone_id)
        )
        
        if not zone:
            show_error("Failed to load zone details")
            return False
        
        # Update current zone in state
        game_state.current_zone_id = zone["id"]
        game_state.current_zone_name = zone["name"]
        
        show_success(f"Selected zone: {zone['name']}")
        
        # Show zone details
        await self.show_zone_details(zone)
        
        if confirm_action("Enter this zone?", default=True):
            return True
        else:
            # Clear zone selection if user decides not to enter
            game_state.clear_zone()
            return False
    
    async def navigate_zones(self) -> bool:
        """Interactive zone navigation for the current world"""
        if not game_state.current_world_id:
            show_error("No world selected. Please select a world first.")
            return False
            
        self.current_parent_id = None  # Start at top level
        current_path = ["Top Level"]
        
        while True:
            clear_screen()
            show_title(f"Zone Navigation - {game_state.current_world_name}", 
                       "Navigate through zone hierarchy")
            
            # Show breadcrumb navigation
            console.print("[bold]Current location:[/bold]")
            console.print(" > ".join(f"[blue]{crumb}[/blue]" for crumb in current_path))
            console.print()
            
            # Get zones at current level
            zones = await display_loading(
                "Loading zones...",
                self.zone_service.get_zones(game_state.current_world_id, self.current_parent_id)
            )
            
            if not zones:
                show_warning("No zones found at this level")
            else:
                # Display zones in a table
                display_table(
                    "Zones at this level",
                    zones,
                    [
                        ("id", "ID", "dim"),
                        ("name", "Name", "green"),
                        ("zone_type", "Type", "blue"),
                        ("description", "Description", "cyan")
                    ]
                )
            
            # Show options menu
            options = []
            
            if zones:
                options.append(("select", "Select a zone"))
                
            options.append(("create", "Create new zone at this level"))
            
            if self.current_parent_id:  # Only if we're not at the top level
                options.append(("up", "Go up a level"))
                
            options.append(("exit", "Exit navigation"))
            
            choice = create_menu("Navigation Options", options)
            
            if choice == "select" and zones:
                zone_id = prompt_select_item(
                    zones,
                    id_key="id",
                    name_key="name",
                    prompt_text="Select zone",
                    extra_info_key="zone_type"
                )
                
                if zone_id:
                    # Get full zone details
                    zone = await display_loading(
                        f"Loading zone details...",
                        self.zone_service.get_zone(zone_id)
                    )
                    
                    if zone:
                        show_title(f"Zone: {zone['name']}", "Select action")
                        
                        # Show options for this zone
                        zone_options = [
                            ("details", "View zone details"),
                            ("enter", "Enter this zone"),
                            ("subzones", "View sub-zones"),
                            ("edit", "Edit zone settings"),
                            ("delete", "Delete zone"),
                            ("agent-limits", "View agent limits"),
                            ("back", "Back to navigation")
                        ]
                        
                        zone_choice = create_menu(f"Zone: {zone['name']}", zone_options)
                        
                        if zone_choice == "details":
                            await self.show_zone_details(zone)
                        elif zone_choice == "enter":
                            # Update current zone in state
                            game_state.current_zone_id = zone["id"]
                            game_state.current_zone_name = zone["name"]
                            show_success(f"Selected zone: {zone['name']}")
                            return True
                        elif zone_choice == "subzones":
                            # Navigate to sub-zones
                            self.current_parent_id = zone["id"]
                            current_path.append(zone["name"])
                        elif zone_choice == "edit":
                            await self.edit_zone(zone)
                        elif zone_choice == "delete":
                            if await self.delete_zone(zone):
                                # Refresh the zone list
                                continue
                        elif zone_choice == "agent-limits":
                            await self.show_agent_limits(zone)
                        
            elif choice == "create":
                if await self.create_zone(self.current_parent_id):
                    # Zone created successfully
                    return True
                    
            elif choice == "up" and self.current_parent_id:
                # Go up a level
                parent_zone = await self.zone_service.get_zone(self.current_parent_id)
                self.current_parent_id = parent_zone.get("parent_zone_id") if parent_zone else None
                current_path.pop()
                
            elif choice == "exit":
                return False  # Exit navigation
    
    async def create_zone(self, parent_zone_id: Optional[str] = None) -> bool:
        """Create a new zone"""
        if not game_state.current_world_id:
            show_error("No world selected. Please select a world first.")
            return False
            
        # Show parent zone info if available
        if parent_zone_id:
            parent_zone = await self.zone_service.get_zone(parent_zone_id)
            if parent_zone:
                show_info(f"Creating sub-zone in: {parent_zone['name']}")
                
        show_title("Create Zone", "Create a new zone in your world")
        
        name = prompt_input("Name", "Enter a name for your zone:")
        description = prompt_input("Description", "Enter a description (optional):", default="", multiline=True)
        
        # Suggest some zone types
        zone_types = [
            "city", "town", "village", "forest", "mountains", "plains", 
            "desert", "ocean", "dungeon", "castle", "ruin", "cave"
        ]
        
        console.print("\n[bold]Suggested Zone Types:[/bold]")
        for i, zone_type in enumerate(zone_types, 1):
            console.print(f"[cyan]{i}.[/cyan] {zone_type}")
        console.print("[cyan]0.[/cyan] Custom type")
        
        type_choice = prompt_input("ZoneType", "Select zone type (number or enter custom)", default="0")
        if type_choice.isdigit():
            choice = int(type_choice)
            if 1 <= choice <= len(zone_types):
                zone_type = zone_types[choice - 1]
            else:
                zone_type = prompt_input("CustomType", "Enter custom zone type", default="general")
        else:
            zone_type = type_choice
        
        # Create the zone
        zone = await display_loading(
            "Creating zone...",
            self.zone_service.create_zone(
                game_state.current_world_id, 
                name, 
                description, 
                zone_type, 
                parent_zone_id
            )
        )
        
        if not zone:
            show_error("Failed to create zone")
            return False
        
        show_success(f"Zone '{name}' created successfully!")
        
        # Zone is already set in state by the service
        
        if confirm_action("Enter your new zone?", default=True):
            return True
        else:
            # Clear zone selection if user decides not to enter
            game_state.clear_zone()
            return False
    
    async def edit_zone(self, zone: Dict[str, Any]) -> bool:
        """Edit zone settings"""
        # Check world ownership
        world = await self.world_service.get_world(zone["world_id"])
        if not world or world.get("owner_id") != game_state.current_user_id:
            show_error("Only the world owner can edit zones")
            return False
            
        show_title(f"Edit Zone: {zone['name']}", "Change zone settings")
        
        name = prompt_input("Name", "Enter new name (leave blank to keep current):", default=zone["name"])
        description = prompt_input("Description", "Enter new description (leave blank to keep current):", default=zone.get("description", ""), multiline=True)
        zone_type = prompt_input("Type", "Enter new zone type (leave blank to keep current):", default=zone.get("zone_type", ""))
        
        # Prepare update data
        update_data = {}
        if name != zone["name"]:
            update_data["name"] = name
        if description != zone.get("description"):
            update_data["description"] = description
        if zone_type != zone.get("zone_type"):
            update_data["zone_type"] = zone_type
        
        if not update_data:
            show_warning("No changes made")
            return False
        
        # Update the zone
        updated_zone = await display_loading(
            "Updating zone...",
            self.zone_service.update_zone(zone["id"], update_data)
        )
        
        if not updated_zone:
            show_error("Failed to update zone")
            return False
        
        show_success(f"Zone '{updated_zone['name']}' updated successfully!")
        
        # Update current zone name in state if this is the current zone
        if game_state.current_zone_id == zone["id"]:
            game_state.current_zone_name = updated_zone["name"]
        
        return True
    
    async def delete_zone(self, zone: Dict[str, Any]) -> bool:
        """Delete a zone"""
        # Check world ownership
        world = await self.world_service.get_world(zone["world_id"])
        if not world or world.get("owner_id") != game_state.current_user_id:
            show_error("Only the world owner can delete zones")
            return False
            
        show_title(f"Delete Zone: {zone['name']}", "Warning: This action cannot be undone")
        
        # Confirm deletion
        if not confirm_action(
            f"Are you sure you want to permanently delete the zone '{zone['name']}'?", 
            default=False
        ):
            show_warning("Zone deletion cancelled")
            return False
        
        # If this is the current zone, warn the user
        if zone["id"] == game_state.current_zone_id:
            show_warning("You are currently in this zone. Deleting it will return you to the world selection.")
            if not confirm_action("Continue with deletion?", default=False):
                show_warning("Zone deletion cancelled")
                return False
        
        # Delete the zone
        result = await display_loading(
            "Deleting zone...",
            self.zone_service.delete_zone(zone["id"])
        )
        
        if not result:
            show_error("Failed to delete zone")
            return False
        
        show_success(f"Zone '{zone['name']}' deleted successfully!")
        
        # Zone is already cleared from state by the service if it was the current zone
        
        return True
    
    async def show_zone_details(self, zone: Optional[Dict[str, Any]] = None) -> None:
        """Show detailed information about a zone"""
        if not zone and not game_state.current_zone_id:
            show_error("No zone selected")
            return
            
        if not zone:
            # Get zone details
            zone = await display_loading(
                "Loading zone details...",
                self.zone_service.get_zone(game_state.current_zone_id)
            )
            
            if not zone:
                show_error("Failed to load zone details")
                return
                
        show_title(f"Zone: {zone['name']}", "Zone Details")
        
        # Get number of sub-zones
        sub_zones = await self.zone_service.get_zones(zone["world_id"], zone["id"])
        sub_zone_count = len(sub_zones)
        
        # Get characters in zone
        characters = await self.zone_service.get_zone_characters(zone["id"])
        character_count = len(characters)
        
        # Get agents in zone
        agents = await self.zone_service.get_zone_agents(zone["id"])
        agent_count = len(agents)
        
        # Show basic zone details
        show_details(
            f"Zone Information",
            {
                "ID": zone["id"],
                "Name": zone["name"],
                "Type": zone.get("zone_type", "general"),
                "Description": zone.get("description", "N/A"),
                "Sub-zones": sub_zone_count,
                "Characters": character_count,
                "NPCs/Agents": agent_count,
                "World": game_state.current_world_name
            },
            highlight_fields=["Name", "Type"]
        )
        
        # Show characters in zone if any
        if characters:
            console.print("\n[bold]Characters in this zone:[/bold]")
            for i, char in enumerate(characters, 1):
                console.print(f"[cyan]{i}.[/cyan] {char['name']}")
        
        # Show agents in zone if any
        if agents:
            console.print("\n[bold]NPCs/Agents in this zone:[/bold]")
            for i, agent in enumerate(agents, 1):
                console.print(f"[magenta]{i}.[/magenta] {agent['name']}")
        
        # Wait for user to press enter
        input("\nPress Enter to continue...")
    
    async def show_agent_limits(self, zone: Dict[str, Any]) -> None:
        """Show agent limit information and purchase options"""
        # Get agent limits
        limits = await display_loading(
            "Loading agent limits...",
            self.zone_service.get_agent_limits(zone["id"])
        )
        
        if not limits:
            show_error("Failed to load agent limits")
            return
            
        show_title(f"Agent Limits - {zone['name']}", "Agent capacity and upgrade options")
        
        # Show limit details
        show_details(
            f"Agent Limits",
            {
                "Current Agent Count": limits.get("agent_count", 0),
                "Base Agent Limit": limits.get("base_limit", 25),
                "Agent Upgrades Purchased": limits.get("upgrades_purchased", 0),
                "Total Agent Limit": limits.get("total_limit", 25),
                "Remaining Capacity": limits.get("remaining_capacity", 25)
            },
            highlight_fields=["Total Agent Limit", "Remaining Capacity"]
        )
        
        console.print("\n[bold]Each agent upgrade costs $9.99 and increases your agent limit by 10.[/bold]")
        
        # Check if low on capacity
        if limits.get("remaining_capacity", 25) < 5:
            show_warning("WARNING: You are approaching your agent limit!")
        
        # Check if user can purchase upgrades
        if limits.get("can_purchase_upgrade", False):
            if confirm_action("Would you like to purchase an agent limit upgrade?", default=False):
                await self.purchase_agent_limit_upgrade(zone["id"])
        else:
            show_warning("Only the world owner can purchase agent limit upgrades")
            
        # Wait for user to press enter
        input("\nPress Enter to continue...")
    
    async def purchase_agent_limit_upgrade(self, zone_id: str) -> bool:
        """Purchase an agent limit upgrade"""
        show_title("Purchase Agent Limit Upgrade", "Upgrade your zone's agent capacity")
        
        console.print("[bold yellow]This will initiate a purchase for $9.99[/bold yellow]")
        console.print("Each upgrade increases your zone's agent limit by 10 agents.")
        
        if not confirm_action("Continue with agent limit upgrade purchase?", default=False):
            show_warning("Agent limit upgrade purchase cancelled")
            return False
            
        result = await display_loading(
            "Initiating agent limit upgrade purchase...",
            self.zone_service.purchase_agent_limit_upgrade(zone_id)
        )
        
        if not result or "checkout_url" not in result:
            show_error("Failed to initiate agent limit upgrade purchase")
            return False
            
        # Show checkout URL
        show_success("Agent limit upgrade purchase initiated!")
        console.print(f"\nPlease complete your purchase at:")
        console.print(f"[blue underline]{result['checkout_url']}[/blue underline]")
        console.print("\nAfter payment, your agent limit will increase automatically.")
        
        return True
    
    async def purchase_zone_upgrade(self) -> bool:
        """Purchase a zone limit upgrade for the current world"""
        if not game_state.current_world_id:
            show_error("No world selected. Please select a world first.")
            return False
            
        # Get world details
        world = await display_loading(
            "Loading world details...",
            self.world_service.get_world(game_state.current_world_id)
        )
        
        if not world:
            show_error("Failed to load world details")
            return False
            
        # Check if user is the owner
        if world.get("owner_id") != game_state.current_user_id:
            show_error("Only the world owner can purchase zone upgrades")
            return False
            
        show_title("Purchase Zone Upgrade", "Upgrade your world's zone capacity")
        
        console.print("[bold yellow]This will initiate a purchase for $49.99[/bold yellow]")
        console.print("Each upgrade increases your world's zone limit by 100 zones.")
        
        # Calculate zone information
        zones = await self.zone_service.get_zones(game_state.current_world_id)
        zone_count = len(zones)
        zone_limit = world.get("zone_limit", 100)
        zone_upgrades = world.get("zone_limit_upgrades", 0)
        total_limit = world.get("total_zone_limit", zone_limit + (zone_upgrades * 100))
        
        # Show current zone limits
        show_details(
            f"Zone Limits for {world['name']}",
            {
                "Current Zone Count": zone_count,
                "Base Zone Limit": zone_limit,
                "Zone Upgrades Purchased": zone_upgrades,
                "Total Zone Limit": total_limit,
                "Remaining Capacity": total_limit - zone_count
            },
            highlight_fields=["Total Zone Limit", "Remaining Capacity"]
        )
        
        if zone_count >= total_limit - 20:
            show_warning("WARNING: You are approaching your zone limit!")
            
        if not confirm_action("Continue with zone upgrade purchase?", default=False):
            show_warning("Zone upgrade purchase cancelled")
            return False
            
        result = await display_loading(
            "Initiating zone upgrade purchase...",
            self.zone_service.purchase_zone_upgrade(game_state.current_world_id)
        )
        
        if not result or "checkout_url" not in result:
            show_error("Failed to initiate zone upgrade purchase")
            return False
            
        # Show checkout URL
        show_success("Zone upgrade purchase initiated!")
        console.print(f"\nPlease complete your purchase at:")
        console.print(f"[blue underline]{result['checkout_url']}[/blue underline]")
        console.print("\nAfter payment, your zone limit will increase automatically.")
        
        return True
    
    async def show_zone_menu(self) -> Optional[str]:
        """Show zone management menu"""
        if game_state.current_zone_id:
            subtitle = f"Current Zone: {game_state.current_zone_name}"
            
            options = [
                ("enter", "Enter current zone"),
                ("change", "Change zone"),
                ("detail", "View zone details"),
                ("edit", "Edit zone settings"),
                ("create", "Create new zone"),
                ("navigate", "Navigate zones"),
                ("upgrade", "Purchase zone upgrade"),
                ("agent-limits", "View agent limits"),
                ("back", "Back to world menu")
            ]
        else:
            subtitle = "No zone selected"
            
            options = [
                ("select", "Select zone"),
                ("create", "Create new zone"),
                ("navigate", "Navigate zones"),
                ("upgrade", "Purchase zone upgrade"),
                ("back", "Back to world menu")
            ]
        
        choice = create_menu("Zone Management", options, subtitle)
        
        if not game_state.current_zone_id:
            # Handle options when no zone is selected
            if choice == "select":
                result = await self.show_zone_selection()
                return "enter" if result else "refresh"
            elif choice == "create":
                result = await self.create_zone()
                return "enter" if result else "refresh"
            elif choice == "navigate":
                result = await self.navigate_zones()
                return "enter" if result else "refresh"
            elif choice == "upgrade":
                await self.purchase_zone_upgrade()
                return "refresh"
        else:
            # Handle options when a zone is selected
            if choice == "enter":
                return "enter"
            elif choice == "change":
                result = await self.show_zone_selection()
                return "enter" if result else "refresh"
            elif choice == "detail":
                await self.show_zone_details()
                return "refresh"
            elif choice == "edit":
                zone = await self.zone_service.get_zone(game_state.current_zone_id)
                if zone:
                    await self.edit_zone(zone)
                return "refresh"
            elif choice == "create":
                result = await self.create_zone()
                return "enter" if result else "refresh"
            elif choice == "navigate":
                result = await self.navigate_zones()
                return "enter" if result else "refresh"
            elif choice == "upgrade":
                await self.purchase_zone_upgrade()
                return "refresh"
            elif choice == "agent-limits":
                zone = await self.zone_service.get_zone(game_state.current_zone_id)
                if zone:
                    await self.show_agent_limits(zone)
                return "refresh"
        
        return choice