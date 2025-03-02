from typing import List, Optional, Dict, Any, Generic, TypeVar
from pydantic import BaseModel

T = TypeVar('T')

# Base response model with pagination info
class PaginatedResponse(BaseModel, Generic[T]):
    """Base response model for paginated results"""
    total: int
    page: int
    page_size: int
    total_pages: int
    items: List[T]