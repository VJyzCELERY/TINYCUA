# Integration Tests for TINYCUA SDK

This directory contains comprehensive integration tests for the TINYCUA SDK, based on the examples provided in the `examples/` directory.

## Test Structure

### Test Files

1. **test_all.py** - Comprehensive test suite covering all major SDK functionality
2. **test_01_basic_agent.py** - Tests based on `01_agent_basic.py` example
3. **test_02_streaming.py** - Tests based on `02_agent_streaming.py` example
4. **test_03_memory_session.py** - Tests based on `03_memory_and_session.py` example
5. **test_05_agent_hierarchy.py** - Tests based on `05_agent_hierarchy.py` example
6. **test_06_local_storage.py** - Tests based on `06_local_storage.py` example

## Prerequisites

- **LM Studio** running at `http://localhost:1234`
- Model: `qwen/qwen3.5-9b` loaded in LM Studio
- Python 3.10+
- Test dependencies (installed via `pip install pytest pytest-asyncio`)

## Running Tests

### Run All Tests

```bash
python tests/run_integration_tests.py
```

### Run Specific Test File

```bash
pytest tests/integration/test_01_basic_agent.py -v
```

### Run Tests with Coverage

```bash
pytest tests/integration/ --cov=tinycua_sdk --cov-report=html
```

### Run Tests in Parallel

```bash
pytest tests/integration/ -n auto -v
```

## Test Coverage

### Basic Agent Functionality (test_01_basic_agent.py)
- Agent creation with tools
- Direct mode execution
- Tool call detection and execution
- Plan mode execution
- Streaming (text and with tools)
- Trace functionality
- Deployment functionality

### Agent Streaming (test_02_streaming.py)
- Text-only streaming
- Streaming with single tool call
- Streaming with multiple tool calls
- DONE event handling

### Memory and Sessions (test_03_memory_session.py)
- Memory tools (remember, recall, list_memory)
- Memory streaming
- Cancel execution
- Session persistence
- Custom memory backend

### Agent Hierarchy (test_05_agent_hierarchy.py)
- Agent hierarchy structure
- Manual delegation
- Context passing
- Result aggregation

### Local Storage (test_06_local_storage.py)
- Session store creation
- Message management
- Context retrieval tools
- Search functionality

## Test Fixtures

### Basic Fixtures
- `basic_agent`: Creates a basic agent with no tools
- `agent_with_tools`: Creates an agent with calculator tool
- `streaming_agent`: Creates an agent with weather and calculator tools
- `hierarchical_agents`: Creates a hierarchy of agents

### Memory Fixtures
- `memory_agent`: Creates an agent with memory tools
- `temp_memory_backend`: Creates a temporary memory backend

### Storage Fixtures
- `temp_store`: Creates a temporary session store

## Expected Results

### Passing Tests
All tests should pass if:
- LM Studio is running at `http://localhost:1234`
- The model `qwen/qwen3.5-9b` is loaded in LM Studio
- All SDK dependencies are installed

### Failing Tests
Some tests may skip if:
- LM Studio is not running (streaming tests)
- Backend is not available (deployment tests)
- Network issues prevent API calls

## Debugging Tests

### Enable Verbose Logging
```bash
pytest tests/integration/ -v -s --log-cli-level=DEBUG
```

### Debug Specific Test
```bash
pytest tests/integration/test_01_basic_agent.py::TestAgentCreation::test_agent_creation -v -s
```

### View Test Output
```bash
pytest tests/integration/ -v --tb=short --capture=no
```

## Continuous Integration

The tests can be integrated into CI/CD pipelines:

```yaml
# Example GitHub Actions workflow
- name: Run Integration Tests
  run: |
    # Start LM Studio (if needed)
    # Run tests
    python tests/run_integration_tests.py
```

## Contributing

To add new tests:

1. Create a new test file in `tests/integration/` following the naming convention
2. Add test classes and methods covering the functionality
3. Use appropriate fixtures for setup
4. Run tests locally before committing
5. Update this README with new test coverage

## Troubleshooting

### Tests Fail to Connect to LM Studio
- Ensure LM Studio is running
- Check that the model is loaded
- Verify the API URL is correct (`http://localhost:1234`)

### Tests Timeout
- Increase timeout in `conftest.py`
- Check network connectivity
- Verify LM Studio is not overloaded

### Tests Skip Unexpectedly
- Review skip conditions in test code
- Check if prerequisites are met
- Verify environment variables are set

## License

Tests are provided under the same license as the TINYCUA SDK.
