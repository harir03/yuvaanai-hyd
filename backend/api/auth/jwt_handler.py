"""
Intelli-Credit — JWT Authentication Handler

Creates and verifies JWT access tokens for API authentication.
Uses python-jose with HS256 algorithm.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel, Field

from config.settings import settings

logger = logging.getLogger(__name__)

# ── Security scheme ──
security = HTTPBearer(auto_error=False)


# ── Models ──

class TokenData(BaseModel):
    """Decoded JWT payload."""
    sub: str = Field(..., description="User identifier (username or email)")
    role: str = Field(default="officer", description="User role")
    exp: Optional[datetime] = None


class TokenResponse(BaseModel):
    """Response when a token is issued."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(..., description="Seconds until expiration")


class UserCredentials(BaseModel):
    """Login request body."""
    username: str = Field(..., min_length=1, max_length=128)
    password: str = Field(..., min_length=1, max_length=256)


# ── Token creation ──

def create_access_token(
    sub: str,
    role: str = "officer",
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a signed JWT access token.

    Args:
        sub: Subject identifier (username or email).
        role: User role (officer, admin, viewer).
        expires_delta: Custom expiration. Defaults to settings value.

    Returns:
        Encoded JWT string.
    """
    expire = datetime.now(timezone.utc) + (
        expires_delta
        or timedelta(minutes=settings.jwt_access_token_expire_minutes)
    )
    payload = {
        "sub": sub,
        "role": role,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    token = jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    return token


# ── Token verification ──

def verify_token(token: str) -> TokenData:
    """Verify and decode a JWT token.

    Args:
        token: Raw JWT string.

    Returns:
        Decoded TokenData.

    Raises:
        HTTPException: If token is invalid or expired.
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        sub: Optional[str] = payload.get("sub")
        if sub is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing subject",
            )
        return TokenData(
            sub=sub,
            role=payload.get("role", "officer"),
            exp=datetime.fromtimestamp(payload["exp"], tz=timezone.utc) if "exp" in payload else None,
        )
    except JWTError as e:
        logger.warning("[Auth] JWT verification failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )


# ── FastAPI dependency ──

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Optional[TokenData]:
    """FastAPI dependency that extracts and verifies the current user from Bearer token.

    Returns None if no token is provided (allows unauthenticated access
    when used as optional dependency). Use require_auth for mandatory auth.
    """
    if credentials is None:
        return None
    return verify_token(credentials.credentials)


async def require_auth(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> TokenData:
    """FastAPI dependency that REQUIRES a valid JWT token.

    Raises 401 if no token or invalid token.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return verify_token(credentials.credentials)


async def require_admin(
    user: TokenData = Depends(require_auth),
) -> TokenData:
    """FastAPI dependency that requires admin role."""
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user


async def optional_auth(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Optional[TokenData]:
    """Auth dependency that enforces tokens in production but allows unauthenticated
    access in development/demo mode. Routes use this so the demo works without tokens
    while production deployments are protected.
    """
    if credentials is not None:
        return verify_token(credentials.credentials)
    # In production, require a token
    if settings.app_env == "production":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # Development/demo — allow unauthenticated access
    return None
