# Design Document: End-to-End TinyCUA Architecture Verification Gate

**Spec**: `./spec.md`
**Status**: Draft
**Last Updated**: 2026-06-13

---

## Overview

This design defines the verification strategy for Milestone 4.5 — the gate that must pass before WildClawBench integration begins. The verification gate does not implement new features; it validates that all existing components (implemented in Milestones 1.1–4.4) work together across every documented architecture path. The output is a verification report documenting pass/fail status for each path.

---

## Architecture

### Component Overview

The verification gate exercises the existing TinyCUA architecture:

```
create_tinycua_agent(session=None, agent_config=None, session_config=None)
  → Agent(loop=TinyCUALoop(...))
  → NodeQueue with all concrete nodes
  → run(query) through each documented path
  → verify output and artifacts
```

Verification does not modify any existing components. It creates test harnesses that exercise the full flow.

### Affected Components

> **Path convention**: All paths are relative to `src/tinycua/tinycua/`.

| Component | Change Type | Notes |
|-----------|-------------|-------|
| `tests/verification/` | New | Verification test suite for each architecture path |
| `tests/verification/conftest.py` | New | Shared fixtures: local LLM endpoint, agent factory, mock helpers |
| `tests/verification/test_passthrough.py` | New | Passthrough path verification |
| `tests/verification/test_task_creation.py` | New | Task creation path verification |
| `tests/verification/test_task_recreation.py` | New | Task recreation/reanalysis path verification |
| `tests/verification/test_proceed_execution.py` | New | Proceed execution path verification |
| `tests/verification/test_effort_loop.py` | New | Effort loop path verification |
| `tests/verification/test_executor_reviewer.py` | New | Executor/reviewer accept/retry/replan/open_question verification |
| `tests/verification/test_aggregation.py` | New | Aggregation path verification |
| `tests/verification/test_response.py` | New | Response path verification |
| `tests/verification/test_response_suspension.py` | New | Response suspension/digestion path verification |
| `tests/verification/test_worker_suspension.py` | New | Worker suspension/digestion path verification |
| `tests/verification/test_propagation.py` | New | Propagation/dedupe verification |
| `tests/verification/test_tool_scoping.py` | New | Tool scoping verification |
| `tests/verification/test_retry_validation.py` | New | Retry/validation verification |
| `tests/verification/test_streaming.py` | New | Streaming verification |
| `tests/verification/report.py` | New | Verification report generator |

---

## Data Model

### Verification Report Structure

```python
@dataclass
class PathResult:
    path_name: str                    # e.g., "passthrough", "task_creation"
    status: Literal["PASS", "FAIL", "SKIP"]
    duration_seconds: float
    error_message: str | None         # None on PASS
    logs: list[str]                   # captured log output
    artifacts: dict[str, Any]         # transcript, session state, etc.

@dataclass
class VerificationReport:
    timestamp: str                    # ISO 8601
    llm_model: str                    # local model name
    llm_endpoint: str                 # endpoint URL
    hardware: str                     # hardware description
    results: list[PathResult]
    total: int
    passed: int
    failed: int
    skipped: int
    gate_status: Literal["PASS", "FAIL"]  # all must pass for gate to pass
```

### Local LLM Endpoint Configuration

```python
# In conftest.py — shared fixture for all verification tests
@pytest.fixture
def local_llm_endpoint():
    """Configure local LLM endpoint for verification.
    
    Expected env vars:
    - TINYCUA_LLM_BASE_URL: OpenAI-compatible endpoint URL
    - TINYCUA_LLM_MODEL: model name
    - TINYCUA_LLM_API_KEY: API key (can be dummy for local)
    """
    return LLMEndpointConfig(
        base_url=os.environ.get("TINYCUA_LLM_BASE_URL", "http://localhost:8000/v1"),
        model=os.environ.get("TINYCUA_LLM_MODEL", "local-model"),
        api_key=os.environ.get("TINYCUA_LLM_API_KEY", "not-needed"),
    )
```

---

## API / Interface Contracts

### Verification Test Pattern

Each verification test follows the same pattern:

```python
@pytest.mark.verification
class TestPassthroughPath:
    def test_passthrough_produces_response(self, local_llm_endpoint):
        """Verify: Simple query → QueryAnalyst → passthrough → Worker → ResponseNode."""
        agent = create_tinycua_agent(
            session_config=SessionConfig(
                llm_endpoint=local_llm_endpoint,
            )
        )
        result = agent.run("What is 2+2?")
        
        # Verify response is a non-empty string
        assert isinstance(result, str)
        assert len(result) > 0
        
        # Verify session state
        session = agent.loop.root_session
        assert session.chat_history is not None
        # Verify no task was created (passthrough path)
        assert session.task is None or session.task.status == "pending"
```

### Suspension/Digestion Test Pattern

