"""Tests for client modules."""



class TestClientModules:
    """Test client modules."""

    def test_clients_module_imports(self):
        """Test clients module imports."""
        from tinycua_sdk import clients

        assert clients is not None

    def test_agent_client_import(self):
        """Test agent client can be imported."""
        from tinycua_sdk.clients.agent_client import AgentClient

        assert AgentClient is not None

    def test_backend_client_import(self):
        """Test backend client can be imported."""
        from tinycua_sdk.clients.backend import BackendClient

        assert BackendClient is not None


class TestBackendClient:
    """Test backend client."""

    def test_backend_client_init(self):
        """Test backend client initialization."""
        from tinycua_sdk.clients.backend import BackendClient

        client = BackendClient(base_url="http://localhost:8000")
        assert client is not None

    def test_backend_client_has_url(self):
        """Test backend client has base URL."""
        from tinycua_sdk.clients.backend import BackendClient

        client = BackendClient(base_url="http://localhost:8000")
        assert hasattr(client, "base_url")
