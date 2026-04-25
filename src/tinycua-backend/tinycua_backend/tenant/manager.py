"""Tenant management service."""

import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from tinycua_backend.auth.models import User
from tinycua_backend.tenant.models import Tenant, TenantType


class TenantManager:
    """Manager for tenant CRUD operations."""

    def __init__(self, db: Session) -> None:
        """Initialize the tenant manager.

        Args:
            db: Database session
        """
        self._db = db

    def create_tenant(
        self, name: str, tenant_type: TenantType = TenantType.STANDARD
    ) -> Tenant:
        """Create a new tenant.

        Args:
            name: Tenant name
            tenant_type: Type of tenant

        Returns:
            Created tenant

        Raises:
            ValueError: If tenant creation fails
        """
        tenant = Tenant(name=name, tenant_type=tenant_type)
        self._db.add(tenant)
        try:
            self._db.commit()
            self._db.refresh(tenant)
        except IntegrityError:
            self._db.rollback()
            raise ValueError(f"Tenant with name '{name}' already exists")
        return tenant

    def get_tenant(self, tenant_id: uuid.UUID) -> Tenant | None:
        """Get a tenant by ID.

        Args:
            tenant_id: Tenant ID

        Returns:
            Tenant or None if not found
        """
        return self._db.query(Tenant).filter(Tenant.id == tenant_id).first()

    def get_tenant_by_name(self, name: str) -> Tenant | None:
        """Get a tenant by name.

        Args:
            name: Tenant name

        Returns:
            Tenant or None if not found
        """
        return self._db.query(Tenant).filter(Tenant.name == name).first()

    def list_tenants(self) -> list[Tenant]:
        """List all tenants.

        Returns:
            List of all tenants
        """
        return self._db.query(Tenant).all()

    def update_tenant(self, tenant_id: uuid.UUID, name: str) -> Tenant:
        """Update a tenant's name.

        Args:
            tenant_id: Tenant ID
            name: New name

        Returns:
            Updated tenant

        Raises:
            ValueError: If tenant not found
        """
        tenant = self.get_tenant(tenant_id)
        if not tenant:
            raise ValueError("Tenant not found")
        tenant.name = name
        self._db.commit()
        self._db.refresh(tenant)
        return tenant

    def delete_tenant(self, tenant_id: uuid.UUID) -> None:
        """Delete a tenant.

        Args:
            tenant_id: Tenant ID

        Raises:
            ValueError: If tenant not found
        """
        tenant = self.get_tenant(tenant_id)
        if not tenant:
            raise ValueError("Tenant not found")
        self._db.delete(tenant)
        self._db.commit()

    def list_tenant_users(self, tenant_id: uuid.UUID) -> list[User]:
        """List all users in a tenant.

        Args:
            tenant_id: Tenant ID

        Returns:
            List of users in the tenant
        """
        return self._db.query(User).filter(User.tenant_id == tenant_id).all()
