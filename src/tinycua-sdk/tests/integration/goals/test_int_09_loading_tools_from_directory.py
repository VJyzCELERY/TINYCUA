"""Integration tests for tool directory loading."""

from pathlib import Path

from tinycua_sdk import Tool


class TestInt09LoadingToolsFromDirectory:
    """Test suite for Tool.load_directory and from_config."""

    def test_int_01_tool_directory_discovery(self, tmp_path: Path):
        """load_directory finds @tool functions in subdirectory modules."""
        tools_dir = tmp_path / "my_tools"
        mod_dir = tools_dir / "math_tools"
        mod_dir.mkdir(parents=True)
        (mod_dir / "__init__.py").write_text("")
        (mod_dir / "arithmetic.py").write_text(
            "from tinycua_sdk import tool\n\n"
            "@tool\ndef add(a: int, b: int) -> int:\n"
            '    """Add two numbers."""\n'
            "    return a + b\n"
        )

        tools = Tool.load_directory(tools_dir)
        assert len(tools) == 1
        assert tools[0].name == "add"

    def test_int_02_tool_directory_empty(self, tmp_path: Path):
        """load_directory returns empty list for empty directory."""
        empty_dir = tmp_path / "empty_tools"
        empty_dir.mkdir(parents=True)
        assert Tool.load_directory(empty_dir) == []

    def test_int_03_tool_directory_no_tools(self, tmp_path: Path):
        """Directory with modules but no @tool functions returns empty list."""
        tools_dir = tmp_path / "no_tools"
        mod_dir = tools_dir / "utils"
        mod_dir.mkdir(parents=True)
        (mod_dir / "__init__.py").write_text("")
        (mod_dir / "helpers.py").write_text(
            "def helper_func():\n    return 42\n"
        )

        tools = Tool.load_directory(tools_dir)
        assert tools == []

    def test_int_04_tool_directory_skips_prefix_underscore(self, tmp_path: Path):
        """Files starting with _ are skipped."""
        tools_dir = tmp_path / "filtered_tools"
        mod_dir = tools_dir / "filtered"
        mod_dir.mkdir(parents=True)
        (mod_dir / "__init__.py").write_text("")
        (mod_dir / "_private.py").write_text(
            "from tinycua_sdk import tool\n\n"
            "@tool\ndef hidden() -> None:\n"
            '    """Hidden tool."""\n'
            "    pass\n"
        )
        (mod_dir / "public.py").write_text(
            "from tinycua_sdk import tool\n\n"
            "@tool\ndef visible() -> None:\n"
            '    """Visible tool."""\n'
            "    pass\n"
        )

        tools = Tool.load_directory(tools_dir)
        names = [t.name for t in tools]
        assert "visible" in names
        assert "hidden" not in names

    def test_int_05_tool_from_config_openai_format(self):
        """Tool.from_config handles OpenAI-style function config dict."""
        config = {
            "type": "function",
            "function": {
                "name": "greet",
                "description": "Greet someone.",
                "parameters": {
                    "type": "object",
                    "properties": {"name": {"type": "string"}},
                    "required": ["name"],
                },
            },
        }
        tool = Tool.from_config(config)
        assert tool.name == "greet"
        assert tool.description == "Greet someone."
        assert "name" in tool.parameters["properties"]

    def test_int_06_tool_directory_multiple_tools(self, tmp_path: Path):
        """load_directory finds multiple @tool functions across modules."""
        tools_dir = tmp_path / "multi_tools"
        mod_dir = tools_dir / "string_tools"
        mod_dir.mkdir(parents=True)
        (mod_dir / "__init__.py").write_text("")
        (mod_dir / "text.py").write_text(
            "from tinycua_sdk import tool\n\n"
            "@tool\ndef uppercase(s: str) -> str:\n"
            '    """Convert to uppercase."""\n'
            "    return s.upper()\n\n"
            "@tool\ndef lowercase(s: str) -> str:\n"
            '    """Convert to lowercase."""\n'
            "    return s.lower()\n"
        )

        tools = Tool.load_directory(tools_dir)
        assert len(tools) == 2
        names = {t.name for t in tools}
        assert names == {"uppercase", "lowercase"}