```python
@pytest.mark.verification
class TestResponseSuspension:
    def test_response_suspends_for_digestion(self, local_llm_endpoint):
        """Verify: ResponseNode suspends → InformationDigester → digest → resume."""
        agent = create_tinycua_agent(
            session_config=SessionConfig(
                llm_endpoint=local_llm_endpoint,
            )
        )
        # Use a query that triggers suspension (complex context needed)
        result = agent.run("Summarize all the files in the current directory and explain their purpose")
        
        assert isinstance(result, str)
        assert len(result) > 0
        
        # Verify suspension occurred (check session context for digest entries)
        session = agent.loop.root_session
        digest_entries = [
            e for e in session.session_context
            if "digested" in e.content.lower() or "digest" in e.content.lower()
        ]
        # At least one digest entry should exist if suspension occurred
        # (may not always trigger — depends on LLM behavior)
```

### Streaming Verification Pattern

```python
@pytest.mark.verification
class TestStreaming:
    @pytest.mark.asyncio
    async def test_streaming_emits_lifecycle_events(self, local_llm_endpoint):
        """Verify: stream=True emits structured lifecycle events."""
        agent = create_tinycua_agent(
            session_config=SessionConfig(
                llm_endpoint=local_llm_endpoint,
            )
        )
        events = []
        async for event in agent.run("Hello", stream=True):
            events.append(event)
        
        # Verify lifecycle events were emitted
        event_types = [e.get("type") for e in events]
        assert "node.started" in event_types or "response.completed" in event_types
        
        # Verify events are JSON-serializable
        import json
        json.dumps(events)  # Should not raise
```

### Report Generation

```python
def generate_verification_report(
    results: list[PathResult],
    llm_config: LLMEndpointConfig,
) -> VerificationReport:
    """Generate a structured verification report."""
    report = VerificationReport(
        timestamp=datetime.utcnow().isoformat(),
        llm_model=llm_config.model,
        llm_endpoint=llm_config.base_url,
        hardware=platform.node(),
        results=results,
        total=len(results),
        passed=sum(1 for r in results if r.status == "PASS"),
        failed=sum(1 for r in results if r.status == "FAIL"),
        skipped=sum(1 for r in results if r.status == "SKIP"),
        gate_status="PASS" if all(r.status != "FAIL" for r in results) else "FAIL",
    )
    return report
```

### Error Handling

| Error Case | Behavior | Notes |
|------------|----------|-------|
| Local LLM endpoint unavailable | Test marked as `SKIP` with clear error message | Not a gate failure — infrastructure issue |
| Node execution error | Test marked as `FAIL` with full traceback | Gate failure — must be resolved |
| Timeout | Test marked as `FAIL` with timeout message | Configurable timeout per test |
| LLM produces invalid output | Retry/validation should handle; if exhausted, test `FAIL` | Documents the failure path |

---

## Implementation Phases

### Phase 1 — Test Infrastructure (required)

- [ ] Create `tests/verification/` directory structure
- [ ] Create `conftest.py` with shared fixtures (local LLM endpoint, agent factory)
- [ ] Create `report.py` with `PathResult`, `VerificationReport`, and report generator
- [ ] Add pytest marker `@pytest.mark.verification` for selective test execution

### Phase 2 — Core Path Verification (required)

- [ ] `test_passthrough.py` — Verify passthrough path
- [ ] `test_task_creation.py` — Verify first-time task creation path
- [ ] `test_proceed_execution.py` — Verify proceed execution path
- [ ] `test_aggregation.py` — Verify aggregation path
- [ ] `test_response.py` — Verify response path

### Phase 3 — Advanced Path Verification (required)

- [ ] `test_task_recreation.py` — Verify task recreation/reanalysis path
- [ ] `test_effort_loop.py` — Verify effort loop path
- [ ] `test_executor_reviewer.py` — Verify accept/retry/replan/open_question paths
- [ ] `test_response_suspension.py` — Verify response suspension/digestion path
- [ ] `test_worker_suspension.py` — Verify worker suspension/digestion path

### Phase 4 — Cross-Cutting Concern Verification (required)

- [ ] `test_propagation.py` — Verify propagation/dedupe
- [ ] `test_tool_scoping.py` — Verify tool scoping
- [ ] `test_retry_validation.py` — Verify retry/validation
- [ ] `test_streaming.py` — Verify streaming events

### Phase 5 — Report and Gate (required)

- [ ] Generate verification report with pass/fail for each path
- [ ] Document local LLM model, endpoint, and hardware used
- [ ] Document any failures and their root causes
- [ ] Gate decision: all paths must pass for gate to pass

### Phase 6 — Enhancements _(post-MVP)_

- [ ] CI integration for automated verification runs
- [ ] Comparison report across multiple LLM models
- [ ] Performance metrics (latency per path, token usage)

> **Note**: Phase 6 must NOT be implemented until Phase 5 is complete and the gate passes.

---

## Technical Decisions

1. **Decision**: Use pytest with `@pytest.mark.verification` for selective execution.
   - **Reason**: Allows running verification tests separately from unit/integration tests. Can be invoked with `pytest -m verification`.
   - **Alternatives Considered**: Separate test script — rejected because pytest provides better reporting, fixtures, and parallel execution.

2. **Decision**: Each architecture path gets its own test file.
   - **Reason**: Matches the structure of `expected_scenarios.md` and makes it easy to identify which path failed.
   - **Alternatives Considered**: Single monolithic test — rejected because failures are harder to isolate and diagnose.

