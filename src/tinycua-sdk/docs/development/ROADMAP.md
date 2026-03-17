# TINYCUA SDK - Development Roadmap (TDD Order)

This document outlines future development tasks in Test-Driven Development order. Each feature should have tests written before implementation.

---

## Phase 1: Core Features (MVP)

### 1.1 Backend Integration (High Priority)
**Status**: Not Started

- [ ] Implement `_run_deployed()` method in Agent
- [ ] Create backend API client
- [ ] Test: `test_agent_run_deployed_calls_backend()`
- [ ] Test: `test_deployed_agent_uses_backend_url()`

### 1.2 Persistent Session Storage (Medium Priority)
**Status**: Not Started

- [ ] Add file-based session storage
- [ ] Test: `test_session_save_to_file()`
- [ ] Test: `test_session_load_from_file()`

---

## Phase 2: Advanced Features

### 2.1 Enhanced Memory Tools
**Status**: Local Implementation Complete

- [ ] Embeddings-based semantic search (backend required)
- [ ] Memory compaction
- [ ] Test: `test_memory_semantic_search()`
- [ ] Test: `test_memory_compaction()`

### 2.2 Agent Communication Protocol
**Status**: Not Started

- [ ] Define message protocol between agents
- [ ] Support for agent-to-agent tool sharing
- [ ] Test: `test_agent_tool_sharing()`

### 2.3 Multi-turn Conversation Context
**Status**: Not Started

- [ ] Conversation history management
- [ ] Context window optimization
- [ ] Test: `test_conversation_history_truncation()`

---

## Phase 3: Remote Execution

### 3.1 Remote Runner Server
**Status**: Not Started

- [ ] Implement HTTP server for runner
- [ ] SSE streaming endpoint
- [ ] Authentication
- [ ] Test: `test_remote_runner_server_health()`
- [ ] Test: `test_remote_runner_execute_stream()`

### 3.2 Backend API
**Status**: Not Started

- [ ] Deploy endpoint
- [ ] Session management
- [ ] Tool registry
- [ ] Test: `test_backend_deploy_agent()`
- [ ] Test: `test_backend_execute_agent()`

---

## Phase 4: Developer Experience

### 4.1 CLI Tool
**Status**: Not Started

- [ ] Interactive REPL
- [ ] Agent scaffolding
- [ ] Configuration management
- [ ] Test: `test_cli_repl_command()`

### 4.2 Visualization
**Status**: Not Started

- [ ] Agent execution trace visualization
- [ ] Tool call graph
- [ ] Token usage tracking

---

## Phase 5: Production Hardening

### 5.1 Error Handling
**Status**: Not Started

- [ ] Retry logic with exponential backoff
- [ ] Circuit breaker pattern
- [ ] Graceful degradation
- [ ] Test: `test_retry_on_failure()`

### 5.2 Security
**Status**: Not Started

- [ ] API key rotation
- [ ] Input sanitization
- [ ] Tool execution sandboxing
- [ ] Test: `test_api_key_rotation()`

---

## Testing Guidelines

When adding new features:

1. **Write failing test first** - Test should describe expected behavior
2. **Implement minimum code** - Just enough to pass the test
3. **Refactor** - Clean up while keeping tests green
4. **Add integration tests** - For end-to-end behavior
5. **Document** - Update specs and examples

### Test Markers
- `@pytest.mark.unit` - Fast, no external dependencies
- `@pytest.mark.integration` - Requires external service (LM Studio, backend)
- `@pytest.mark.lm_studio` - Requires LM Studio running
- `@pytest.mark.backend` - Requires backend server
- `@pytest.mark.remote_runner` - Requires remote runner server

---

## Running Tests

```bash
# Run all unit tests (fast)
make test

# Run with coverage
make coverage

# Run only integration tests (requires services)
pytest -m integration -v

# Run specific marker
pytest -m lm_studio -v
```

---

## Notes

- All new features should have both unit and integration tests
- Integration tests should auto-skip when services unavailable
- Maintain backward compatibility
- Document breaking changes in CHANGELOG.md
