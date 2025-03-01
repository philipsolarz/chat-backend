#!/usr/bin/env python
# Console UI utilities
from datetime import datetime
import os
import asyncio
from typing import Dict, List, Any, Optional, Callable, Awaitable, Tuple
from rich.console import Console
from rich.prompt import Prompt, Confirm, IntPrompt
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich.syntax import Syntax
from rich.progress import Progress
from rich.markdown import Markdown
from rich.layout import Layout
from rich.live import Live
from rich import box

# Initialize Rich console
console = Console()


def clear_screen():
    """Clear the terminal screen"""
    os.system('cls' if os.name == 'nt' else 'clear')


def show_title(title: str, subtitle: Optional[str] = None, style="bold cyan"):
    """Display a centered title"""
    clear_screen()
    
    # Create title panel
    title_text = Text(title, style=style)
    title_panel = Panel(title_text, expand=False)
    
    console.print(title_panel)
    
    if subtitle:
        console.print(f"\n{subtitle}\n")


def create_menu(title: str, options: List[Tuple[str, str]], subtitle: Optional[str] = None):
    """Display a numbered menu and return the selected option"""
    show_title(title, subtitle)
    
    for i, (key, description) in enumerate(options, 1):
        console.print(f"[cyan]{i}.[/cyan] {description}")
    
    # Add exit option
    console.print(f"[red]0.[/red] Exit")
    
    # Get user choice
    while True:
        try:
            choice = IntPrompt.ask("Enter your choice", default=0)
            
            if choice == 0:
                return None
            elif 1 <= choice <= len(options):
                return options[choice-1][0]
            else:
                console.print("[yellow]Invalid choice. Please try again.[/yellow]")
        except ValueError:
            console.print("[yellow]Please enter a number.[/yellow]")


def display_table(title: str, data: List[Dict[str, Any]], columns: List[Tuple[str, str, str]]):
    """
    Display data in a table format
    
    Args:
        title: Table title
        data: List of dictionaries containing the data
        columns: List of (key, header, style) tuples
    """
    table = Table(title=title)
    
    # Add columns
    for key, header, style in columns:
        table.add_column(header, style=style)
    
    # Add rows
    for item in data:
        row = []
        for key, _, _ in columns:
            # Handle nested values using dot notation
            if "." in key:
                parts = key.split(".")
                value = item
                for part in parts:
                    if isinstance(value, dict) and part in value:
                        value = value[part]
                    else:
                        value = ""
                        break
            else:
                value = item.get(key, "")
                
            # Convert to string and truncate if necessary
            value_str = str(value)
            if len(value_str) > 50:
                value_str = value_str[:47] + "..."
                
            row.append(value_str)
            
        table.add_row(*row)
    
    console.print(table)


async def display_loading(message: str, coro: Awaitable):
    """Display a loading spinner while awaiting a coroutine"""
    with console.status(f"[bold green]{message}[/bold green]"):
        result = await coro
    return result


def show_error(message: str):
    """Display an error message"""
    console.print(f"[bold red]Error:[/bold red] {message}")


def show_success(message: str):
    """Display a success message"""
    console.print(f"[bold green]Success:[/bold green] {message}")


def show_warning(message: str):
    """Display a warning message"""
    console.print(f"[bold yellow]Warning:[/bold yellow] {message}")


def show_info(message: str):
    """Display an info message"""
    console.print(f"[bold blue]Info:[/bold blue] {message}")


def show_details(title: str, details: Dict[str, Any], highlight_fields: List[str] = None):
    """
    Display a dictionary of details in a panel
    
    Args:
        title: Panel title
        details: Dictionary of key-value pairs
        highlight_fields: List of field keys to highlight
    """
    highlight_fields = highlight_fields or []
    formatted_details = []
    
    for key, value in details.items():
        if key in highlight_fields:
            style = "bold cyan"
        else:
            style = "cyan"
            
        value_str = str(value)
        if isinstance(value, bool):
            value_str = f"[{'green' if value else 'red'}]{value}[/{'green' if value else 'red'}]"
            
        formatted_details.append(f"[{style}]{key}:[/{style}] {value_str}")
    
    console.print(Panel("\n".join(formatted_details), title=title, border_style="green"))


def prompt_input(field_name: str, description: str, default: str = "", password: bool = False, 
                 choices: List[str] = None, multiline: bool = False) -> str:
    """Prompt for user input with consistent formatting"""
    console.print(f"[bold]{description}[/bold]")
    
    if multiline:
        console.print("Enter text (press Enter twice to finish):")
        lines = []
        while True:
            line = input()
            if not line and (not lines or not lines[-1]):
                break
            lines.append(line)
        return "\n".join(lines)
    
    if choices:
        return Prompt.ask(field_name, choices=choices, default=default)
    
    return Prompt.ask(field_name, password=password, default=default)


def confirm_action(prompt: str, default: bool = False) -> bool:
    """Ask for confirmation before performing an action"""
    return Confirm.ask(prompt, default=default)


