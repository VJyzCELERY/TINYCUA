"""Test utilities for tinycua-backend unit tests."""

from __future__ import annotations

from typing import Any


def get_tenant_filter(tenant: Any, model: Any) -> Any:
    """Get filter condition for tenant-specific queries.

    For system tenant, returns no filter (access all).
    For other tenants, returns filter by tenant_id.

    Args:
        tenant: The tenant instance
        model: The SQLAlchemy model to filter

    Returns:
        Filter condition or None for system tenant
    """
    from tinycua_backend.tenant.models import TenantType

    if tenant.tenant_type == TenantType.SYSTEM:
        return None
    return model.tenant_id == tenant.id
