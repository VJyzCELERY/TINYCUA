"""Unit tests for ToolResolver."""

import pytest
from pathlib import Path

from tinycua_sdk.agent.tool_resolver import (
    ToolResolver,
    ToolResolutionError,
    TimeoutError,
)
from tinycua_sdk.tools.decorators import Tool
from tinycua_sdk.core.registry import ToolRegistry


@pytest.fixture
def registry():
    """Create a fresh ToolRegistry for testing."""
    reg = ToolRegistry()
    reg.clear()
    yield reg
    reg.clear()


@pytest.fixture
def resolver(registry):
    """Create a ToolResolver with test registry."""
    return ToolResolver(registry=registry, strict_mode=False)


@pytest.fixture
def resolver_strict(registry):
    """Create a ToolResolver in strict mode."""
    return ToolResolver(registry=registry, strict_mode=True)


class TestToolResolutionError:
    """Tests for ToolResolutionError exception."""

    def test_exception_message(self):
        """Test that exception message is preserved."""
        error = ToolResolutionError("Test error message")
        assert str(error) == "Test error message"

    def test_exception_with_tool_spec(self):
        """Test that tool_spec is preserved."""
        tool_spec = {"tool": "source"}
        error = ToolResolutionError("Error", tool_spec=tool_spec)
        assert error.tool_spec == tool_spec


class TestTimeoutError:
    """Tests for TimeoutError exception."""

    def test_exception_message(self):
        """Test that exception message is preserved."""
        error = TimeoutError("Timeout occurred")
        assert str(error) == "Timeout occurred"


class TestToolResolverInit:
    """Tests for ToolResolver initialization."""

    def test_default_registry(self, resolver):
        """Test that default registry is used when not provided."""
        assert resolver.registry is not None

    def test_custom_registry(self, registry, resolver):
        """Test that custom registry is used when provided."""
        assert resolver.registry is registry

    def test_strict_mode_default(self):
        """Test that strict mode defaults to False."""
        resolver = ToolResolver()
        assert resolver._strict_mode is False

    def test_strict_mode_true(self):
        """Test that strict mode can be set to True."""
        resolver = ToolResolver(strict_mode=True)
        assert resolver._strict_mode is True


class TestToolSpecParsing:
    """Tests for tool specification parsing."""

    def test_parse_string_reference(self, resolver):
        """Test parsing a string tool reference."""
        tool_specs = ["search_web", "calculate"]
        result = resolver._parse_tool_specs(tool_specs)
        assert result == ["search_web", "calculate"]

    def test_parse_inline_tool(self, resolver):
        """Test parsing an inline tool definition."""
        tool_specs = [
            {
                "tool": "@tool\ndef custom_adder(a: int, b: int) -> int:\n    return a + b"
            }
        ]
        result = resolver._parse_tool_specs(tool_specs)
        assert len(result) == 1
        assert result[0]["tool"].startswith("@tool")

    def test_parse_mcp_tool(self, resolver):
        """Test parsing an MCP tool configuration."""
        tool_specs = [{"mcp": "filesystem", "server": "filesystem"}]
        result = resolver._parse_tool_specs(tool_specs)
        assert len(result) == 1
        assert result[0]["mcp"] == "filesystem"

    def test_parse_mixed_formats(self, resolver):
        """Test parsing mixed tool formats."""
        tool_specs = [
            "search_web",
            {"tool": "@tool\ndef test(): pass"},
            {"mcp": "filesystem", "server": "filesystem"},
        ]
        result = resolver._parse_tool_specs(tool_specs)
        assert len(result) == 3

    def test_parse_empty_list(self, resolver):
        """Test parsing empty tool list."""
        tool_specs = []
        result = resolver._parse_tool_specs(tool_specs)
        assert result == []


class TestToolReferenceResolution:
    """Tests for tool reference resolution."""

    def test_resolve_registered_tool(self, registry, resolver):
        """Test resolving a registered tool."""
        test_tool = Tool(
            name="search_web",
            description="Search the web",
            parameters={"type": "object", "properties": {}},
        )
        registry.register(
            name="search_web", tool=test_tool, schema=test_tool.to_config()
        )

        result = resolver.resolve_tool_reference("search_web")
        assert isinstance(result, Tool)
        assert result.name == "search_web"

    def test_resolve_unregistered_tool_returns_string(self, registry, resolver):
        """Test that unresolved tool returns string for lazy resolution."""
        result = resolver.resolve_tool_reference("unknown_tool")
        assert result == "unknown_tool"

    def test_resolve_unregistered_tool_strict_mode(self, registry, resolver_strict):
        """Test that unresolved tool raises error in strict mode."""
        with pytest.raises(ToolResolutionError) as exc_info:
            resolver_strict.resolve_tool_reference("unknown_tool")
        assert "unknown_tool" in str(exc_info.value)


class TestInlineToolResolution:
    """Tests for inline tool resolution."""

    def test_resolve_valid_inline_tool(self, registry, resolver):
        """Test resolving a valid inline tool."""
        source = '''@tool
def custom_adder(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b
'''
        result = resolver.resolve_inline_tool(source)
        assert isinstance(result, Tool)
        assert result.name == "custom_adder"

    def test_resolve_inline_tool_syntax_error(self, registry, resolver):
        """Test that invalid syntax raises error."""
        source = """@tool
def broken(a: int, b: int)
    return a + b
"""
        with pytest.raises(ToolResolutionError) as exc_info:
            resolver.resolve_inline_tool(source)
        assert "Invalid Python syntax" in str(exc_info.value)

    def test_resolve_inline_tool_dangerous_function(self, registry, resolver):
        """Test that dangerous functions are blocked."""
        source = """@tool
def dangerous():
    exec("print(1)")
"""
        with pytest.raises(ToolResolutionError) as exc_info:
            resolver.resolve_inline_tool(source)
        assert (
            "SecurityError" in str(exc_info.value)
            or "dangerous" in str(exc_info.value).lower()
        )

    def test_resolve_inline_tool_timeout(self, registry, resolver):
        """Test that timeout parameter is accepted (no subprocess used)."""
        source = '''@tool
def custom_adder(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b
'''
        # Timeout parameter is accepted but not used in AST-based approach
        result = resolver.resolve_inline_tool(source)
        assert isinstance(result, Tool)
        assert result.name == "custom_adder"