def prompt_select_item(items: List[Dict[str, Any]], id_key: str, name_key: str, 
                      prompt_text: str, allow_none: bool = True, 
                      extra_info_key: Optional[str] = None) -> Optional[str]:
    """
    Display a list of items and prompt user to select one
    
    Args:
        items: List of item dictionaries
        id_key: Dictionary key for the id field
        name_key: Dictionary key for the display name
        prompt_text: Text to display for the prompt
        allow_none: Whether to allow selecting none
        extra_info_key: Optional key for additional display info
        
    Returns:
        Selected item ID or None if cancelled
    """
    if not items:
        console.print("[yellow]No items available.[/yellow]")
        return None
    
    console.print("[bold]Available Options:[/bold]")
    for i, item in enumerate(items, 1):
        display = f"[cyan]{i}.[/cyan] {item.get(name_key, 'Unknown')}"
        if extra_info_key and extra_info_key in item:
            display += f" ({item[extra_info_key]})"
        console.print(display)
    
    if allow_none:
        console.print("[yellow]0. None/Cancel[/yellow]")
    
    while True:
        try:
            choice = IntPrompt.ask(prompt_text, default=0)
            
            if choice == 0 and allow_none:
                return None
            elif 1 <= choice <= len(items):
                return items[choice-1].get(id_key)
            else:
                console.print("[yellow]Invalid choice. Please try again.[/yellow]")
        except ValueError:
            console.print("[yellow]Please enter a number.[/yellow]")


class ChatUI:
    """UI component for chat interface with message history"""
    
    def __init__(self, title: str, subtitle: Optional[str] = None):
        self.title = title
        self.subtitle = subtitle
        self.messages = []
        self.max_display_messages = 20
    
    def clear_messages(self):
        """Clear the message history"""
        self.messages = []
    
    def add_message(self, sender: str, content: str, is_self: bool = False, is_system: bool = False):
        """Add a message to the history"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.messages.append({
            "sender": sender,
            "content": content,
            "timestamp": timestamp,
            "is_self": is_self,
            "is_system": is_system
        })
    
    def display(self):
        """Display the chat interface"""
        clear_screen()
        
        # Create title
        title_text = Text(self.title, style="bold cyan")
        console.print(Panel(title_text, expand=False))
        
        if self.subtitle:
            console.print(self.subtitle)
        
        console.print()
        
        # Show most recent messages
        display_messages = self.messages[-self.max_display_messages:] if self.messages else []
        
        if not display_messages:
            console.print("[dim]No messages yet. Start typing to chat.[/dim]\n")
        else:
            # Display messages
            for msg in display_messages:
                if msg["is_system"]:
                    console.print(f"[yellow]{msg['content']}[/yellow]")
                else:
                    if msg["is_self"]:
                        name_style = "blue italic"
                    else:
                        name_style = "green"
                        
                    console.print(
                        f"[{name_style}]{msg['sender']}[/{name_style}] "
                        f"[dim]({msg['timestamp']})[/dim]: {msg['content']}"
                    )
            
            console.print()
        
        # Draw input prompt
        console.print("[bold]Enter your message:[/bold] (type '/exit' to leave)")
    
    async def live_update(self, message_queue: asyncio.Queue):
        """Start a live-updating chat display"""
        live = Live(auto_refresh=False)
        live.start()
        
        try:
            while True:
                # Update the display
                layout = Layout()
                
                # Header
                layout.split(
                    Layout(name="header"),
                    Layout(name="body"),
                    Layout(name="input")
                )
                
                header_panel = Panel(
                    Text(self.title, style="bold cyan"),
                    box=box.ROUNDED,
                    border_style="cyan"
                )
                layout["header"].update(header_panel)
                
                # Message body
                display_messages = self.messages[-self.max_display_messages:] if self.messages else []
                messages_text = Text()
                
                if not display_messages:
                    messages_text.append("No messages yet. Start typing to chat.\n", style="dim")
                else:
                    for msg in display_messages:
                        if msg["is_system"]:
                            messages_text.append(f"{msg['content']}\n", style="yellow")
                        else:
                            if msg["is_self"]:
                                name_style = "blue italic"
                            else:
                                name_style = "green"
                                
                            messages_text.append(f"{msg['sender']}", style=name_style)
                            messages_text.append(f" ({msg['timestamp']}): ", style="dim")
                            messages_text.append(f"{msg['content']}\n")
                
                body_panel = Panel(
                    messages_text,
                    title="Messages",
                    box=box.ROUNDED,
                    border_style="blue",
                    padding=(0, 1)
                )
                layout["body"].update(body_panel)
                
                # Input prompt
                input_text = Text("Enter your message: (type '/exit' to leave)")
                input_panel = Panel(
                    input_text,
                    box=box.ROUNDED,
                    border_style="green"
                )
                layout["input"].update(input_panel)
                
                # Update the live display
                live.update(layout)
                live.refresh()
                
                # Wait for the next message
                try:
                    message = await asyncio.wait_for(message_queue.get(), timeout=0.1)
                    if message.get("type") == "exit":
                        break
                    
                    sender = message.get("sender", "Unknown")
                    content = message.get("content", "")
                    is_self = message.get("is_self", False)
                    is_system = message.get("is_system", False)
                    
                    self.add_message(sender, content, is_self, is_system)
                except asyncio.TimeoutError:
                    # Just refresh the display
                    pass
                
        finally:
            live.stop()