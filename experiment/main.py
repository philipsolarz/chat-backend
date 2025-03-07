"""
Simple demo script for character conversations.
"""
import asyncio
import os
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel

from models import Character
from agent import ConversationManager

# Load environment variables for API keys
load_dotenv()

# Setup console
console = Console()

# Create display function
async def display_message(name, message):
    """Display a character message with formatting"""
    # Choose color based on character name
    color = "yellow" if "Thorin" in name else "green"
    
    # Create and display panel
    panel = Panel(
        message,
        title=f"[bold {color}]{name}[/bold {color}]",
        border_style=color
    )
    console.print(panel)
    
    # Brief pause for readability
    await asyncio.sleep(0.2)

async def main():
    """Run a simple character conversation demo"""
    console.print(Panel.fit(
        "[bold magenta]Fantasy Character Chat[/bold magenta]",
        border_style="magenta"
    ))
    
    # Create characters with combined descriptions
    thorin = Character(
        name="Thorin Ironhammer",
        description="""
        A stocky dwarven blacksmith with a thick braided beard. Thorin is gruff and direct, 
        valuing hard work and craftsmanship above all else. He's suspicious of magic and speaks 
        in short, sometimes abrupt sentences. He often refers to "the old days" and his ancestors' 
        achievements. He comes from a long line of master smiths and now runs the local forge, 
        known for crafting the finest weapons in the region.
        """
    )
    
    sylvia = Character(
        name="Sylvia Nightbloom",
        description="""
        A tall, slender elven herbalist with silver-streaked dark hair. Sylvia is eloquent and 
        thoughtful, often using flowery language and botanical metaphors. She's over 300 years old 
        and has spent centuries studying plants and remedies. She runs an apothecary shop in town 
        after leaving the Elven High Council, disillusioned with court politics. She's patient but 
        can be dismissive of those who disregard knowledge or nature.
        """
    )
    
    # Create manager and conversation
    manager = ConversationManager()
    conversation = manager.create_conversation([thorin, sylvia])
    
    console.print("[bold]Starting conversation...[/bold]\n")
    
    # Run the conversation (10 turns with 3 second delay)
    try:
        await manager.run_conversation(
            conversation_id=conversation.id,
            turns=10,
            delay=10.0,
            message_callback=display_message
        )
    except KeyboardInterrupt:
        console.print("\n[bold red]Conversation interrupted![/bold red]")
    except Exception as e:
        console.print(f"\n[bold red]Error: {str(e)}[/bold red]")
    
    console.print("\n[bold]Conversation finished![/bold]")

if __name__ == "__main__":
    asyncio.run(main())