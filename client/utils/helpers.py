#!/usr/bin/env python
# Helper utility functions
import re
import json
import os
import asyncio
from datetime import datetime, date
from typing import Dict, Any, List, Optional, Union, Tuple


def format_date(date_obj: Union[datetime, date, str, None]) -> str:
    """Format a date or datetime object as a readable string"""
    if date_obj is None:
        return "N/A"
        
    if isinstance(date_obj, str):
        try:
            # Try to parse ISO format
            date_obj = datetime.fromisoformat(date_obj.replace('Z', '+00:00'))
        except ValueError:
            return date_obj
    
    if isinstance(date_obj, datetime):
        return date_obj.strftime("%Y-%m-%d %H:%M:%S")
    elif isinstance(date_obj, date):
        return date_obj.strftime("%Y-%m-%d")
    
    return str(date_obj)


def format_datetime_relative(dt: Union[datetime, str, None]) -> str:
    """Format a datetime as a relative time (e.g., '2 hours ago')"""
    if dt is None:
        return "N/A"
        
    if isinstance(dt, str):
        try:
            # Try to parse ISO format
            dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))
        except ValueError:
            return dt
    
    if not isinstance(dt, datetime):
        return str(dt)
    
    now = datetime.now()
    diff = now - dt
    
    seconds = diff.total_seconds()
    
    if seconds < 60:
        return "just now"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    elif seconds < 86400:
        hours = int(seconds // 3600)
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    elif seconds < 604800:
        days = int(seconds // 86400)
        return f"{days} day{'s' if days != 1 else ''} ago"
    elif seconds < 2592000:
        weeks = int(seconds // 604800)
        return f"{weeks} week{'s' if weeks != 1 else ''} ago"
    else:
        return format_date(dt)


def truncate_text(text: str, max_length: int = 50, ellipsis: str = "...") -> str:
    """Truncate text to a maximum length and add ellipsis if needed"""
    if not text:
        return ""
        
    if len(text) <= max_length:
        return text
        
    return text[:max_length - len(ellipsis)] + ellipsis


def validate_email(email: str) -> bool:
    """Validate email format"""
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(email_pattern, email))


def validate_password(password: str, min_length: int = 8) -> Tuple[bool, str]:
    """
    Validate password strength
    
    Returns:
        Tuple of (is_valid, message)
    """
    if len(password) < min_length:
        return False, f"Password must be at least {min_length} characters long"
        
    # Check for at least one letter and one number
    if not re.search(r'[A-Za-z]', password) or not re.search(r'\d', password):
        return False, "Password must contain both letters and numbers"
        
    return True, "Password is valid"


def safe_get(obj: Dict[str, Any], path: str, default: Any = None) -> Any:
    """
    Safely get a nested value from a dictionary using dot notation
    
    Example:
        safe_get(data, "user.profile.name", "Unknown")
    """
    keys = path.split('.')
    result = obj
    
    for key in keys:
        if isinstance(result, dict) and key in result:
            result = result[key]
        else:
            return default
            
    return result


def write_json_file(data: Any, file_path: str) -> bool:
    """Write data to a JSON file"""
    try:
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        print(f"Error writing JSON file: {str(e)}")
        return False


def read_json_file(file_path: str, default: Any = None) -> Any:
    """Read data from a JSON file"""
    try:
        if not os.path.exists(file_path):
            return default
            
        with open(file_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error reading JSON file: {str(e)}")
        return default


def generate_random_id(length: int = 8) -> str:
    """Generate a random ID string"""
    import random
    import string
    
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))


def parse_bool(value: Union[str, bool, int, None]) -> bool:
    """Parse a string, int, or None value into a boolean"""
    if isinstance(value, bool):
        return value
    
    if value is None:
        return False
        
    if isinstance(value, int):
        return value != 0
        
    if isinstance(value, str):
        return value.lower() in ('yes', 'true', 't', 'y', '1')
        
    return bool(value)


def run_async(coro):
    """Run an async function in a synchronous context"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        # If there's no event loop in the current thread, create one
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(coro)


def format_currency(amount: Union[int, float, None], currency: str = "USD") -> str:
    """Format a currency amount"""
    if amount is None:
        return "N/A"
    
    # Handle amounts in cents (e.g. from Stripe)
    if isinstance(amount, int) and amount > 0 and currency.upper() in ["USD", "EUR", "GBP"]:
        amount = amount / 100
    
    if currency.upper() == "USD":
        return f"${amount:.2f}"
    elif currency.upper() == "EUR":
        return f"€{amount:.2f}"
    elif currency.upper() == "GBP":
        return f"£{amount:.2f}"
    else:
        return f"{amount:.2f} {currency.upper()}"


def pluralize(count: int, singular: str, plural: Optional[str] = None) -> str:
    """Return singular or plural form based on count"""
    if count == 1:
        return f"{count} {singular}"
    else:
        if plural is None:
            # Simple English pluralization
            if singular.endswith('y') and not singular.endswith(('ay', 'ey', 'iy', 'oy', 'uy')):
                plural = singular[:-1] + 'ies'
            elif singular.endswith(('s', 'x', 'z', 'ch', 'sh')):
                plural = singular + 'es'
            else:
                plural = singular + 's'
        
        return f"{count} {plural}"