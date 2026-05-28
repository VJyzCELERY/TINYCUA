"""Tenant management API endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from tinycua_backend.auth.core import CurrentTenant, get_current_tenant
from tinycua_backend.storage.database import get_db
from tinycua_backend.tenant.manager import TenantManager

router = APIRouter(prefix="/v1/tenants", tags=["tenants"])


class TenantResponse(BaseModel):
    """Response model for tenant."""

    tenant_id: str
    name: str
    tenant_type: str


class TenantUpdateRequest(BaseModel):
    """Request model for updating a tenant."""

    name: str


@router.get("/{tenant_id}", response_model=TenantResponse)
async def get_tenant(
    tenant_id: str,
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> TenantResponse:
    """Get a tenant by ID.

    Args:
        tenant_id: Tenant ID
        current_tenant: Current authenticated tenant
        db: Database session

    Returns:
        Tenant information

    Raises:
        HTTPException: If not authorized or tenant not found
    """
    manager = TenantManager(db)
    try:
        tenant_uuid = uuid.UUID(tenant_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid tenant ID format",
        )

    tenant = manager.get_tenant(tenant_uuid)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )

    if not current_tenant.is_system and current_tenant.tenant.id != tenant.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this tenant",
        )

    return TenantResponse(
        tenant_id=str(tenant.id),
        name=tenant.name,
        tenant_type=tenant.tenant_type.value,
    )


@router.get("/", response_model=list[TenantResponse])
async def list_tenants(
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> list[TenantResponse]:
    """List all tenants.

    Args:
        current_tenant: Current authenticated tenant
        db: Database session

    Returns:
        List of all tenants

    Raises:
        HTTPException: If not authorized
    """
    if not current_tenant.is_system:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only system tenant can list all tenants",
        )

    manager = TenantManager(db)
    tenants = manager.list_tenants()

    return [
        TenantResponse(
            tenant_id=str(t.id),
            name=t.name,
            tenant_type=t.tenant_type.value,
        )
        for t in tenants
    ]


@router.patch("/{tenant_id}", response_model=TenantResponse)
async def update_tenant(
    tenant_id: str,
    request: TenantUpdateRequest,
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> TenantResponse:
    """Update a tenant.

    Args:
        tenant_id: Tenant ID
        request: Tenant update request
        current_tenant: Current authenticated tenant
        db: Database session

    Returns:
        Updated tenant

    Raises:
        HTTPException: If not authorized or tenant not found
    """
    manager = TenantManager(db)
    try:
        tenant_uuid = uuid.UUID(tenant_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid tenant ID format",
        )

    if not current_tenant.is_system and current_tenant.tenant.id != tenant_uuid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this tenant",
        )

    try:
        tenant = manager.update_tenant(tenant_uuid, request.name)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    return TenantResponse(
        tenant_id=str(tenant.id),
        name=tenant.name,
        tenant_type=tenant.tenant_type.value,
    )


@router.delete("/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tenant(
    tenant_id: str,
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> None:
    """Delete a tenant.

    Args:
        tenant_id: Tenant ID
        current_tenant: Current authenticated tenant
        db: Database session

    Raises:
        HTTPException: If not authorized or tenant not found
    """
    manager = TenantManager(db)
    try:
        tenant_uuid = uuid.UUID(tenant_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid tenant ID format",
        )

    if not current_tenant.is_system:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only system tenant can delete tenants",
        )

    try:
        manager.delete_tenant(tenant_uuid)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
