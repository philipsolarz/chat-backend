# Simple UI utilities for RPG Client
import os
import sys
from typing import List, Dict, Any, Optional, Callable, TypeVar
from getpass import getpass
from datetime import datetime

T = TypeVar('T')

# ANSI color codes
RESET = "\033[0m"
BOLD = "\033[1m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
GRAY = "\033[90m"

def clear_screen() -> None:
    """Clear the terminal screen"""
    os.system('cls' if os.name == 'nt' else 'clear')

def show_title(title: str, subtitle: Optional[str] = None) -> None:
    """Display a title banner"""
    clear_screen()
    print(f"\n{BOLD}{CYAN}{'=' * 50}{RESET}")
    print(f"{BOLD}{CYAN}  {title}{RESET}")
    print(f"{BOLD}{CYAN}{'=' * 50}{RESET}")
    
    if subtitle:
        print(f"\n{subtitle}\n")

def show_menu(title: str, options: List[str], subtitle: Optional[str] = None) -> Optional[str]:
    """Display a menu and return the selected option index"""
    show_title(title, subtitle)
    
    for i, option in enumerate(options, 1):
        print(f"{CYAN}{i}.{RESET} {option}")
    
    print(f"\n{RED}0.{RESET} Exit")
    
    while True:
        try:
            choice = input("\nEnter your choice: ")
            
            if choice == "0":
                return None
                
            choice_num = int(choice)
            if 1 <= choice_num <= len(options):
                return str(choice_num)
            else:
                print(f"{YELLOW}Invalid choice. Please try again.{RESET}")
        except ValueError:
            print(f"{YELLOW}Please enter a number.{RESET}")

def select_item(items: List[T], display_fn: Callable[[T], str], title: str = "Select an item", subtitle: Optional[str] = None) -> Optional[T]:
    """Display a list of items and let user select one"""
    show_title(title, subtitle)
    
    if not items:
        print(f"{YELLOW}No items available.{RESET}")
        input("Press Enter to continue...")
        return None
    
    for i, item in enumerate(items, 1):
        print(f"{CYAN}{i}.{RESET} {display_fn(item)}")
    
    print(f"\n{RED}0.{RESET} Cancel")
    
    while True:
        try:
            choice = input("\nEnter your choice: ")
            
            if choice == "0":
                return None
                
            choice_num = int(choice)
            if 1 <= choice_num <= len(items):
                return items[choice_num - 1]
            else:
                print(f"{YELLOW}Invalid choice. Please try again.{RESET}")
        except ValueError:
            print(f"{YELLOW}Please enter a number.{RESET}")

def prompt(message: str, default: Optional[str] = None, password: bool = False, required: bool = True) -> str:
    """Prompt for user input"""
    while True:
        if default:
            prompt_text = f"{message} [{default}]: "
        else:
            prompt_text = f"{message}: "
        
        if password:
            value = getpass(prompt_text)
        else:
            value = input(prompt_text)
        
        # Use default if no input and default provided
        if not value and default:
            return default
            
        # Check if input is required
        if not value and required:
            print(f"{YELLOW}This field is required. Please try again.{RESET}")
            continue
            
        return value

def confirm(message: str, default: bool = False) -> bool:
    """Ask for confirmation"""
    default_text = "Y/n" if default else "y/N"
    response = input(f"{message} [{default_text}]: ")
    
    if not response:
        return default
        
    return response.lower() in ['y', 'yes']

def show_error(message: str) -> None:
    """Display an error message"""
    print(f"{RED}Error: {message}{RESET}")

def show_warning(message: str) -> None:
    """Display a warning message"""
    print(f"{YELLOW}{message}{RESET}")

def show_success(message: str) -> None:
    """Display a success message"""
    print(f"{GREEN}{message}{RESET}")

def show_info(message: str) -> None:
    """Display an info message"""
    print(f"{BLUE}{message}{RESET}")

def show_system_message(message: str) -> None:
    """Display a system message in chat"""
    print(f"{MAGENTA}System: {message}{RESET}")

def show_chat_message(sender: str, content: str, is_self: bool = False) -> None:
    """Display a chat message"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    
    if is_self:
        print(f"{CYAN}[{timestamp}] {sender}{RESET}: {content}")
    else:
        print(f"{GREEN}[{timestamp}] {sender}{RESET}: {content}")

def show_emote(emote_text: str) -> None:
    """Display an emote in chat"""
    print(f"{YELLOW}* {emote_text} *{RESET}")

def get_input() -> str:
    """Get user input for chat"""
    return input(f"{GRAY}> {RESET}")