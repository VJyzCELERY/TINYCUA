"""Authentication module for tinycua-backend."""

import asyncio
import hmac
import logging
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

from fastapi import Depends, Header, HTTPException, status
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from tinycua_backend.config import get_config
from tinycua_backend.storage.database import get_db
from tinycua_backend.auth.models import APIKey
from tinycua_backend.tenant.models import Tenant, TenantType

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
logger = logging.getLogger(__name__)

MIN_API_KEY_LENGTH = 32
MAX_API_KEYS_PER_REQUEST = 5


def _get_jwt_secret() -> str:
    """Get the JWT secret from config or environment.

    Returns:
        The JWT secret string

    Raises:
        RuntimeError: If no JWT secret is configured
    """
    config = get_config()
    secret = config.auth.jwt_secret or os.environ.get("JWT_SECRET", "")
    if not secret:
        raise RuntimeError(
            "JWT secret not configured. Set JWT_SECRET environment variable "
            "or auth.jwt_secret in config."
        )
    return secret


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


def create_jwt_token(
    user_id: str,
    tenant_id: str,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a JWT token.

    Args:
        user_id: The user's ID
        tenant_id: The tenant's ID
        expires_delta: Optional expiration time

    Returns:
        JWT token string
    """
    config = get_config()
    jwt_secret = _get_jwt_secret()
    if expires_delta is None:
        expires_delta = timedelta(hours=config.auth.jwt_expiration_hours)

    expire = datetime.now(timezone.utc) + expires_delta
    payload = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "jti": str(uuid.uuid4()),
    }
    return str(
        jwt.encode(
            payload,
            jwt_secret,
            algorithm=config.auth.jwt_algorithm,
        )
    )


def decode_jwt_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT token.

    Args:
        token: The JWT token string

    Returns:
        The payload dict

    Raises:
        HTTPException: If the token is invalid
    """
    config = get_config()
    jwt_secret = _get_jwt_secret()
    try:
        payload = jwt.decode(
            token,
            jwt_secret,
            algorithms=[config.auth.jwt_algorithm],
        )
        return dict(payload)
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid JWT token",
        ) from e


class CurrentTenant:
    """Represents the current authenticated tenant."""

    def __init__(self, tenant: Tenant, user_id: str | None = None):
        """Initialize the current tenant.

        Args:
            tenant: The tenant instance
            user_id: Optional user ID
        """
        self.tenant = tenant
        self.user_id = user_id

    @property
    def is_system(self) -> bool:
        """Check if this is a system tenant (global API key)."""
        return self.tenant.tenant_type == TenantType.SYSTEM


def get_tenant_filter(tenant: Tenant, model: Any) -> Any:
    """Get filter condition for tenant-specific queries.

    For system tenant, returns no filter (access all).
    For other tenants, returns filter by tenant_id.

    Args:
        tenant: The tenant instance
        model: The SQLAlchemy model to filter

    Returns:
        Filter condition or None for system tenant
    """
    if tenant.tenant_type == TenantType.SYSTEM:
        return None
    return model.tenant_id == tenant.id


def get_or_create_guest_tenant(db: Session) -> Tenant:
    """Get or create the guest tenant.

    Args:
        db: Database session

    Returns:
        The guest tenant
    """
    guest_tenant = (
        db.query(Tenant).filter(Tenant.tenant_type == TenantType.GUEST).first()
    )

    if guest_tenant:
        return guest_tenant

    guest_tenant = Tenant(
        name="Guest",
        tenant_type=TenantType.GUEST,
    )
    db.add(guest_tenant)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        guest_tenant = (
            db.query(Tenant).filter(Tenant.tenant_type == TenantType.GUEST).first()
        )
        if guest_tenant:
            return guest_tenant
        raise
    db.refresh(guest_tenant)

    return guest_tenant


def get_or_create_system_tenant(db: Session) -> Tenant:
    """Get or create the system tenant (for global API key).

    The system tenant owns all resources and bypasses tenant restrictions.

    Args:
        db: Database session

    Returns:
        The system tenant
    """
    system_tenant = (
        db.query(Tenant).filter(Tenant.tenant_type == TenantType.SYSTEM).first()
    )

    if system_tenant:
        return system_tenant

    system_tenant = Tenant(
        name="System",
        tenant_type=TenantType.SYSTEM,
    )
    db.add(system_tenant)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        system_tenant = (
            db.query(Tenant).filter(Tenant.tenant_type == TenantType.SYSTEM).first()
        )
        if system_tenant:
            return system_tenant
        raise
    db.refresh(system_tenant)

    return system_tenant


async def get_current_tenant(
    authorization: Annotated[str | None, Header()] = None,
    db: Session = Depends(get_db),
) -> CurrentTenant:
    """Get the current tenant from the authorization header.

    Tries in order:
    1. Global API key (bypasses tenant - system access)
    2. JWT token (tenant-specific)
    3. Tenant API key (tenant-specific)

    Args:
        authorization: The Authorization header
        db: Database session

    Returns:
        CurrentTenant instance

    Raises:
        HTTPException: If authentication fails
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
        )

    try:
        scheme, token = authorization.split(" ", 1)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format",
        )

    # Check for global API key first (system-wide access)
    config = get_config()
    if config.auth.api_key and hmac.compare_digest(token, config.auth.api_key):
        # Create or get system tenant for global API key
        system_tenant = await asyncio.to_thread(get_or_create_system_tenant, db)
        return CurrentTenant(tenant=system_tenant, user_id="system")

    # Try JWT token
    if scheme.lower() == "bearer":
        try:
            payload = decode_jwt_token(token)
            tenant_id = payload.get("tenant_id")
            user_id = payload.get("sub")

            tenant_uuid = uuid.UUID(tenant_id)
            tenant = await asyncio.to_thread(
                lambda: db.query(Tenant).filter(Tenant.id == tenant_uuid).first()
            )
            if not tenant:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid tenant",
                )

            return CurrentTenant(tenant=tenant, user_id=user_id)
        except HTTPException:
            raise
        except (JWTError, ValueError, KeyError):
            pass  # Expected validation failures - fall through to API key
        except Exception as e:
            logger.warning("Unexpected error during JWT validation: %s", e)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            )

    # Try tenant API key
    if len(token) < MIN_API_KEY_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    key_prefix = token[:8]
    api_keys = await asyncio.to_thread(
        lambda: db.query(APIKey)
        .filter(APIKey.is_active.is_(True), APIKey.key_prefix == key_prefix)
        .limit(MAX_API_KEYS_PER_REQUEST)
        .all()
    )

    matched_key = None
    for api_key in api_keys:
        if verify_api_key(token, api_key.key_hash):
            matched_key = api_key
            break

    if not matched_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    now = datetime.now(timezone.utc)
    if matched_key.expires_at and matched_key.expires_at < now:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key has expired",
        )

    # Update last used
    matched_key.last_used_at = now
    await asyncio.to_thread(db.commit)

    tenant = await asyncio.to_thread(
        lambda: db.query(Tenant).filter(Tenant.id == matched_key.tenant_id).first()
    )
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    return CurrentTenant(tenant=tenant)
