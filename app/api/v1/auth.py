# app/api/v1/auth.py
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.api.auth import get_access_token, get_current_user
from app.database import get_db
from app.api import schemas
from app.models.user import User
from app.services.auth_service import AuthService
from app.api.dependencies import get_service

router = APIRouter()


@router.post("/register", response_model=schemas.TokenResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    request: schemas.SignUpRequest,
    auth_service: AuthService = Depends(get_service(AuthService))
):
    """
    Register a new user with Supabase Auth
    
    Returns a token response including access_token and refresh_token
    """
    try:
        user, session = auth_service.sign_up(
            email=request.email,
            password=request.password,
            first_name=request.first_name,
            last_name=request.last_name
        )
        
        return {
            "access_token": session.access_token,
            "refresh_token": session.refresh_token,
            "user_id": user.id,
            "email": user.email
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Registration failed: {str(e)}"
        )


@router.post("/login", response_model=schemas.TokenResponse)
async def login_user(
    request: schemas.SignInRequest,
    auth_service: AuthService = Depends(get_service(AuthService))
):
    """
    Sign in an existing user
    
    Returns a token response including access_token and refresh_token
    """
    try:
        response = auth_service.sign_in(
            email=request.email,
            password=request.password
        )
        
        return response
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {str(e)}"
        )


@router.post("/refresh", response_model=schemas.TokenResponse)
async def refresh_token(
    request: schemas.RefreshTokenRequest,
    auth_service: AuthService = Depends(get_service(AuthService))
):
    """
    Refresh an authentication token
    
    Returns a new token response
    """
    try:
        response = auth_service.refresh_token(request.refresh_token)
        
        return response
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token refresh failed: {str(e)}"
        )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout_user(
    auth_service: AuthService = Depends(get_service(AuthService)),
    token: str = Depends(get_access_token),
):
    """
    Sign out and invalidate the token
    
    Returns no content on success
    """
    try:
        auth_service.sign_out(token)
        return None
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Sign out failed: {str(e)}"
        )
    
@router.get("/verify-email")
async def verify_email(
    token_hash: str,
    type: str,
    next: Optional[str] = "/",
    request: Request = None,
    auth_service: AuthService = Depends(get_service(AuthService))
):
    """
    Verify email using token from email link
    
    This endpoint is called when a user clicks the verification link in their email
    It verifies the OTP token and redirects the user to the specified redirect URL
    """
    # Use the auth service to verify the token
    verification_successful = auth_service.verify_email_token(token_hash, type)
    
    # Get the frontend URL from the request or use default
    frontend_url = request.headers.get("origin", "http://localhost:3000")
    
    if verification_successful:
        # If verification succeeded, redirect to success page
        redirect_url = f"{frontend_url}{next}"
    else:
        # If verification failed, redirect to error page
        redirect_url = f"{frontend_url}/error"
    
    # Return a redirect response
    return RedirectResponse(url=redirect_url, status_code=status.HTTP_303_SEE_OTHER)


@router.post("/resend-verification", status_code=status.HTTP_200_OK)
async def resend_verification_email(
    request_data: schemas.ResendVerificationRequest,
    auth_service: AuthService = Depends(get_service(AuthService))
):
    """
    Resend a verification email to a user
    
    Returns success message on success
    """
    try:
        # Use the auth service to resend the verification email
        auth_service.resend_verification_email(
            email=request_data.email,
            redirect_url=request_data.redirect_url
        )
        
        return {
            "status": "success", 
            "message": "Verification email sent"
        }
    
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error sending verification email: {str(e)}"
        )