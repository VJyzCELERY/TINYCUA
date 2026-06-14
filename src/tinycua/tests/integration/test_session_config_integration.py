"""Integration tests for SessionConfig, Node Config, and Local Model Config."""

import pytest


def test_node_config_with_all_policies():
    """Test NodeConfigBase construction with all policy types and their defaults."""
    from tinycua.config.node_config import (
        NodeConfigBase,
        NodeMessagePolicy,
        NodeToolPolicy,
        NodeStreamPolicy,
        NodeRetryPolicy,
    )

    # Arrange & Act
    config = NodeConfigBase(
        custom_instruction_append="Custom instruction",
        custom_continuation_append="Custom continuation",
        custom_retry_append="Custom retry",
        tool_policy=NodeToolPolicy(
            include_agent_tools="selected", allowed_agent_tool_names=["web_search"]
        ),
        stream_policy=NodeStreamPolicy(visible_to_user=False),
        retry_policy=NodeRetryPolicy(max_attempts=5),
        message_policy=NodeMessagePolicy(include_chat_history=True),
    )

    # Assert
    assert config.custom_instruction_append == "Custom instruction"
    assert config.custom_continuation_append == "Custom continuation"
    assert config.custom_retry_append == "Custom retry"
    assert config.tool_policy.include_agent_tools == "selected"
    assert config.tool_policy.allowed_agent_tool_names == ["web_search"]
    assert config.stream_policy.visible_to_user is False
    assert config.retry_policy.max_attempts == 5
    assert config.message_policy.include_chat_history is True


def test_tool_policy_resolution():
    """Test NodeToolPolicy tool resolution with allow/deny precedence."""
    from tinycua.config.node_config import NodeToolPolicy

    # Arrange
    policy = NodeToolPolicy(
        include_agent_tools="selected",
        allowed_agent_tool_names=["web_search", "calculator"],
        denied_agent_tool_names=["web_search"],
    )

    # Create mock outer tools
    class MockTool:
        def __init__(self, name):
            self.name = name

    outer_tools = [MockTool("web_search"), MockTool("calculator"), MockTool("other")]

    # Act
    result = policy.resolve_tools(outer_agent_tools=outer_tools)
    result_names = [t.name for t in result]

    # Assert - deny wins over allow
    assert "web_search" not in result_names  # denied, even though allowed
    assert "calculator" in result_names  # allowed, not denied
    assert "other" not in result_names  # not in allowed list


def test_system_prompt_builder():
    """Test SystemPromptBuilder fragment ordering and build output."""
    from tinycua.config.system_prompt import SystemPromptBuilder

    # Arrange
    builder = SystemPromptBuilder()
    builder.add_static("Static prompt")
    builder.add_configurable_append("Configurable prompt")
    builder.add_dynamic_context("Dynamic context")

    # Act
    result = builder.build()

    # Assert
    assert result["role"] == "system"
    assert "Static prompt" in result["content"]
    assert "Configurable prompt" in result["content"]
    assert "Dynamic context" in result["content"]


def test_todo_lifecycle():
    """Test Todo append, mark_done, next_pending, and max_items limit."""
    from tinycua.models.todo import Todo

    # Arrange
    todo = Todo(max_items=3)

    # Act & Assert - Append items
    todo.append("Task 1")
    todo.append("Task 2")
    todo.append("Task 3")

    # Test max_items limit
    with pytest.raises(ValueError):
        todo.append("Task 4")

    # Test next_pending
    item = todo.next_pending()
    assert item is not None
    assert item.description == "Task 1"
    assert item.status == "pending"
    assert item.order == 0  # first append -> index 0

    # Test mark_done
    todo.mark_done(0)
    item = todo.next_pending()
    assert item.description == "Task 2"
    assert item.order == 1  # second append -> index 1

    # Test mark_done with invalid index
    with pytest.raises(IndexError):
        todo.mark_done(99)


def test_local_model_config():
    """Test LocalModelConfig construction and defaults."""
    from tinycua.config.local_model import LocalModelConfig

    # Arrange & Act
    config = LocalModelConfig(
        base_url="http://localhost:11434/v1",
        model="llama3",
    )

    # Assert
    assert config.base_url == "http://localhost:11434/v1"
    assert config.model == "llama3"
    assert config.api_key is None
    assert config.timeout == 30.0
    assert config.temperature == 0.7
    assert config.max_tokens is None
