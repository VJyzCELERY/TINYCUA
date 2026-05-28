"""Authentication middleware for runner."""

import logging

from fastapi import HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from tinycua_runner.config import get_config

logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)


async def validate_runner_token(
    credentials: HTTPAuthorizationCredentials | None = None,
) -> bool:
    """Validate that the request comes from trusted backend.

    Args:
        credentials: HTTP authorization credentials

    Returns:
        True if valid

    Raises:
        HTTPException: If token is invalid
    """
    config = get_config()
    logger.info(f"Validating token, config token: {config.runner_token}")

    if credentials is None:
        logger.warning("No credentials provided")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
        )

    scheme = credentials.scheme.lower()
    if scheme != "bearer":
        logger.warning(f"Invalid scheme: {scheme}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication scheme",
        )

    token = credentials.credentials
    logger.info(f"Received token: {token}")
    if token != config.runner_token:
        logger.warning(f"Token mismatch: {token} != {config.runner_token}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid runner token",
        )

    return True
