"""Integration Tests: Memory System

Tests based on memory example (13_memory_example.py)
Tests:
1. Basic memory operations (remember, recall, forget, list)
2. Custom memory backend
3. Memory with agents
4. Memory persistence
"""

import pytest
import tempfile
import os

from tinycua_sdk import Agent
from tinycua.agent.tools.memory_tools import (
    remember,
    recall,
    forget,
    list_memory,
    clear_memory,
    set_memory_backend,
)
from tinycua_sdk.tools import LocalMemoryBackend


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def temp_memory_backend():
    """Create a temporary memory backend."""
    with tempfile.TemporaryDirectory() as tmpdir:
        memory_path = os.path.join(tmpdir, "memory.json")
        backend = LocalMemoryBackend(storage_path=memory_path)
        set_memory_backend(backend)
        yield backend


@pytest.fixture
def memory_agent():
    """Create an agent with memory tools."""
    with tempfile.TemporaryDirectory() as tmpdir:
        memory_path = os.path.join(tmpdir, "memory.json")
        backend = LocalMemoryBackend(storage_path=memory_path)
        set_memory_backend(backend)
        
        yield Agent(
            name="memory-agent",
            instructions="You have memory tools to remember and recall information.",
            provider="lmstudio",
            model="qwen/qwen3.5-9b",
            base_url="http://localhost:1234",
            api_key="dummy",
            tools=[remember, recall, list_memory],
        )


# =============================================================================
# Test Cases
# =============================================================================

class TestMemoryBasics:
    """Test basic memory operations."""

    def test_remember_set_value(self, temp_memory_backend):
        """Test remembering a value."""
        result = remember.invoke(key="test_key", value="test_value")
        
        assert result["success"] == True
        assert result["key"] == "test_key"

    def test_recall_existing_key(self, temp_memory_backend):
        """Test recalling an existing key."""
        remember.invoke(key="test_key", value="test_value")
        result = recall.invoke(key="test_key")
        
        assert result["found"] == True
        assert result["value"] == "test_value"

    def test_recall_nonexistent_key(self, temp_memory_backend):
        """Test recalling a key that doesn't exist."""
        result = recall.invoke(key="nonexistent")
        
        assert result["found"] == False
        assert result["value"] is None

    def test_forget_existing_key(self, temp_memory_backend):
        """Test forgetting an existing key."""
        remember.invoke(key="test_key", value="test_value")
        result = forget.invoke(key="test_key")
        
        assert result["success"] == True

    def test_forget_nonexistent_key(self, temp_memory_backend):
        """Test forgetting a key that doesn't exist."""
        result = forget.invoke(key="nonexistent")
        
        assert result["success"] == False

    def test_list_memory(self, temp_memory_backend):
        """Test listing all memory keys."""
        remember.invoke(key="key1", value="value1")
        remember.invoke(key="key2", value="value2")
        
        result = list_memory.invoke()
        
        assert "keys" in result
        assert len(result["keys"]) == 2
        assert "key1" in result["keys"]
        assert "key2" in result["keys"]

    def test_clear_memory(self, temp_memory_backend):
        """Test clearing all memory."""
        remember.invoke(key="key1", value="value1")
        remember.invoke(key="key2", value="value2")
        
        result = clear_memory.invoke()
        
        assert result["success"] == True
        
        # Verify keys are gone
        result = list_memory.invoke()
        assert len(result["keys"]) == 0


class TestMemoryBackend:
    """Test different memory backends."""

    def test_local_backend_storage_path(self):
        """Test local backend with custom storage path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            memory_path = os.path.join(tmpdir, "test_memory.json")
            backend = LocalMemoryBackend(storage_path=memory_path)
            
            # Store a value
            backend.set("key", "value")
            
            # Verify file exists
            assert os.path.exists(memory_path)

    def test_local_backend_persistence(self):
        """Test memory persists in the file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            memory_path = os.path.join(tmpdir, "test_memory.json")
            backend = LocalMemoryBackend(storage_path=memory_path)
            
            # Store a value
            backend.set("user_name", "Alice")
            
            # Create new backend with same path
            backend2 = LocalMemoryBackend(storage_path=memory_path)
            
            # Should be able to recall
            value, found = backend2.get("user_name")
            assert found == True
            assert value == "Alice"

    def test_local_backend_delete(self):
        """Test deleting from local backend."""
        with tempfile.TemporaryDirectory() as tmpdir:
            memory_path = os.path.join(tmpdir, "test_memory.json")
            backend = LocalMemoryBackend(storage_path=memory_path)
            
            backend.set("key", "value")
            backend.delete("key")
            
            value, found = backend.get("key")
            assert found == False


class TestMemoryWithAgent:
    """Test memory operations with agents."""

    def test_agent_creation_with_memory_tools(self, temp_memory_backend):
        """Test creating agent with memory tools."""
        agent = Agent(
            name="memory-agent",
            instructions="You have memory tools.",
            provider="lmstudio",
            model="qwen/qwen3.5-9b",
            base_url="http://localhost:1234",
            api_key="dummy",
            tools=[remember, recall, list_memory],
        )
        
        # Verify memory tools are added
        tool_names = [t.name for t in agent.tools]
        assert "remember" in tool_names
        assert "recall" in tool_names
        assert "list_memory" in tool_names

    @pytest.mark.asyncio
    async def test_agent_run_simple(self, memory_agent):
        """Test agent run without memory invocation."""
        try:
            response = await memory_agent.run("Say 'hello' in one word.")
            assert isinstance(response, str)
        except Exception:
            pytest.skip("LM Studio not available")


class TestMemoryPersistence:
    """Test memory persistence scenarios."""

    def test_memory_across_invocations(self, temp_memory_backend):
        """Test memory persists across multiple invocations."""
        # First invocation - store
        remember.invoke(key="user_preference", value="dark_mode")
        
        # Second invocation - store more
        remember.invoke(key="language", value="English")
        
        # Third invocation - recall
        result = recall.invoke(key="user_preference")
        
        assert result["found"] == True
        assert result["value"] == "dark_mode"

    def test_memory_list_all_keys(self, temp_memory_backend):
        """Test listing all keys after multiple stores."""
        remember.invoke(key="key1", value="value1")
        remember.invoke(key="key2", value="value2")
        remember.invoke(key="key3", value="value3")
        
        result = list_memory.invoke()
        
        assert len(result["keys"]) == 3

    def test_memory_overwrite(self, temp_memory_backend):
        """Test overwriting an existing key."""
        remember.invoke(key="mykey", value="original")
        remember.invoke(key="mykey", value="updated")
        
        result = recall.invoke(key="mykey")
        
        assert result["value"] == "updated"


class TestMemoryEdgeCases:
    """Test memory edge cases."""

    def test_empty_value(self, temp_memory_backend):
        """Test storing empty value."""
        remember.invoke(key="empty_key", value="")
        result = recall.invoke(key="empty_key")
        
        assert result["found"] == True
        assert result["value"] == ""

    def test_special_characters(self, temp_memory_backend):
        """Test storing values with special characters."""
        special_value = "Hello, World! @#$%^&*()"
        remember.invoke(key="special", value=special_value)
        
        result = recall.invoke(key="special")
        
        assert result["value"] == special_value

    def test_long_value(self, temp_memory_backend):
        """Test storing long values."""
        long_value = "x" * 10000
        remember.invoke(key="long", value=long_value)
        
        result = recall.invoke(key="long")
        
        assert result["value"] == long_value


# =============================================================================
# Test Runner
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])