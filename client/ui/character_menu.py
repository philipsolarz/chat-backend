#!/usr/bin/env python
# Character selection and management menu
import asyncio
from typing import Dict, Any, Optional, List, Tuple

from client.api.character_service import CharacterService
from client.api.zone_service import ZoneService
from client.game.state import game_state
from client.ui.console import (
    console, clear_screen, show_title, show_error, show_success, show_warning,
    prompt_input, confirm_action, create_menu, display_loading, display_table,
    prompt_select_item, show_details
)


class CharacterMenu:
    """User interface for character selection and management"""
    
    def __init__(self):
        self.character_service = CharacterService()
        self.zone_service = ZoneService()
    
    async def show_character_selection(self) -> bool:
        """Show character selection screen for current world"""
        if not game_state.current_world_id:
            show_error("No world selected")
            return False
            
        # First load available characters in this world
        all_characters = await display_loading(
            "Loading characters...",
            self.character_service.get_characters()
        )
        
        # Filter to current world
        world_characters = [c for c in all_characters if c.get("world_id") == game_state.current_world_id]
        
        show_title(
            f"Character Selection - {game_state.current_world_name}", 
            "Select a character to play or create a new one"
        )
        
        if not world_characters:
            show_warning("You don't have any characters in this world. Create a new character to continue.")
            
            # Skip to character creation
            return await self.create_character()
        
        # Display characters in a table
        display_table(
            "Your Characters in this World",
            world_characters,
            [
                ("id", "ID", "dim"),
                ("name", "Name", "green"),
                ("zone_id", "Zone", "blue"),
                ("description", "Description", "cyan")
            ]
        )
        
        # Show options menu
        options = [
            ("select", "Select an existing character"),
            ("create", "Create a new character"),
            ("back", "Back to world menu")
        ]
        
        choice = create_menu("Character Options", options)
        
        if choice == "select":
            return await self.select_character(world_characters)
        elif choice == "create":
            return await self.create_character()
        else:
            return False
    
    async def select_character(self, characters: List[Dict[str, Any]]) -> bool:
        """Select a character from the list"""
        character_id = prompt_select_item(
            characters,
            id_key="id",
            name_key="name",
            prompt_text="Select character",
            extra_info_key="description"
        )
        
        if not character_id:
            show_warning("No character selected")
            return False
        
        # Get full character details
        character = await display_loading(
            f"Loading character details...",
            self.character_service.get_character(character_id)
        )
        
        if not character:
            show_error("Failed to load character details")
            return False
        
        # Update current character in state
        game_state.current_character_id = character["id"]
        game_state.current_character_name = character["name"]
        
        # Also update current zone if the character has one
        if character.get("zone_id"):
            # Get zone details
            zone = await self.zone_service.get_zone(character["zone_id"])
            if zone:
                game_state.current_zone_id = zone["id"]
                game_state.current_zone_name = zone["name"]
        
        show_success(f"Selected character: {character['name']}")
        
        # Show character details
        show_details(
            f"Character: {character['name']}",
            {
                "ID": character["id"],
                "Name": character["name"],
                "Description": character.get("description", "N/A"),
                "Public": "Yes" if character.get("is_public", False) else "No",
                "Zone": game_state.current_zone_name if game_state.current_zone_id else "None"
            },
            highlight_fields=["Name", "Zone"]
        )
        
        if confirm_action("Play as this character?", default=True):
            return True
        else:
            # Clear character selection if user decides not to play
            game_state.clear_character()
            return False
    
    async def create_character(self) -> bool:
        """Create a new character"""
        if not game_state.current_world_id:
            show_error("No world selected")
            return False
            
        show_title(
            f"Create Character - {game_state.current_world_name}", 
            "Create a new character to play in this world"
        )
        
        name = prompt_input("Name", "Enter a name for your character:")
        description = prompt_input(
            "Description", 
            "Enter a description of your character (personality, appearance, etc.):", 
            default="", 
            multiline=True
        )
        
        # Get zones in the world for selection
        zones = await display_loading(
            "Loading zones...",
            self.zone_service.get_zones(game_state.current_world_id)
        )
        
        zone_id = None
        
        if zones:
            # Prompt for zone selection
            console.print("\n[bold]Choose a starting zone:[/bold]")
            zone_id = prompt_select_item(
                zones,
                id_key="id",
                name_key="name",
                prompt_text="Select starting zone",
                extra_info_key="zone_type"
            )
        else:
            show_warning("No zones found in this world. Character will be created without a zone.")
        
        is_public = False
        
        # Premium users can make characters public
        if game_state.is_premium:
            is_public = confirm_action(
                "Make this character public? (Public characters can be used by AI agents)", 
                default=False
            )
        
        # Create the character
        character = await display_loading(
            "Creating character...",
            self.character_service.create_character(
                name, 
                description, 
                is_public,
                world_id=game_state.current_world_id,
                zone_id=zone_id
            )
        )
        
        if not character:
            show_error("Failed to create character")
            return False
        
        show_success(f"Character '{name}' created successfully!")
        
        # Character is already set in state by the service
        
        # Also update current zone if a zone was selected
        if zone_id:
            # Get zone details
            zone = await self.zone_service.get_zone(zone_id)
            if zone:
                game_state.current_zone_id = zone["id"]
                game_state.current_zone_name = zone["name"]
        
        if confirm_action("Play as your new character?", default=True):
            return True
        else:
            # Clear character selection if user decides not to play
            game_state.clear_character()
            return False
    
    async def show_character_menu(self) -> Optional[str]:
        """Show character management menu"""
        if game_state.current_character_id:
            subtitle = f"Current Character: {game_state.current_character_name}"
            
            options = [
                ("play", "Play as current character"),
                ("change", "Change character"),
                ("detail", "View character details"),
                ("edit", "Edit character"),
                ("move", "Move to different zone"),
                ("delete", "Delete character"),
                ("back", "Back to world menu")
            ]
        else:
            subtitle = "No character selected"
            
            options = [
                ("select", "Select character"),
                ("create", "Create new character"),
                ("back", "Back to world menu")
            ]
        
        choice = create_menu("Character Management", options, subtitle)
        
        if not game_state.current_character_id:
            # Handle options when no character is selected
            if choice == "select":
                result = await self.show_character_selection()
                return "play" if result else "refresh"
            elif choice == "create":
                result = await self.create_character()
                return "play" if result else "refresh"
        else:
            # Handle options when a character is selected
            if choice == "play":
                return "play"
            elif choice == "change":
                result = await self.show_character_selection()
                return "play" if result else "refresh"
            elif choice == "detail":
                await self.show_character_details()
                return "refresh"
            elif choice == "edit":
                await self.edit_character()
                return "refresh"
            elif choice == "move":
                await self.move_character()
                return "refresh"
            elif choice == "delete":
                result = await self.delete_character()
                return "refresh"
        
        return choice
    
    async def show_character_details(self) -> None:
        """Show detailed information about the current character"""
        if not game_state.current_character_id:
            show_error("No character selected")
            return
        
        character = await display_loading(
            "Loading character details...",
            self.character_service.get_character(game_state.current_character_id)
        )
        
        if not character:
            show_error("Failed to load character details")
            return
        
        show_title(f"Character: {character['name']}", "Character Details")
        
        # Get zone info if available
        zone_name = "None"
        if character.get("zone_id"):
            zone = await self.zone_service.get_zone(character["zone_id"])
            if zone:
                zone_name = zone["name"]
        
        # Show details
        show_details(
            f"Character Information",
            {
                "ID": character["id"],
                "Name": character["name"],
                "Description": character.get("description", "N/A"),
                "Public": "Yes" if character.get("is_public", False) else "No",
                "World": game_state.current_world_name,
                "Zone": zone_name,
                "Template": "Yes" if character.get("is_template", False) else "No"
            },
            highlight_fields=["Name", "Zone"]
        )
        
        # Wait for user to press enter
        input("\nPress Enter to continue...")
    
    async def edit_character(self) -> bool:
        """Edit character settings"""
        if not game_state.current_character_id:
            show_error("No character selected")
            return False
        
        character = await display_loading(
            "Loading character details...",
            self.character_service.get_character(game_state.current_character_id)
        )
        
        if not character:
            show_error("Failed to load character details")
            return False
        
        show_title(f"Edit Character: {character['name']}", "Change character settings")
        
        name = prompt_input("Name", "Enter new name (leave blank to keep current):", default=character["name"])
        description = prompt_input(
            "Description", 
            "Enter new description (leave blank to keep current):", 
            default=character.get("description", ""), 
            multiline=True
        )
        
        is_public = character.get("is_public", False)
        
        # Premium users can change public status
        if game_state.is_premium:
            is_public = confirm_action(
                "Make this character public? (Public characters can be used by AI agents)", 
                default=is_public
            )
        
        # Prepare update data
        update_data = {}
        if name != character["name"]:
            update_data["name"] = name
        if description != character.get("description"):
            update_data["description"] = description
        if is_public != character.get("is_public"):
            update_data["is_public"] = is_public
        
        if not update_data:
            show_warning("No changes made")
            return False
        
        # Update the character
        updated_character = await display_loading(
            "Updating character...",
            self.character_service.update_character(game_state.current_character_id, update_data)
        )
        
        if not updated_character:
            show_error("Failed to update character")
            return False
        
        show_success(f"Character '{updated_character['name']}' updated successfully!")
        
        # Update current character name in state
        game_state.current_character_name = updated_character["name"]
        
        return True
    
    async def move_character(self) -> bool:
        """Move character to a different zone"""
        if not game_state.current_character_id:
            show_error("No character selected")
            return False
            
        if not game_state.current_world_id:
            show_error("No world selected")
            return False
        
        # Get character details
        character = await display_loading(
            "Loading character details...",
            self.character_service.get_character(game_state.current_character_id)
        )
        
        if not character:
            show_error("Failed to load character details")
            return False
        
        # Get zones in the world
        zones = await display_loading(
            "Loading zones...",
            self.zone_service.get_zones(game_state.current_world_id)
        )
        
        if not zones:
            show_error("No zones found in this world")
            return False
        
        show_title(
            f"Move Character: {character['name']}", 
            f"Current Zone: {game_state.current_zone_name if game_state.current_zone_id else 'None'}"
        )
        
        # Prompt for zone selection
        console.print("\n[bold]Choose a zone to move to:[/bold]")
        zone_id = prompt_select_item(
            zones,
            id_key="id",
            name_key="name",
            prompt_text="Select destination zone",
            extra_info_key="zone_type"
        )
        
        if not zone_id:
            show_warning("Move cancelled")
            return False
        
        # Move the character
        result = await display_loading(
            "Moving character...",
            self.zone_service.move_character_to_zone(game_state.current_character_id, zone_id)
        )
        
        if not result:
            show_error("Failed to move character")
            return False
        
        # Get zone details to update current zone
        zone = await self.zone_service.get_zone(zone_id)
        if zone:
            game_state.current_zone_id = zone["id"]
            game_state.current_zone_name = zone["name"]
            
            show_success(f"Character moved to {zone['name']} successfully!")
        else:
            show_warning("Character moved but zone details could not be loaded")
        
        return True
    
    async def delete_character(self) -> bool:
        """Delete the current character"""
        if not game_state.current_character_id:
            show_error("No character selected")
            return False
        
        character = await display_loading(
            "Loading character details...",
            self.character_service.get_character(game_state.current_character_id)
        )
        
        if not character:
            show_error("Failed to load character details")
            return False
        
        show_title(f"Delete Character: {character['name']}", "Warning: This action cannot be undone")
        
        # Confirm deletion
        if not confirm_action(
            f"Are you sure you want to permanently delete the character '{character['name']}'?", 
            default=False
        ):
            show_warning("Character deletion cancelled")
            return False
        
        # Delete the character
        result = await display_loading(
            "Deleting character...",
            self.character_service.delete_character(game_state.current_character_id)
        )
        
        if not result:
            show_error("Failed to delete character")
            return False
        
        show_success(f"Character '{character['name']}' deleted successfully!")
        
        # Character is already cleared from state by the service
        
        return True