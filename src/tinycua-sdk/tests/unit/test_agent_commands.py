"""Unit tests for agent CLI commands module."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest


class TestValidateAgentPath:
    """Tests for _validate_agent_path function."""

    def test_validate_valid_path(self):
        """Valid path returns resolved absolute path."""
        from tinycua_sdk.cli.agent_commands import _validate_agent_path

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "agent.md"
            path.write_text("---\nname: test\n---")
            result = _validate_agent_path(path)
            assert result.is_absolute()
            assert result == path.resolve()

    def test_validate_rejects_traversal(self):
        """Path traversal attempt raises ValueError."""
        from tinycua_sdk.cli.agent_commands import _validate_agent_path

        with pytest.raises(ValueError) as exc_info:
            _validate_agent_path(Path("../../etc/passwd"))
        assert "directory traversal" in str(exc_info.value).lower()

    def test_validate_accepts_absolute_path(self):
        """Absolute path without traversal is accepted."""
        from tinycua_sdk.cli.agent_commands import _validate_agent_path

        # Absolute paths without .. are valid
        result = _validate_agent_path(Path("/tmp/agent.md"))
        assert result.is_absolute()


class TestLoadOverrideFile:
    """Tests for _load_override_file function."""

    def test_load_json_override(self):
        """Loading JSON override file works."""
        from tinycua_sdk.cli.agent_commands import _load_override_file

        with tempfile.TemporaryDirectory() as tmpdir:
            override_file = Path(tmpdir) / "overrides.json"
            override_file.write_text('{"model": "gpt-4o"}')
            result = _load_override_file(override_file)
            assert result["model"] == "gpt-4o"

    def test_load_yaml_override(self):
        """Loading YAML override file works."""
        from tinycua_sdk.cli.agent_commands import _load_override_file

        with tempfile.TemporaryDirectory() as tmpdir:
            override_file = Path(tmpdir) / "overrides.yaml"
            override_file.write_text("model: gpt-4o\n")
            result = _load_override_file(override_file)
            assert result["model"] == "gpt-4o"

    def test_load_nonexistent_file(self):
        """Loading nonexistent file raises error."""
        from tinycua_sdk.cli.agent_commands import _load_override_file

        with pytest.raises(ValueError) as exc_info:
            _load_override_file(Path("/nonexistent/overrides.json"))
        assert "not found" in str(exc_info.value).lower()

    def test_load_malformed_json(self):
        """Loading malformed JSON raises error."""
        from tinycua_sdk.cli.agent_commands import _load_override_file

        with tempfile.TemporaryDirectory() as tmpdir:
            override_file = Path(tmpdir) / "overrides.json"
            override_file.write_text("{invalid json}")
            with pytest.raises(ValueError) as exc_info:
                _load_override_file(override_file)
            assert "parse" in str(exc_info.value).lower()

    def test_load_malformed_yaml(self):
        """Loading malformed YAML raises error."""
        from tinycua_sdk.cli.agent_commands import _load_override_file

        with tempfile.TemporaryDirectory() as tmpdir:
            override_file = Path(tmpdir) / "overrides.yaml"
            override_file.write_text("invalid: yaml: : :")
            with pytest.raises(ValueError) as exc_info:
                _load_override_file(override_file)
            assert "parse" in str(exc_info.value).lower()


class TestCmdAgentCreate:
    """Tests for cmd_agent_create function."""

    @pytest.mark.asyncio
    async def test_create_from_file(self):
        """Creating agent from AGENT.md file works."""
        from tinycua_sdk.cli.agent_commands import cmd_agent_create

        args = MagicMock()
        args.path = str(
            Path(__file__).parent.parent / "fixtures" / "agents" / "simple_agent.md"
        )
        args.template = None
        args.model = None
        args.provider = None
        args.tools = None
        args.skills = None
        args.loop = None
        args.temperature = None
        args.override_file = None

        result = await cmd_agent_create(args)
        assert result == 0

    @pytest.mark.asyncio
    async def test_create_from_directory(self):
        """Creating agent from directory with AGENT.md works."""
        from tinycua_sdk.cli.agent_commands import cmd_agent_create

        args = MagicMock()
        args.path = str(Path(__file__).parent.parent / "fixtures" / "agents" / "basic")
        args.template = None
        args.model = None
        args.provider = None
        args.tools = None
        args.skills = None
        args.loop = None
        args.temperature = None
        args.override_file = None

        result = await cmd_agent_create(args)
        assert result == 0

    @pytest.mark.asyncio
    async def test_create_from_template_coder(self):
        """Creating agent from coder template works."""
        from tinycua_sdk.cli.agent_commands import cmd_agent_create

        args = MagicMock()
        args.path = None
        args.template = "coder"
        args.model = None
        args.provider = None
        args.tools = None
        args.skills = None
        args.loop = None
        args.temperature = None
        args.override_file = None

        result = await cmd_agent_create(args)
        assert result == 0

    @pytest.mark.asyncio
    async def test_create_from_template_researcher(self):
        """Creating agent from researcher template works."""
        from tinycua_sdk.cli.agent_commands import cmd_agent_create

        args = MagicMock()
        args.path = None
        args.template = "researcher"
        args.model = None
        args.provider = None
        args.tools = None
        args.skills = None
        args.loop = None
        args.temperature = None
        args.override_file = None

        result = await cmd_agent_create(args)
        assert result == 0

    @pytest.mark.asyncio
    async def test_create_from_template_assistant(self):
        """Creating agent from assistant template works."""
        from tinycua_sdk.cli.agent_commands import cmd_agent_create

        args = MagicMock()
        args.path = None
        args.template = "assistant"
        args.model = None
        args.provider = None
        args.tools = None
        args.skills = None
        args.loop = None
        args.temperature = None
        args.override_file = None

        result = await cmd_agent_create(args)
        assert result == 0

    @pytest.mark.asyncio
    async def test_create_invalid_template(self):
        """Creating agent with invalid template shows error."""
        from tinycua_sdk.cli.agent_commands import cmd_agent_create

        args = MagicMock()
        args.path = None
        args.template = "invalid_template"
        args.model = None
        args.provider = None
        args.tools = None
        args.skills = None
        args.loop = None
        args.temperature = None
        args.override_file = None

        result = await cmd_agent_create(args)
        assert result == 1

    @pytest.mark.asyncio
    async def test_create_with_cli_override(self):
        """Creating agent with CLI override works."""
        from tinycua_sdk.cli.agent_commands import cmd_agent_create

        args = MagicMock()
        args.path = None
        args.template = "coder"
        args.model = "gpt-4o"
        args.provider = None
        args.tools = None
        args.skills = None
        args.loop = None
        args.temperature = None
        args.override_file = None

        result = await cmd_agent_create(args)
        assert result == 0

    @pytest.mark.asyncio
    async def test_create_with_override_file_json(self):
        """Creating agent with JSON override file works."""
        from tinycua_sdk.cli.agent_commands import cmd_agent_create

        args = MagicMock()
        args.path = None
        args.template = "coder"
        args.model = None
        args.provider = None
        args.tools = None
        args.skills = None
        args.loop = None
        args.temperature = None
        args.override_file = str(
            Path(__file__).parent.parent / "fixtures" / "agents" / "overrides.json"
        )

        result = await cmd_agent_create(args)
        assert result == 0

    @pytest.mark.asyncio
    async def test_create_with_override_file_yaml(self):
        """Creating agent with YAML override file works."""
        from tinycua_sdk.cli.agent_commands import cmd_agent_create

        args = MagicMock()
        args.path = None
        args.template = "coder"
        args.model = None
        args.provider = None
        args.tools = None
        args.skills = None
        args.loop = None
        args.temperature = None
        args.override_file = str(
            Path(__file__).parent.parent / "fixtures" / "agents" / "overrides.yaml"
        )

        result = await cmd_agent_create(args)
        assert result == 0

    @pytest.mark.asyncio
    async def test_create_missing_file(self):
        """Creating agent from missing file returns error."""
        from tinycua_sdk.cli.agent_commands import cmd_agent_create

        args = MagicMock()
        args.path = "/nonexistent/AGENT.md"
        args.template = None
        args.model = None
        args.provider = None
        args.tools = None
        args.skills = None
        args.loop = None
        args.temperature = None
        args.override_file = None

        result = await cmd_agent_create(args)
        assert result == 1

    @pytest.mark.asyncio
    async def test_create_path_traversal(self):
        """Path traversal attempt is rejected."""
        from tinycua_sdk.cli.agent_commands import cmd_agent_create

        args = MagicMock()
        args.path = "../../etc/passwd"
        args.template = None
        args.model = None
        args.provider = None
        args.tools = None
        args.skills = None
        args.loop = None
        args.temperature = None
        args.override_file = None

        result = await cmd_agent_create(args)
        assert result == 1


class TestCmdAgentTemplates:
    """Tests for cmd_agent_templates function."""

    @pytest.mark.asyncio
    async def test_templates_list_all(self):
        """Listing all templates works."""
        from tinycua_sdk.cli.agent_commands import cmd_agent_templates

        args = MagicMock()
        args.verbose = False

        result = await cmd_agent_templates(args)
        assert result == 0

    @pytest.mark.asyncio
    async def test_templates_verbose(self):
        """Listing templates with verbose flag works."""
        from tinycua_sdk.cli.agent_commands import cmd_agent_templates

        args = MagicMock()
        args.verbose = True

        result = await cmd_agent_templates(args)
        assert result == 0


class TestCmdAgentInfo:
    """Tests for cmd_agent_info function."""

    @pytest.mark.asyncio
    async def test_info_from_file(self):
        """Showing info from AGENT.md file works."""
        from tinycua_sdk.cli.agent_commands import cmd_agent_info

        args = MagicMock()
        args.file = str(
            Path(__file__).parent.parent / "fixtures" / "agents" / "simple_agent.md"
        )
        args.template = None

        result = await cmd_agent_info(args)
        assert result == 0

    @pytest.mark.asyncio
    async def test_info_from_template(self):
        """Showing info from template works."""
        from tinycua_sdk.cli.agent_commands import cmd_agent_info

        args = MagicMock()
        args.file = None
        args.template = "coder"

        result = await cmd_agent_info(args)
        assert result == 0

    @pytest.mark.asyncio
    async def test_info_missing_args(self):
        """Showing info without file or template returns error."""
        from tinycua_sdk.cli.agent_commands import cmd_agent_info

        args = MagicMock()
        args.file = None
        args.template = None

        result = await cmd_agent_info(args)
        assert result == 1

    @pytest.mark.asyncio
    async def test_info_file_not_found(self):
        """Showing info from missing file returns error."""
        from tinycua_sdk.cli.agent_commands import cmd_agent_info

        args = MagicMock()
        args.file = "/nonexistent/AGENT.md"
        args.template = None

        result = await cmd_agent_info(args)
        assert result == 1
