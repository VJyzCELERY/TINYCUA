"""Authentication module for tinycua-backend."""

import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from tinycua_backend.config import get_config
from tinycua_backend.database import get_db
from tinycua_backend.models.api_key import APIKey
from tinycua_backend.models.tenant import Tenant, TenantType


def hash_api_key(key: str) -> str:
    """Hash an API key using SHA-256.

    Args:
        key: The raw API key

    Returns:
        The hashed key
    """
    return hashlib.sha256(key.encode()).hexdigest()


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
    if expires_delta is None:
        expires_delta = timedelta(hours=config.auth.jwt_expiration_hours)

    expire = datetime.utcnow() + expires_delta
    payload = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "exp": expire,
    }
    return jwt.encode(
        payload,
        config.auth.jwt_secret,
        algorithm=config.auth.jwt_algorithm,
    )


def decode_jwt_token(token: str) -> dict:
    """Decode and validate a JWT token.

    Args:
        token: The JWT token string

    Returns:
        The payload dict

    Raises:
        HTTPException: If the token is invalid
    """
    config = get_config()
    try:
        payload = jwt.decode(
            token,
            config.auth.jwt_secret,
            algorithms=[config.auth.jwt_algorithm],
        )
        return payload
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


def get_tenant_filter(tenant: Tenant, model):
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
    return model.tenant_id == str(tenant.id)


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

    if not guest_tenant:
        guest_tenant = Tenant(
            name="Guest",
            tenant_type=TenantType.GUEST,
        )
        db.add(guest_tenant)
        db.commit()
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

    if not system_tenant:
        system_tenant = Tenant(
            name="System",
            tenant_type=TenantType.SYSTEM,
        )
        db.add(system_tenant)
        db.commit()
        db.refresh(system_tenant)

    return system_tenant


class GuestTenant:
    """Represents a guest (unauthenticated) tenant.

    Guest tenants are temporary and don't require authentication.
    Sessions are managed in-memory.
    """

    def __init__(self, tenant: Tenant):
        """Initialize guest tenant.

        Args:
            tenant: The guest tenant instance
        """
        self.tenant = tenant


async def get_guest_tenant(
    db: Session = Depends(get_db),
) -> GuestTenant:
    """Get the guest tenant (no auth required).

    This creates/returns the shared guest tenant for unauthenticated access.

    Args:
        db: Database session

    Returns:
        GuestTenant instance
    """
    guest_tenant = get_or_create_guest_tenant(db)
    return GuestTenant(tenant=guest_tenant)


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
    if config.auth.api_key and token == config.auth.api_key:
        # Create or get system tenant for global API key
        system_tenant = get_or_create_system_tenant(db)
        return CurrentTenant(tenant=system_tenant, user_id="system")

    # Try JWT token
    if scheme.lower() == "bearer":
        try:
            payload = decode_jwt_token(token)
            tenant_id = payload.get("tenant_id")
            user_id = payload.get("sub")

            tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
            if not tenant:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid tenant",
                )

            return CurrentTenant(tenant=tenant, user_id=user_id)
        except HTTPException:
            raise
        except Exception:
            pass  # Fall through to try API key

    # Try tenant API key
    key_hash = hash_api_key(token)
    api_key = db.query(APIKey).filter(APIKey.key_hash == key_hash).first()

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    if not api_key.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key is inactive",
        )

    if api_key.expires_at and api_key.expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key has expired",
        )

    # Update last used
    api_key.last_used_at = datetime.utcnow()
    db.commit()

    tenant = api_key.tenant
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    return CurrentTenant(tenant=tenant)


def require_scope(required_scope: str):
    """Create a dependency that checks for a required scope.

    Args:
        required_scope: The required scope (e.g., "agent:read")

    Returns:
        A dependency function
    """

    async def scope_checker(
        authorization: Annotated[str | None, Header()] = None,
        db: Session = Depends(get_db),
    ) -> CurrentTenant:
        """Check if the API key has the required scope."""
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

        # For now, only check API keys for scopes
        if scheme.lower() == "bearer":
            # JWT tokens get full access
            return await get_current_tenant(authorization, db)

        # Check API key scopes
        key_hash = hash_api_key(token)
        api_key = db.query(APIKey).filter(APIKey.key_hash == key_hash).first()

        if not api_key or not api_key.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key",
            )

        if required_scope not in api_key.scopes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required scope: {required_scope}",
            )

        return await get_current_tenant(authorization, db)

    return scope_checker
