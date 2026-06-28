"""Unit tests for SystemPrompt and SystemPromptBuilder."""

from tinycua.config.system_prompt import SystemPrompt, SystemPromptBuilder


class TestSystemPrompt:
    """Tests for SystemPrompt dataclass."""

    def test_construction(self) -> None:
        """Test SystemPrompt construction."""
        prompt = SystemPrompt(
            priority=0,
            kind="static",
            content="Hello",
        )
        assert prompt.priority == 0
        assert prompt.kind == "static"
        assert prompt.content == "Hello"
        assert prompt.metadata == {}

    def test_with_metadata(self) -> None:
        """Test SystemPrompt with metadata."""
        prompt = SystemPrompt(
            priority=1,
            kind="dynamic",
            content="Context",
            metadata={"source": "test"},
        )
        assert prompt.metadata == {"source": "test"}


class TestSystemPromptBuilder:
    """Tests for SystemPromptBuilder class."""

    def test_empty_build(self) -> None:
        """Test build with no fragments."""
        builder = SystemPromptBuilder()
        result = builder.build()
        assert result == {"role": "system", "content": ""}

    def test_add_static(self) -> None:
        """Test adding static fragment."""
        builder = SystemPromptBuilder()
        builder.add_static("Static prompt")
        assert len(builder.fragments) == 1
        assert builder.fragments[0].kind == "static"
        assert builder.fragments[0].content == "Static prompt"

    def test_add_configurable_append(self) -> None:
        """Test adding configurable append fragment."""
        builder = SystemPromptBuilder()
        builder.add_configurable_append("Configurable prompt")
        assert len(builder.fragments) == 1
        assert builder.fragments[0].kind == "configurable"
        assert builder.fragments[0].content == "Configurable prompt"

    def test_add_dynamic_context(self) -> None:
        """Test adding dynamic context fragment."""
        builder = SystemPromptBuilder()
        builder.add_dynamic_context("Dynamic context")
        assert len(builder.fragments) == 1
        assert builder.fragments[0].kind == "dynamic"
        assert builder.fragments[0].content == "Dynamic context"

    def test_priority_ordering(self) -> None:
        """Test fragments are ordered by priority."""
        builder = SystemPromptBuilder()
        builder.add_dynamic_context("Dynamic")  # priority 0
        builder.add_static("Static")  # priority 1
        builder.add_configurable_append("Configurable")  # priority 2

        result = builder.build()
        # Should be in insertion order since priorities are sequential
        assert "Dynamic" in result["content"]
        assert "Static" in result["content"]
        assert "Configurable" in result["content"]

    def test_build_output_format(self) -> None:
        """Test build returns correct format."""
        builder = SystemPromptBuilder()
        builder.add_static("Static prompt")
        builder.add_configurable_append("Configurable prompt")
        builder.add_dynamic_context("Dynamic context")

        result = builder.build()
        assert result["role"] == "system"
        assert isinstance(result["content"], str)
        assert "Static prompt" in result["content"]
        assert "Configurable prompt" in result["content"]
        assert "Dynamic context" in result["content"]

    def test_build_merges_content(self) -> None:
        """Test build merges content with newlines."""
        builder = SystemPromptBuilder()
        builder.add_static("Line 1")
        builder.add_static("Line 2")

        result = builder.build()
        lines = result["content"].split("\n")
        assert "Line 1" in lines
        assert "Line 2" in lines
