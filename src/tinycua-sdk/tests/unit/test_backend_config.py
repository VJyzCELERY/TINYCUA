"""Tests for BackendConfig value object."""


class TestBackendConfig:
    """Tests for BackendConfig."""

    def test_backend_config_defaults(self):
        """BackendConfig defaults to local execution."""
        from tinycua_sdk import BackendConfig, BackendKind

        config = BackendConfig()
        assert config.kind == BackendKind.LOCAL

    def test_backend_config_remote(self):
        """BackendConfig can be configured for remote execution."""
        from tinycua_sdk import BackendConfig, BackendKind

        config = BackendConfig(
            kind=BackendKind.REMOTE,
            url="http://remote.example.com",
        )
        assert config.kind == BackendKind.REMOTE
        assert config.url == "http://remote.example.com"

    def test_backend_config_to_dict(self):
        """BackendConfig.to_dict() returns a plain dict."""
        from tinycua_sdk import BackendConfig, BackendKind

        config = BackendConfig(kind=BackendKind.REMOTE)
        d = config.to_dict()
        assert d["kind"] == "remote"

    def test_backend_config_round_trip(self):
        """BackendConfig serializes and deserializes correctly."""
        from tinycua_sdk import BackendConfig, BackendKind

        original = BackendConfig(
            kind=BackendKind.REMOTE,
            url="http://remote.example.com",
        )
        d = original.to_dict()
        restored = BackendConfig.from_dict(d)
        assert restored.kind == BackendKind.REMOTE
        assert restored.url == "http://remote.example.com"
