"""API key utilities for tinycua-backend."""

from __future__ import annotations

import secrets

from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)

MIN_API_KEY_LENGTH = 32
MAX_API_KEYS_PER_REQUEST = 5


def hash_api_key(key: str) -> str:
    """Hash an API key using bcrypt.

    Args:
        key: The raw API key

    Returns:
        The bcrypt hashed key
    """
    return str(pwd_context.hash(key))


def verify_api_key(key: str, hashed: str) -> bool:
    """Verify an API key against a bcrypt hash.

    Args:
        key: The raw API key
        hashed: The bcrypt hash

    Returns:
        True if key matches
    """
    return bool(pwd_context.verify(key, hashed))


def create_api_key() -> str:
    """Create a new random API key.

    Returns:
        A new API key
    """
    return f"tcu_{secrets.token_urlsafe(32)}"
