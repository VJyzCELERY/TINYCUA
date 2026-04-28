# TINYCUA SDK - Automated Integration Test Suite

## Overview

This document describes the automated integration test suite created for the TINYCUA SDK, based on the examples provided in the `examples/` directory.

## Test Suite Structure

### Location
```
src/tinycua-sdk/tests/integration/
```

### Test Files

| File | Example | Coverage |
|------|---------|----------|
| `test_all.py` | All examples | Comprehensive test suite |
| `test_01_basic_agent.py` | `01_agent_basic.py` | Basic agent functionality |
| `test_02_streaming.py` | `02_agent_streaming.py` | Streaming functionality |
| `test_03_memory_session.py` | `03_memory_and_session.py` | Memory and session tools |
| `test_05_agent_hierarchy.py` | `05_agent_hierarchy.py` | Agent hierarchy |
| `test_06_local_storage.py` | `06_local_storage.py` | Local storage and context |

## Test Coverage by Example

### Example 1: Basic Agent (`01_agent_basic.py`)
**Tests:**
- Agent creation with tools
- Direct mode execution (simple completion)
- Tool call detection and execution
- Plan mode execution
- Trace functionality
- Deployment functionality
- Text-only streaming
- Streaming with tool execution

**Key Test Methods:**
- `test_agent_creation()`
- `test_direct_mode_simple()`
- `test_tool_call_detection()`
- `test_tool_execution()`
- `test_react_loop()`
- `test_text_streaming()`
- `test_stream_with_tools()`
- `test_trace_functionality()`

### Example 2: Agent Streaming (`02_agent_streaming.py`)
**Tests:**
- Text-only streaming
- Streaming with tool calls
- Streaming with multiple tool calls
- DONE event handling

**Key Test Methods:**
- `test_text_only_streaming()`
- `test_text_only_streaming_done_event()`
- `test_stream_with_single_tool()`
- `test_stream_with_tool_done_event()`
- `test_stream_multiple_tools()`
- `test_stream_multiple_tools_done()`

### Example 3: Memory and Session (`03_memory_and_session.py`)
**Tests:**
- Memory tools (remember, recall, list_memory)
- Memory streaming
- Cancel execution
- Session persistence (create, save, load, list, delete)
- Custom memory backend

**Key Test Methods:**
- `test_remember_tool()`
- `test_recall_tool()`
- `test_list_memory_tool()`
- `test_stream_with_memory_tool()`
- `test_cancel_agent()`
- `test_create_session()`
- `test_save_and_load_session()`
- `test_list_sessions()`
- `test_delete_session()`
- `test_custom_backend()`

### Example 5: Agent Hierarchy (`05_agent_hierarchy.py`)
**Tests:**
- Agent hierarchy structure
- Manual delegation
- Context passing
- Result aggregation
- Agent configuration

**Key Test Methods:**
- `test_create_sub_agents()`
- `test_main_agent_has_sub_agents()`
- `test_sub_agent_names()`
- `test_pass_context_to_sub_agent()`
- `test_aggregate_results()`
- `test_agent_with_sub_agents()`
- `test_agent_without_sub_agents()`

### Example 6: Local Storage (`06_local_storage.py`)
**Tests:**
- Session store creation
- Table creation
- Session creation
- Message management
- Context retrieval tools
- Grep search functionality
- Full context update
- Summary update

**Key Test Methods:**
- `test_create_store()`
- `test_create_tables()`
- `test_create_session()`
- `test_add_message()`
- `test_get_context_summary_tool()`
- `test_get_recent_turns_tool()`
- `test_search_context_grep_tool()`
- `test_search_context_grep_tool_empty()`
- `test_update_full_context()`
- `test_update_summary()`

## Test Fixtures

### Agent Fixtures
- `basic_agent`: Basic agent with no tools
- `agent_with_tools`: Agent with calculator tool
- `streaming_agent`: Agent with weather and calculator tools
- `hierarchical_agents`: Hierarchy of researcher, coder, writer agents

### Memory Fixtures
- `memory_agent`: Agent with memory tools (remember, recall, list_memory)
- `temp_memory_backend`: Temporary memory backend using temp directory

### Storage Fixtures
- `temp_store`: Temporary session store with SQLite database

## Test Runner

### Run All Tests
```bash
cd src/tinycua-sdk
python tests/run_integration_tests.py
```

### Run Specific Test
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

## Prerequisites

### Required Services
- **OpenAI-compatible endpoint** running at `http://localhost:1234/v1`

- Model: `qwen/qwen3.5-9b` loaded
### Python Dependencies
```bash
pip install pytest pytest-asyncio
```

## Test Configuration

### Environment Variables
```bash
export TINYCUA_PROVIDER=openai-compatible
export TINYCUA_MODEL=qwen/qwen3.5-9b
export TINYCUA_BASE_URL=http://localhost:1234/v1
export TINYCUA_API_KEY=dummy
```

### Fixtures Configuration
- All tests use async fixtures for proper test isolation
- Memory backend is reset between tests
- Temporary databases are cleaned up automatically

## Test Results

### Expected Results
- **Passing**: All tests pass if OpenAI-compatible endpoint is running with the correct model

- **Failing**: Tests will fail if OpenAI-compatible endpoint is not running or model is not loaded

### Test Output
```
============================= test session starts ==============================
collected X items

tests/integration/test_01_basic_agent.py::TestAgentCreation::test_agent_creation PASSED [ 1/7]
tests/integration/test_01_basic_agent.py::TestDirectMode::test_direct_mode_simple PASSED [ 2/7]
...

============================== X passed in Y.YYs ==============================
```

## Continuous Integration

### GitHub Actions Example
```yaml
name: Integration Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install pytest pytest-asyncio
      - run: python tests/run_integration_tests.py
```

## Maintenance

### Adding New Tests
1. Create a new test file following the naming convention
2. Add test classes and methods
3. Use appropriate fixtures
4. Update this README with new coverage

### Updating Existing Tests
1. Modify test methods to cover new functionality
2. Update fixtures if needed
3. Run tests to verify changes
4. Update this README

### Adding New Examples
1. Create example in `examples/` directory
2. Create corresponding test file in `tests/integration/`
3. Add test methods for each feature
4. Update this README

## License

Tests are provided under the same license as the TINYCUA SDK.
