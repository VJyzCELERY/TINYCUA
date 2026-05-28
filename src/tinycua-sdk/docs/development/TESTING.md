# Testing Guide

## Test Structure

Unit tests are located in `tests/unit/` and follow the pattern `test_<module>.py`.

```
tests/unit/
├── conftest.py           # Shared fixtures
├── test_agent.py         # Agent tests
├── test_loop.py          # BaseLoop tests
├── test_tool.py         # Tool tests
└── ...
```

## Running Tests

```bash
# Run all unit tests
pytest tests/unit/ -v

# Run with coverage
pytest tests/unit/ --cov=tinycua_sdk --cov-report=term-missing

# Run specific test file
pytest tests/unit/test_agent.py -v
```

## Test Patterns

### Naming Convention

Tests follow `test_<class>_<method>_<scenario>`:

```python
class TestAgent:
    def test_agent_initialization(self):
        ...

    def test_agent_with_tools(self):
        ...
```

### Fixtures

Shared fixtures are in `conftest.py`:

- `mock_provider` - Mocked LLM provider
- `mock_agent_config` - Agent configuration
- `temp_skill_dir` - Temporary skills directory
- `temp_memory_dir` - Temporary memory directory

### Mocking External Dependencies

Use `unittest.mock` for external calls (network, file I/O):

```python
from unittest.mock import MagicMock, patch

def test_agent_with_provider(self):
    with patch('tinycua_sdk.client.LMStudioProvider') as mock:
        mock.return_value.complete.return_value = "response"
        agent = Agent(provider=mock)
```

### Test Isolation

Each test should be independent:
- No dependencies between tests
- Use fixtures for setup/teardown
- Avoid shared state