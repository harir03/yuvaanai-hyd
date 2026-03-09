"""
Intelli-Credit — Authentication Routes

POST /api/auth/login   — Authenticate user and return JWT token
POST /api/auth/seed    — Seed default admin + officer accounts (dev only)
GET  /api/auth/me      — Get current user info
"""

import logging
from datetime import datetime, timezone

import bcrypt
from fastapi import APIRouter, HTTPException, Depends, status

from backend.api.auth.jwt_handler import (
    UserCredentials,
    TokenResponse,
    TokenData,
    create_access_token,
    require_auth,
)
from backend.storage.database_models import UserDB
from config.settings import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])

# ── In-memory user store (fallback when PostgreSQL is unavailable) ──
_users_store: dict[str, dict] = {}


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def _get_user(username: str) -> dict | None:
    """Look up user from in-memory store."""
    return _users_store.get(username)


def _seed_default_users() -> int:
    """Seed default admin and officer accounts. Returns count of users created."""
    created = 0

    defaults = [
        {
            "username": "admin",
            "email": "admin@intellicredit.ai",
            "password": "admin123",
            "role": "admin",
        },
        {
            "username": "officer",
            "email": "officer@intellicredit.ai",
            "password": "officer123",
            "role": "officer",
        },
    ]

    for user_data in defaults:
        if user_data["username"] not in _users_store:
            _users_store[user_data["username"]] = {
                "username": user_data["username"],
                "email": user_data["email"],
                "password_hash": _hash_password(user_data["password"]),
                "role": user_data["role"],
                "is_active": True,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "last_login": None,
            }
            created += 1
            logger.info(f"[Auth] Seeded user: {user_data['username']} ({user_data['role']})")

    return created


# ── Auto-seed on module load ──
_seed_default_users()


@router.post("/login", response_model=TokenResponse)
async def login(credentials: UserCredentials):
    """Authenticate user and return JWT access token."""
    user = _get_user(credentials.username)

    if not user or not user["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    if not _verify_password(credentials.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    # Update last login
    user["last_login"] = datetime.now(timezone.utc).isoformat()

    # Create JWT token
    token = create_access_token(sub=user["username"], role=user["role"])
    expires_in = settings.jwt_access_token_expire_minutes * 60

    logger.info(f"[Auth] User logged in: {user['username']} ({user['role']})")

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=expires_in,
    )


@router.get("/me")
async def get_me(user: TokenData = Depends(require_auth)):
    """Get current authenticated user info."""
    stored = _get_user(user.sub)
    return {
        "username": user.sub,
        "role": user.role,
        "email": stored["email"] if stored else None,
        "is_active": stored["is_active"] if stored else True,
    }


@router.post("/seed")
async def seed_users():
    """Seed default admin + officer accounts. Development only."""
    if settings.app_env == "production":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Seed endpoint disabled in production",
        )

    created = _seed_default_users()
    return {
        "message": f"Seeded {created} new users",
        "users": [
            {"username": u["username"], "role": u["role"]}
            for u in _users_store.values()
        ],
    }