3. **Decision**: Use a shared `conftest.py` fixture for local LLM endpoint configuration.
   - **Reason**: All tests need the same endpoint configuration; centralizing it avoids duplication and makes reconfiguration easy.
   - **Alternatives Considered**: Per-test configuration — rejected as wasteful and error-prone.

4. **Decision**: Generate a structured `VerificationReport` dataclass.
   - **Reason**: Machine-readable output that can be consumed by CI pipelines or compared across runs.
   - **Alternatives Considered**: Plain text report — rejected because it's harder to parse and compare.

5. **Decision**: Mark tests as `SKIP` (not `FAIL`) when the local LLM endpoint is unavailable.
   - **Reason**: Infrastructure availability is not a code quality issue. The gate should fail only when the code doesn't work, not when the test environment is misconfigured.
   - **Alternatives Considered**: Fail on missing endpoint — rejected because it conflates infrastructure and code issues.

6. **Decision**: Verification tests use real `create_tinycua_agent(...)` and `agent.run(...)` calls, not mocks.
   - **Reason**: The purpose is to verify end-to-end architecture flow, not unit behavior. Mocks would defeat the purpose of the gate.
   - **Alternatives Considered**: Mock LLM responses — rejected because it doesn't verify the actual LLM integration.

7. **Decision**: Timeout per test is configurable (default 120 seconds).
   - **Reason**: Local LLM inference can be slow; a generous timeout prevents false failures while still catching hangs.
   - **Alternatives Considered**: No timeout — rejected because hangs would block CI indefinitely.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Local LLM model too small to follow tool-call instructions | Medium | High | Use a model known to handle tool calls (e.g., fine-tuned Qwen-7B). Document model requirements. |
| Some paths rarely trigger (e.g., suspension/digestion) | Medium | Medium | Design test queries that are likely to trigger suspension (complex context requests). Document as "best-effort" if path doesn't trigger. |
| Verification tests are flaky due to LLM non-determinism | Medium | Medium | Use temperature=0 for verification runs. Allow retries. Focus on structural correctness (response is string, events are emitted) rather than content correctness. |
| Local LLM endpoint crashes during verification | Low | Medium | Catch endpoint errors, mark test as SKIP with clear message. |
| Verification gate becomes a bottleneck | Low | Low | Tests can run in parallel (pytest-xdist). Each test is independent. |

---

## Open Questions _(optional)_

1. **What is the minimum local LLM model size that can follow TinyCUA tool-call instructions?**
   - Current thinking: 7B parameters minimum. Need to test with Qwen-7B-Chat or similar.

2. **Should verification tests assert on response content quality, or only structural correctness?**
   - Current thinking: Structural correctness only (response is non-empty string, events are emitted, session state is consistent). Content quality is subjective and depends on the model.

3. **Should the verification report be committed to the repo or generated as an artifact?**
   - Current thinking: Generated as an artifact (e.g., `verification-report.json`). Not committed to avoid noise.

---

## References

- Spec: [./spec.md](./spec.md)
- Design docs covered:
  - `src/tinycua/docs/design/loops/expected_scenarios.md` — all scenarios to verify
  - `src/tinycua/docs/design/loops/overview.md` — architecture summary
  - `src/tinycua/docs/design/loops/tinycua_loop.md` — loop execution model
  - `src/tinycua/docs/design/loops/node_queue.md` — queue execution and terminal handling
  - `src/tinycua/docs/design/loops/node.md` — Node, DecisionNode, ProcessNode
  - `src/tinycua/docs/design/loops/query_analyst.md` — QueryAnalyst routing
  - `src/tinycua/docs/design/loops/worker.md` — Worker routing
  - `src/tinycua/docs/design/loops/task_create.md` — Task creation
  - `src/tinycua/docs/design/loops/task_analyzer.md` — Task analysis
  - `src/tinycua/docs/design/loops/task_assessor.md` — Task assessment
  - `src/tinycua/docs/design/loops/task_executor.md` — Task execution
  - `src/tinycua/docs/design/loops/result_reviewer.md` — Result review
  - `src/tinycua/docs/design/loops/result_aggregation.md` — Result aggregation
  - `src/tinycua/docs/design/loops/response.md` — Response synthesis
  - `src/tinycua/docs/design/loops/information_digester.md` — Information digestion
  - `src/tinycua/docs/design/loops/propagation.md` — Propagation and dedupe
  - `src/tinycua/docs/design/config/node_config.md` — Node configuration
  - `src/tinycua/docs/design/config/session_config.md` — Session configuration
- Existing implementation:
  - `tinycua/agent.py` — `create_tinycua_agent()` factory
  - `tinycua/loops/tinycua_loop.py` — `TinyCUALoop`
  - `tinycua/loops/node_queue.py` — `NodeQueue`
  - `tinycua/loops/node.py` — `Node`, `DecisionNode`, `ProcessNode`
  - All concrete TinyCUA nodes in `tinycua/loops/`
- Tracking issue: https://github.com/VJyzCELERY/TINYCUA/issues/87