class TestMCPToolResolution:
    """Tests for MCP tool configuration resolution."""

    def test_resolve_valid_mcp_config(self, registry, resolver):
        """Test resolving a valid MCP configuration."""
        mcp_config = {
            "mcp": "filesystem",
            "server": "filesystem",
            "config": {"allowedDirectories": ["/home/user"]},
        }
        result = resolver.resolve_mcp_tool(mcp_config)
        assert result == mcp_config

    def test_resolve_mcp_missing_mcp_field(self, registry, resolver):
        """Test that missing 'mcp' field raises error."""
        mcp_config = {"server": "filesystem"}
        with pytest.raises(ToolResolutionError) as exc_info:
            resolver.resolve_mcp_tool(mcp_config)
        assert "mcp" in str(exc_info.value)

    def test_resolve_mcp_missing_server_field(self, registry, resolver):
        """Test that missing 'server' field raises error."""
        mcp_config = {"mcp": "filesystem"}
        with pytest.raises(ToolResolutionError) as exc_info:
            resolver.resolve_mcp_tool(mcp_config)
        assert "server" in str(exc_info.value)

    def test_resolve_mcp_empty_mcp_string(self, registry, resolver):
        """Test that empty 'mcp' string raises error."""
        mcp_config = {"mcp": "", "server": "filesystem"}
        with pytest.raises(ToolResolutionError) as exc_info:
            resolver.resolve_mcp_tool(mcp_config)
        assert "non-empty" in str(exc_info.value)

    def test_resolve_mcp_empty_server_string(self, registry, resolver):
        """Test that empty 'server' string raises error."""
        mcp_config = {"mcp": "filesystem", "server": ""}
        with pytest.raises(ToolResolutionError) as exc_info:
            resolver.resolve_mcp_tool(mcp_config)
        assert "non-empty" in str(exc_info.value)

    def test_resolve_mcp_invalid_config_type(self, registry, resolver):
        """Test that invalid config type raises error."""
        mcp_config = {"mcp": "filesystem", "server": "filesystem", "config": "invalid"}
        with pytest.raises(ToolResolutionError) as exc_info:
            resolver.resolve_mcp_tool(mcp_config)
        assert "dictionary" in str(exc_info.value)


class TestToolResolverResolve:
    """Tests for the main resolve method."""

    def test_resolve_string_tools(self, registry, resolver):
        """Test resolving string tool references."""
        tool_specs = ["search_web", "calculate"]
        result = resolver.resolve(tool_specs)
        assert result == ["search_web", "calculate"]

    def test_resolve_inline_tool(self, registry, resolver):
        """Test resolving inline tool definition."""
        tool_specs = [
            {
                "tool": "@tool\ndef custom_adder(a: int, b: int) -> int:\n    return a + b"
            }
        ]
        result = resolver.resolve(tool_specs)
        assert len(result) == 1
        assert isinstance(result[0], Tool)

    def test_resolve_mcp_tool(self, registry, resolver):
        """Test resolving MCP tool configuration."""
        mcp_config = {
            "mcp": "filesystem",
            "server": "filesystem",
            "config": {"allowedDirectories": ["/home/user"]},
        }
        tool_specs = [mcp_config]
        result = resolver.resolve(tool_specs)
        assert len(result) == 1
        assert result[0] == mcp_config

    def test_resolve_mixed_tool_formats(self, registry, resolver):
        """Test resolving mixed tool formats in single list."""
        # Register a tool
        test_tool = Tool(
            name="search_web",
            description="Search the web",
            parameters={"type": "object", "properties": {}},
        )
        registry.register(
            name="search_web", tool=test_tool, schema=test_tool.to_config()
        )

        tool_specs = [
            "search_web",  # Registered tool reference
            {
                "tool": "@tool\ndef custom_adder(a: int, b: int) -> int:\n    return a + b"
            },  # Inline tool
            {"mcp": "filesystem", "server": "filesystem"},  # MCP tool
        ]
        result = resolver.resolve(tool_specs)
        assert len(result) == 3
        # First should be resolved to Tool
        assert isinstance(result[0], Tool)
        # Second should be resolved to Tool (inline)
        assert isinstance(result[1], Tool)
        # Third should be kept as dict (MCP config)
        assert isinstance(result[2], dict)
        assert result[2]["mcp"] == "filesystem"

    def test_resolve_empty_list(self, registry, resolver):
        """Test resolving empty tool list."""
        tool_specs = []
        result = resolver.resolve(tool_specs)
        assert result == []


class TestInlineToolRegistration:
    """Tests for inline tool registration."""

    def test_inline_tool_registered_in_registry(self, registry, resolver):
        """Test that inline tools are registered in the registry."""
        source = '''@tool
def custom_adder(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b
'''
        result = resolver.resolve_inline_tool(source)

        # Tool should be registered
        entry = registry.get("custom_adder")
        assert entry is not None
        assert entry.tool is result
