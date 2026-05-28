"""Authentication dependencies for tinycua-backend."""

from __future__ import annotations

import asyncio
import hmac
import logging
import uuid
from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import Depends, Header, HTTPException, status
from jose import JWTError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from tinycua_backend.auth.api_keys import (
    MAX_API_KEYS_PER_REQUEST,
    MIN_API_KEY_LENGTH,
    verify_api_key,
)
from tinycua_backend.auth.jwt import decode_jwt_token
from tinycua_backend.auth.models import APIKey
from tinycua_backend.config import get_config
from tinycua_backend.storage.database import get_db
from tinycua_backend.tenant.models import Tenant, TenantType

logger = logging.getLogger(__name__)


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
