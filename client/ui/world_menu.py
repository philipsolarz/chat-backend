#!/usr/bin/env python
# World selection and management menu
import asyncio
from typing import Dict, Any, Optional, List, Tuple

from client.api.world_service import WorldService
from client.game.state import game_state
from client.ui.console import (
    console, clear_screen, show_title, show_error, show_success, show_warning,
    prompt_input, confirm_action, create_menu, display_loading, display_table,
    prompt_select_item, show_details
)


class WorldMenu:
    """User interface for world selection and management"""
    
    def __init__(self):
        self.world_service = WorldService()
    
    async def show_world_selection(self) -> bool:
        """Show world selection screen"""
        # First load available worlds
        worlds = await display_loading(
            "Loading worlds...",
            self.world_service.get_worlds()
        )
        
        show_title("World Selection", "Select a world to enter or create your own")
        
        if not worlds:
            show_warning("No worlds found. You can create a new world or use a starter world.")
            
            # Still provide the world menu options
            return await self.show_world_menu()
        
        # Display worlds in a table
        display_table(
            "Your Accessible Worlds",
            worlds,
            [
                ("id", "ID", "dim"),
                ("name", "Name", "green"),
                ("genre", "Genre", "blue"),
                ("description", "Description", "cyan")
            ]
        )
        
        # Show options menu
        options = [
            ("select", "Select an existing world"),
            ("create", "Create a new world"),
            ("starter", "Use a starter world"),
            ("premium", "Create premium world ($249.99)")
        ]
        
        choice = create_menu("World Options", options)
        
        if choice == "select":
            return await self.select_world(worlds)
        elif choice == "create":
            return await self.create_world()
        elif choice == "starter":
            return await self.select_starter_world()
        elif choice == "premium":
            return await self.create_premium_world()
        else:
            return False
    
    async def select_world(self, worlds: List[Dict[str, Any]]) -> bool:
        """Select a world from the list"""
        world_id = prompt_select_item(
            worlds,
            id_key="id",
            name_key="name",
            prompt_text="Select world",
            extra_info_key="genre"
        )
        
        if not world_id:
            show_warning("No world selected")
            return False
        
        # Get full world details
        world = await display_loading(
            f"Loading world details...",
            self.world_service.get_world(world_id)
        )
        
        if not world:
            show_error("Failed to load world details")
            return False
        
        # Update current world in state
        game_state.current_world_id = world["id"]
        game_state.current_world_name = world["name"]
        
        show_success(f"Selected world: {world['name']}")
        
        # Show world details
        show_details(
            f"World: {world['name']}",
            {
                "ID": world["id"],
                "Name": world["name"],
                "Genre": world.get("genre", "N/A"),
                "Description": world.get("description", "N/A"),
                "Type": "Premium" if world.get("is_premium", False) else "Starter" if world.get("is_starter", False) else "Standard",
                "Public": "Yes" if world.get("is_public", False) else "No",
                "Owner": "You" if world.get("owner_id") == game_state.current_user_id else "System" if world.get("is_starter", False) else "Other User"
            },
            highlight_fields=["Name", "Type"]
        )
        
        if confirm_action("Enter this world?", default=True):
            return True
        else:
            # Clear world selection if user decides not to enter
            game_state.clear_world()
            return False
    
    async def select_starter_world(self) -> bool:
        """Select a starter world"""
        starter_worlds = await display_loading(
            "Loading starter worlds...",
            self.world_service.get_starter_worlds()
        )
        
        if not starter_worlds:
            show_error("No starter worlds found")
            return False
        
        show_title("Starter Worlds", "Select a pre-made world to start your adventure")
        
        # Display worlds in a table
        display_table(
            "Available Starter Worlds",
            starter_worlds,
            [
                ("id", "ID", "dim"),
                ("name", "Name", "green"),
                ("genre", "Genre", "blue"),
                ("description", "Description", "cyan")
            ]
        )
        
        world_id = prompt_select_item(
            starter_worlds,
            id_key="id",
            name_key="name",
            prompt_text="Select starter world",
            extra_info_key="genre"
        )
        
        if not world_id:
            show_warning("No world selected")
            return False
        
        # Get full world details
        world = await display_loading(
            f"Loading world details...",
            self.world_service.get_world(world_id)
        )
        
        if not world:
            show_error("Failed to load world details")
            return False
        
        # Update current world in state
        game_state.current_world_id = world["id"]
        game_state.current_world_name = world["name"]
        
        show_success(f"Selected starter world: {world['name']}")
        
        if confirm_action("Enter this starter world?", default=True):
            return True
        else:
            # Clear world selection if user decides not to enter
            game_state.clear_world()
            return False
    
    async def create_world(self) -> bool:
        """Create a new world"""
        show_title("Create World", "Create your own custom world")
        
        name = prompt_input("Name", "Enter a name for your world:")
        description = prompt_input("Description", "Enter a description (optional):", default="", multiline=True)
        genre = prompt_input("Genre", "Enter the genre (e.g., Fantasy, Sci-Fi):", default="")
        is_public = confirm_action("Make this world public?", default=False)
        
        # Create the world
        world = await display_loading(
            "Creating world...",
            self.world_service.create_world(name, description, genre, is_public)
        )
        
        if not world:
            show_error("Failed to create world")
            return False
        
        show_success(f"World '{name}' created successfully!")
        
        # World is already set in state by the service
        
        if confirm_action("Enter your new world?", default=True):
            return True
        else:
            # Clear world selection if user decides not to enter
            game_state.clear_world()
            return False
    
    async def create_premium_world(self) -> bool:
        """Start premium world purchase process"""
        show_title("Premium World", "Create a premium world ($249.99)")
        
        # Confirm purchase intent
        if not confirm_action(
            "Premium worlds cost $249.99. Would you like to proceed with purchase?", 
            default=False
        ):
            show_warning("Premium world purchase cancelled")
            return False
        
        name = prompt_input("Name", "Enter a name for your premium world:")
        description = prompt_input("Description", "Enter a description (optional):", default="", multiline=True)
        genre = prompt_input("Genre", "Enter the genre (e.g., Fantasy, Sci-Fi):", default="")
        
        # Start checkout process
        result = await display_loading(
            "Initiating premium world purchase...",
            self.world_service.purchase_premium_world(name, description, genre)
        )
        
        if not result or "checkout_url" not in result:
            show_error("Failed to initiate premium world purchase")
            return False
        
        # Show checkout URL
        show_success("Premium world purchase initiated!")
        console.print(f"\nPlease complete your purchase at:")
        console.print(f"[blue underline]{result['checkout_url']}[/blue underline]")
        console.print("\nAfter payment, your premium world will be created automatically.")
        
        if confirm_action("Return to world menu?", default=True):
            return False
        else:
            return False
    
    async def show_world_menu(self) -> Optional[str]:
        """Show world management menu"""
        if game_state.current_world_id:
            subtitle = f"Current World: {game_state.current_world_name}"
            
            options = [
                ("enter", "Enter current world"),
                ("change", "Change world"),
                ("detail", "View world details"),
                ("edit", "Edit world settings"),
                ("delete", "Delete world"),
                ("back", "Back to main menu")
            ]
        else:
            subtitle = "No world selected"
            
            options = [
                ("select", "Select world"),
                ("create", "Create new world"),
                ("starter", "Use starter world"),
                ("premium", "Create premium world ($249.99)"),
                ("back", "Back to main menu")
            ]
        
        choice = create_menu("World Management", options, subtitle)
        
        if not game_state.current_world_id:
            # Handle options when no world is selected
            if choice == "select":
                await self.show_world_selection()
                return "refresh"
            elif choice == "create":
                result = await self.create_world()
                return "enter" if result else "refresh"
            elif choice == "starter":
                result = await self.select_starter_world()
                return "enter" if result else "refresh"
            elif choice == "premium":
                await self.create_premium_world()
                return "refresh"
        else:
            # Handle options when a world is selected
            if choice == "enter":
                return "enter"
            elif choice == "change":
                await self.show_world_selection()
                return "refresh"
            elif choice == "detail":
                await self.show_world_details()
                return "refresh"
            elif choice == "edit":
                await self.edit_world()
                return "refresh"
            elif choice == "delete":
                result = await self.delete_world()
                return "refresh"
        
        return choice
    
    async def show_world_details(self) -> None:
        """Show detailed information about the current world"""
        if not game_state.current_world_id:
            show_error("No world selected")
            return
        
        world = await display_loading(
            "Loading world details...",
            self.world_service.get_world(game_state.current_world_id)
        )
        
        if not world:
            show_error("Failed to load world details")
            return
        
        show_title(f"World: {world['name']}", "World Details")
        
        # Show details
        show_details(
            f"World Information",
            {
                "ID": world["id"],
                "Name": world["name"],
                "Genre": world.get("genre", "N/A"),
                "Description": world.get("description", "N/A"),
                "Type": "Premium" if world.get("is_premium", False) else "Starter" if world.get("is_starter", False) else "Standard",
                "Public": "Yes" if world.get("is_public", False) else "No",
                "Owner": "You" if world.get("owner_id") == game_state.current_user_id else "System" if world.get("is_starter", False) else "Other User"
            },
            highlight_fields=["Name", "Type"]
        )
        
        # Wait for user to press enter
        input("\nPress Enter to continue...")
    
    async def edit_world(self) -> bool:
        """Edit world settings"""
        if not game_state.current_world_id:
            show_error("No world selected")
            return False
        
        world = await display_loading(
            "Loading world details...",
            self.world_service.get_world(game_state.current_world_id)
        )
        
        if not world:
            show_error("Failed to load world details")
            return False
        
        # Check if user is the owner
        if world.get("owner_id") != game_state.current_user_id:
            show_error("You can only edit worlds you own")
            return False
        
        # Check if it's a starter world
        if world.get("is_starter", False):
            show_error("Starter worlds cannot be edited")
            return False
        
        show_title(f"Edit World: {world['name']}", "Change world settings")
        
        name = prompt_input("Name", "Enter new name (leave blank to keep current):", default=world["name"])
        description = prompt_input("Description", "Enter new description (leave blank to keep current):", default=world.get("description", ""), multiline=True)
        genre = prompt_input("Genre", "Enter new genre (leave blank to keep current):", default=world.get("genre", ""))
        is_public = confirm_action("Make this world public?", default=world.get("is_public", False))
        
        # Prepare update data
        update_data = {}
        if name != world["name"]:
            update_data["name"] = name
        if description != world.get("description"):
            update_data["description"] = description
        if genre != world.get("genre"):
            update_data["genre"] = genre
        if is_public != world.get("is_public"):
            update_data["is_public"] = is_public
        
        if not update_data:
            show_warning("No changes made")
            return False
        
        # Update the world
        updated_world = await display_loading(
            "Updating world...",
            self.world_service.update_world(game_state.current_world_id, update_data)
        )
        
        if not updated_world:
            show_error("Failed to update world")
            return False
        
        show_success(f"World '{updated_world['name']}' updated successfully!")
        
        # Update current world name in state
        game_state.current_world_name = updated_world["name"]
        
        return True
    
    async def delete_world(self) -> bool:
        """Delete the current world"""
        if not game_state.current_world_id:
            show_error("No world selected")
            return False
        
        world = await display_loading(
            "Loading world details...",
            self.world_service.get_world(game_state.current_world_id)
        )
        
        if not world:
            show_error("Failed to load world details")
            return False
        
        # Check if user is the owner
        if world.get("owner_id") != game_state.current_user_id:
            show_error("You can only delete worlds you own")
            return False
        
        # Check if it's a starter world
        if world.get("is_starter", False):
            show_error("Starter worlds cannot be deleted")
            return False
        
        show_title(f"Delete World: {world['name']}", "Warning: This action cannot be undone")
        
        # Confirm deletion
        if not confirm_action(
            f"Are you sure you want to permanently delete the world '{world['name']}'?", 
            default=False
        ):
            show_warning("World deletion cancelled")
            return False
        
        # Double-check for premium worlds
        if world.get("is_premium", False):
            if not confirm_action(
                "This is a premium world. Deleting it will not refund your purchase. Continue?",
                default=False
            ):
                show_warning("World deletion cancelled")
                return False
        
        # Delete the world
        result = await display_loading(
            "Deleting world...",
            self.world_service.delete_world(game_state.current_world_id)
        )
        
        if not result:
            show_error("Failed to delete world")
            return False
        
        show_success(f"World '{world['name']}' deleted successfully!")
        
        # World is already cleared from state by the service
        
        return True