from typing import Optional
from pydantic import BaseModel, EmailStr, Field

class SignUpRequest(BaseModel):
    """Request for user registration"""
    email: EmailStr
    password: str = Field(..., min_length=8)
    first_name: Optional[str] = None
    last_name: Optional[str] = None

class SignInRequest(BaseModel):
    """Request for user login"""
    email: EmailStr
    password: str

class RefreshTokenRequest(BaseModel):
    """Request to refresh an authentication token"""
    refresh_token: str

class TokenResponse(BaseModel):
    """Response with authentication tokens"""
    access_token: str
    refresh_token: str
    user_id: str
    email: str

class ResendVerificationRequest(BaseModel):
    """Request to resend verification email"""
    email: EmailStr
    redirect_url: Optional[str] = None
