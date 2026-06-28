"""Unit tests for LocalModelConfig."""

from tinycua.config.local_model import LocalModelConfig


class TestLocalModelConfig:
    """Tests for LocalModelConfig dataclass."""

    def test_construction_with_required_fields(self) -> None:
        """Test construction with required fields only."""
        config = LocalModelConfig(
            base_url="http://localhost:11434/v1",
            model="llama3",
        )
        assert config.base_url == "http://localhost:11434/v1"
        assert config.model == "llama3"
        assert config.api_key is None
        assert config.timeout == 30.0
        assert config.temperature == 0.7
        assert config.max_tokens is None

    def test_construction_with_all_fields(self) -> None:
        """Test construction with all fields."""
        config = LocalModelConfig(
            base_url="http://localhost:11434/v1",
            model="llama3",
            api_key="test-key",
            timeout=60.0,
            temperature=0.5,
            max_tokens=1024,
        )
        assert config.base_url == "http://localhost:11434/v1"
        assert config.model == "llama3"
        assert config.api_key == "test-key"
        assert config.timeout == 60.0
        assert config.temperature == 0.5
        assert config.max_tokens == 1024

    def test_default_values(self) -> None:
        """Test default values are correct."""
        config = LocalModelConfig(
            base_url="http://example.com",
            model="test",
        )
        assert config.api_key is None
        assert config.timeout == 30.0
        assert config.temperature == 0.7
        assert config.max_tokens is None
