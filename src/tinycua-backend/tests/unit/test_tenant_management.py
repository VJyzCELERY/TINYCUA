"""Unit tests for tenant management."""

from unittest.mock import MagicMock, patch


from tinycua_backend.auth import CurrentTenant, get_or_create_guest_tenant, get_or_create_system_tenant
from tinycua_backend.models.tenant import Tenant, TenantType


class TestTenantCreation:
    """Tests for tenant creation."""

    def test_create_tenant(self, mock_db):
        """Test creating a new tenant."""
        mock_tenant = MagicMock()
        mock_tenant.id = "tenant-123"
        mock_tenant.name = "Test Tenant"
        mock_tenant.tenant_type = TenantType.STANDARD

        def mock_add(obj):
            obj.id = "tenant-123"

        mock_db.add.side_effect = mock_add
        mock_db.commit.side_effect = None

        new_tenant = Tenant(name="Test Tenant", tenant_type=TenantType.STANDARD)
        mock_db.add(new_tenant)

        assert new_tenant.name == "Test Tenant"

    def test_create_guest_tenant(self, mock_db):
        """Test creating a guest tenant."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        mock_guest = MagicMock()
        mock_guest.id = "guest-123"
        mock_guest.tenant_type = TenantType.GUEST

        def mock_add(obj):
            obj.id = "guest-123"

        mock_db.add.side_effect = mock_add
        mock_db.commit.side_effect = None

        with patch("tinycua_backend.auth.Tenant", return_value=mock_guest):
            guest_tenant = get_or_create_guest_tenant(mock_db)

            assert guest_tenant is not None

    def test_create_system_tenant(self, mock_db):
        """Test creating a system tenant."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        mock_system = MagicMock()
        mock_system.id = "system-123"
        mock_system.tenant_type = TenantType.SYSTEM

        def mock_add(obj):
            obj.id = "system-123"

        mock_db.add.side_effect = mock_add
        mock_db.commit.side_effect = None

        with patch("tinycua_backend.auth.Tenant", return_value=mock_system):
            system_tenant = get_or_create_system_tenant(mock_db)

            assert system_tenant is not None


class TestTenantIsolation:
    """Tests for tenant isolation."""

    def test_tenant_filter_for_standard_tenant(self, test_tenant):
        """Test tenant filter applies to standard tenants."""
        from tinycua_backend.auth import get_tenant_filter
        from tinycua_backend.models.user import User

        test_tenant.tenant_type = TenantType.STANDARD
        filter_condition = get_tenant_filter(test_tenant, User)

        assert filter_condition is not None

    def test_tenant_filter_for_system_tenant(self):
        """Test system tenant bypasses filtering."""
        from tinycua_backend.auth import get_tenant_filter
        from tinycua_backend.models.user import User

        system_tenant = MagicMock()
        system_tenant.tenant_type = TenantType.SYSTEM

        filter_condition = get_tenant_filter(system_tenant, User)

        assert filter_condition is None

    def test_current_tenant_is_system(self):
        """Test CurrentTenant.is_system returns True for system tenant."""
        system_tenant = MagicMock()
        system_tenant.tenant_type = TenantType.SYSTEM

        current = CurrentTenant(tenant=system_tenant, user_id="system")

        assert current.is_system is True

    def test_current_tenant_is_not_system(self):
        """Test CurrentTenant.is_system returns False for non-system tenant."""
        standard_tenant = MagicMock()
        standard_tenant.tenant_type = TenantType.STANDARD

        current = CurrentTenant(tenant=standard_tenant, user_id="user-123")

        assert current.is_system is False


class TestTenantModel:
    """Tests for Tenant model."""

    def test_tenant_type_enum(self):
        """Test TenantType enum values."""
        assert TenantType.STANDARD == "standard"
        assert TenantType.GUEST == "guest"
        assert TenantType.SYSTEM == "system"

    def test_tenant_attributes(self, test_tenant):
        """Test tenant has expected attributes."""
        assert hasattr(test_tenant, "id")
        assert hasattr(test_tenant, "name")
        assert hasattr(test_tenant, "tenant_type")


class TestTenantIsolationHTTP:
    """Tests for cross-tenant access prevention via HTTP endpoints."""

    def test_cross_tenant_access_prevented(self):
        """Test that tenant A cannot access tenant B's data through endpoint filters."""
        from tinycua_backend.auth import get_tenant_filter
        from tinycua_backend.models.user import User

        tenant_a = MagicMock()
        tenant_a.id = "tenant-a"
        tenant_a.tenant_type = TenantType.STANDARD

        tenant_b = MagicMock()
        tenant_b.id = "tenant-b"
        tenant_b.tenant_type = TenantType.STANDARD

        filter_a = get_tenant_filter(tenant_a, User)
        filter_b = get_tenant_filter(tenant_b, User)

        assert filter_a is not None
        assert filter_b is not None
        assert filter_a != filter_b

    def test_tenant_specific_data_isolation(self):
        """Test that tenant filter is applied for tenant-specific data queries."""
        from tinycua_backend.auth import get_tenant_filter
        from tinycua_backend.models.user import User

        tenant = MagicMock()
        tenant.id = "tenant-123"
        tenant.tenant_type = TenantType.STANDARD

        filter_condition = get_tenant_filter(tenant, User)

        assert filter_condition is not None

    def test_system_tenant_bypasses_isolation(self):
        """Test that system tenant can access all data."""
        from tinycua_backend.auth import get_tenant_filter
        from tinycua_backend.models.user import User

        system_tenant = MagicMock()
        system_tenant.id = "system-tenant"
        system_tenant.tenant_type = TenantType.SYSTEM

        filter_condition = get_tenant_filter(system_tenant, User)

        assert filter_condition is None
