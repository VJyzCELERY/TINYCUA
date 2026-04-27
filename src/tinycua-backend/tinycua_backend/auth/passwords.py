"""Password hashing utilities for tinycua-backend."""

from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)


def hash_password(password: str) -> str:
    """Hash a password using bcrypt.

    Args:
        password: The raw password

    Returns:
        The bcrypt hashed password
    """
    return str(pwd_context.hash(password))


def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against a bcrypt hash.

    Args:
        password: The raw password
        hashed: The bcrypt hash

    Returns:
        True if password matches
    """
    return bool(pwd_context.verify(password, hashed))
