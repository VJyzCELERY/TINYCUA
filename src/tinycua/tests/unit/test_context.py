"""Unit tests for ExecutorContext and ExecutorConfig dataclasses."""

from __future__ import annotations

from dataclasses import fields

import pytest


# ---------------------------------------------------------------------------
# ExecutorConfig
# ---------------------------------------------------------------------------


class TestExecutorConfig:
    """Test the ExecutorConfig dataclass."""

    def test_default_values(self):
        """All fields should have correct defaults."""
        from tinycua.agent.tools.context import ExecutorConfig

        cfg = ExecutorConfig()
        assert cfg.shell_timeout == 30
        assert cfg.python_timeout == 30
        assert cfg.fetch_timeout == 30
        assert cfg.max_file_size == 102400  # 100KB
        assert cfg.max_fetch_size == 102400
        assert cfg.allowed_paths is None
        assert cfg.enable_fetch is True
        assert cfg.enable_python_exec is True

    def test_custom_values(self):
        """Custom values should override defaults."""
        from tinycua.agent.tools.context import ExecutorConfig

        cfg = ExecutorConfig(
            shell_timeout=10,
            python_timeout=5,
            fetch_timeout=15,
            max_file_size=51200,
            max_fetch_size=25600,
            allowed_paths=["/tmp"],
            enable_fetch=False,
            enable_python_exec=False,
        )
        assert cfg.shell_timeout == 10
        assert cfg.python_timeout == 5
        assert cfg.fetch_timeout == 15
        assert cfg.max_file_size == 51200
        assert cfg.max_fetch_size == 25600
        assert cfg.allowed_paths == ["/tmp"]
        assert cfg.enable_fetch is False
        assert cfg.enable_python_exec is False

    def test_allowed_paths_defaults_to_none(self):
        """allowed_paths=None means no path restrictions."""
        from tinycua.agent.tools.context import ExecutorConfig

        cfg = ExecutorConfig()
        assert cfg.allowed_paths is None

    def test_all_fields_have_type_annotations(self):
        """All fields should have proper type annotations."""
        from tinycua.agent.tools.context import ExecutorConfig

        for f in fields(ExecutorConfig):
            assert f.type is not None, f"Field {f.name} has no type annotation"


# ---------------------------------------------------------------------------
# ExecutorContext
# ---------------------------------------------------------------------------


class TestExecutorContext:
    """Test the ExecutorContext dataclass."""

    def test_default_values(self):
        """Default context should create a default config and None for others."""
        from tinycua.agent.tools.context import ExecutorContext

        ctx = ExecutorContext()
        assert ctx.session is None
        assert ctx.todo_list is None
        assert ctx.config is not None
        assert ctx.config.shell_timeout == 30

    def test_custom_config(self):
        """Custom config should be accepted."""
        from tinycua.agent.tools.context import ExecutorConfig, ExecutorContext

        config = ExecutorConfig(shell_timeout=5)
        ctx = ExecutorContext(config=config)
        assert ctx.config.shell_timeout == 5
        assert ctx.session is None
        assert ctx.todo_list is None

    def test_custom_todo_list(self):
        """A custom todo list should be stored."""
        from tinycua.agent.tools.context import ExecutorContext
        from tinycua.agent.tools.todo.todo_list import TodoList

        todo = TodoList()
        ctx = ExecutorContext(todo_list=todo)
        assert ctx.todo_list is todo

    def test_custom_session(self):
        """Session should be storable (for M2 compatibility)."""
        from tinycua.agent.tools.context import ExecutorContext

        # Session is just a placeholder — any object can be stored in M1
        ctx = ExecutorContext(session="placeholder")
        assert ctx.session == "placeholder"

    def test_config_field_has_default_factory(self):
        """config should use default_factory, not a shared default."""
        from tinycua.agent.tools.context import ExecutorContext

        ctx1 = ExecutorContext()
        ctx2 = ExecutorContext()
        # Each should have its own config instance
        assert ctx1.config is not ctx2.config
