# Design Document: End-to-End TinyCUA Architecture Verification Gate

**Spec**: [./spec.md](./spec.md)
**Status**: Draft
**Last Updated**: 2026-06-13

---

## Overview

This design defines how to verify that the full TinyCUA target architecture flow works end-to-end across all 11 documented paths before WildClawBench benchmark integration begins. The verification gate is implemented as a comprehensive test suite that exercises `create_tinycua_agent(...).run(...)` against a local LLM endpoint, with explicit pass/fail criteria for each architecture path. No new architecture components are introduced — this milestone validates existing implementations from Milestones 1.1–4.4.

---

## Architecture

### Component Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Verification Gate                         │
│                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐   │
│  │  Test Suite   │───▶│  Agent Run   │───▶│  Assertions  │   │
│  │  (11 paths)   │    │  (local LLM) │    │  (per path)  │   │
│  └──────────────┘    └──────────────┘    └──────────────┘   │
│         │                    │                    │          │
│         ▼                    ▼                    ▼          │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐   │
│  │  Local LLM   │    │  TinyCUA     │    │  Gate Report │   │
│  │  Endpoint    │    │  Node Flow   │    │  (pass/fail) │   │
│  └──────────────┘    └──────────────┘    └──────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### Affected Components

> **Path convention**: All paths are relative to the `tinycua` subproject root (`src/tinycua/`).

| Component | Change Type | Notes |
|-----------|-------------|-------|
| `tests/verification/` | New | Verification gate test directory |
| `tests/verification/conftest.py` | New | Shared fixtures: local LLM config, agent factory, assertion helpers |
| `tests/verification/test_passthrough.py` | New | Passthrough path verification |
| `tests/verification/test_task_creation.py` | New | Task creation path verification |
| `tests/verification/test_task_recreation.py` | New | Task recreation path verification |
| `tests/verification/test_task_reanalysis.py` | New | Task reanalysis path verification |
| `tests/verification/test_proceed_execution.py` | New | Proceed execution path verification |
| `tests/verification/test_effort_loop.py` | New | Effort loop path verification |
| `tests/verification/test_retry.py` | New | Executor/reviewer retry path verification |
| `tests/verification/test_replan.py` | New | Executor/reviewer replan path verification |
| `tests/verification/test_open_question.py` | New | Open question path verification |
| `tests/verification/test_aggregation.py` | New | Aggregation path verification |
| `tests/verification/test_response.py` | New | Response path verification |
| `tests/verification/test_response_digestion.py` | New | Response suspension/digestion path verification |
| `tests/verification/test_worker_digestion.py` | New | Worker suspension/digestion path verification |
| `tests/verification/test_propagation.py` | New | Propagation/dedupe verification |
| `tests/verification/test_tool_scoping_flow.py` | New | Full tool scoping flow verification |
| `tests/verification/test_streaming.py` | New | Streaming lifecycle verification |
| `tests/verification/gate_report.py` | New | Gate criteria evaluation and report generation |

---

## Data Model

### Gate Criteria

Each architecture path has a gate criteria definition:

```python
@dataclass
class PathGateCriteria:
    path_name: str                    # e.g., "passthrough"
    description: str                  # Human-readable description
    required: bool = True             # Must pass for gate to open
    test_file: str = ""               # Test module that verifies this path
    status: str = "pending"           # pending | passed | failed | skipped

@dataclass
class GateReport:
    milestone: str = "4.5"
    total_paths: int = 11
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    gate_open: bool = False           # True only if all required paths pass
    paths: list[PathGateCriteria] = field(default_factory=list)
    timestamp: str = ""
    local_llm_endpoint: str = ""
    model_name: str = ""
```

### Verification Path Definitions

| # | Path Name | Test File | Description |
|---|-----------|-----------|-------------|
| 1 | passthrough | `test_passthrough.py` | QueryAnalyst → ResponseNode (no Worker) |
| 2 | task_creation | `test_task_creation.py` | Worker → TaskCreate → Analyzer → Executor → Reviewer → Aggregation → Response |
| 3 | task_recreation | `test_task_recreation.py` | Worker → TaskAnalyzer(task_recreation) with TaskInit/TaskCreate |
| 4 | task_reanalysis | `test_task_reanalysis.py` | Worker → TaskAnalyzer(task_reanalysis) without TaskInit/TaskCreate |
| 5 | proceed_execution | `test_proceed_execution.py` | Worker → TaskExecutor continuation |
| 6 | effort_loop | `test_effort_loop.py` | TaskAssessor + TaskAnalyzer repeated passes before TaskExecutor |
| 7 | retry | `test_retry.py` | TaskExecutor failure → retry → acceptance |
| 8 | replan | `test_replan.py` | ResultReviewer → TaskAnalyzer local replan |
| 9 | open_question | `test_open_question.py` | ResultReviewer → ResultReviewer deterministic route |
| 10 | aggregation | `test_aggregation.py` | Task tree BFS traversal → consolidated context |
| 11 | response_digestion | `test_response_digestion.py` | ResponseNode → InformationDigester → ResponseNode resume |

Additional cross-cutting verifications (tested within the above paths):

| # | Cross-Cutting Concern | Verified In |
|---|----------------------|-------------|
| 12 | Worker digestion | `test_worker_digestion.py` |
| 13 | Propagation/dedupe | `test_propagation.py` |
| 14 | Tool scoping flow | `test_tool_scoping_flow.py` |
| 15 | Streaming | `test_streaming.py` |

---

## API / Interface Contracts

### Test Fixture: Local LLM Configuration

```python
@pytest.fixture
def local_llm_config():
    """
    Configure TinyCUA to use a local OpenAI-compatible endpoint.
    Reads from environment variables:
      - TINYCUA_LLM_BASE_URL (default: http://localhost:8000/v1)
      - TINYCUA_LLM_MODEL (default: local-model)
    """
    return SessionConfig(
        model_endpoint=os.environ.get("TINYCUA_LLM_BASE_URL", "http://localhost:8000/v1"),
        model_name=os.environ.get("TINYCUA_LLM_MODEL", "local-model"),
    )
```

### Test Fixture: Agent Factory

```python
@pytest.fixture
def create_agent(local_llm_config):
    """Factory fixture that creates a configured TinyCUA agent."""
    def _create(session=None, **kwargs):
        return create_tinycua_agent(
            session=session,
            session_config=local_llm_config,
            **kwargs,
        )
    return _create
```

### Test Fixture: Path Assertion Helpers

```python
@pytest.fixture
def assert_path():
    """
    Assert that specific nodes were visited during agent execution.
    Uses transcript/log inspection or mock tracking.
    """
    def _assert(transcript, expected_nodes: list[str]):
        visited = [event.node_name for event in transcript.events if event.type == "node_enter"]
        for node in expected_nodes:
            assert node in visited, f"Expected node '{node}' in path, got: {visited}"
    return _assert
```

### Gate Report Generation

```python
def generate_gate_report(results: dict[str, bool], config: dict) -> GateReport:
    """
    Generate a gate report from test results.
    Returns a GateReport with pass/fail status for each path.
    Gate is open only if all required paths pass.
    """
    report = GateReport(
        local_llm_endpoint=config["base_url"],
        model_name=config["model_name"],
        timestamp=datetime.now().isoformat(),
    )
    for path_name, passed in results.items():
        criteria = PathGateCriteria(
            path_name=path_name,
            status="passed" if passed else "failed",
        )
        report.paths.append(criteria)
        if passed:
            report.passed += 1
        else:
            report.failed += 1
    report.gate_open = report.failed == 0
    return report
```

---

## Implementation Phases

### Phase 1 — Test Infrastructure (required)

- [ ] Create `tests/verification/` directory structure
- [ ] Implement `conftest.py` with local LLM config fixture, agent factory fixture, and assertion helpers
- [ ] Implement `gate_report.py` with `GateReport` and `PathGateCriteria` dataclasses
- [ ] Configure test markers: `@pytest.mark.verification` for all gate tests

### Phase 2 — Core Path Verification (required)

- [ ] Implement `test_passthrough.py` — verify QueryAnalyst → ResponseNode without Worker
- [ ] Implement `test_task_creation.py` — verify full task creation flow
- [ ] Implement `test_task_recreation.py` — verify TaskAnalyzer(task_recreation) with TaskInit/TaskCreate
- [ ] Implement `test_task_reanalysis.py` — verify TaskAnalyzer(task_reanalysis) without TaskInit/TaskCreate
- [ ] Implement `test_proceed_execution.py` — verify continuation on pending task

### Phase 3 — Advanced Path Verification (required)

- [ ] Implement `test_effort_loop.py` — verify effort-controlled assessment/analysis passes
- [ ] Implement `test_retry.py` — verify retry with assistant-role continuations
- [ ] Implement `test_replan.py` — verify local replanning through TaskAnalyzer
- [ ] Implement `test_open_question.py` — verify deterministic open_question routing

### Phase 4 — Cross-Cutting Verification (required)

- [ ] Implement `test_aggregation.py` — verify BFS traversal and context consolidation
- [ ] Implement `test_response.py` — verify final response synthesis
- [ ] Implement `test_response_digestion.py` — verify ResponseNode → InformationDigester suspension
- [ ] Implement `test_worker_digestion.py` — verify InformationDigester before Worker
- [ ] Implement `test_propagation.py` — verify chat_history/session_context separation and dedupe
- [ ] Implement `test_tool_scoping_flow.py` — verify per-node tool visibility end-to-end
- [ ] Implement `test_streaming.py` — verify lifecycle events and final output

### Phase 5 — Gate Report and CI (required)

- [ ] Implement gate report generation in `gate_report.py`
- [ ] Create `Makefile` target or script to run all verification tests and produce gate report
- [ ] Document local LLM setup instructions for developers running verification
- [ ] Verify all 15 test modules pass against local LLM

---

## Technical Decisions

1. **Decision**: Use real local LLM for primary verification, not mock LLM.
   - **Reason**: The gate verifies the full stack including LLM interaction. Mock LLM tests are useful for unit tests but cannot validate the actual agent flow.
   - **Alternatives Considered**: Mock LLM — rejected because it doesn't test the real integration path. Can be added as a fast-fallback option later.

2. **Decision**: One test file per architecture path.
   - **Reason**: Clear traceability between roadmap paths and test files. Easy to identify which path failed. Allows running individual path verifications.
   - **Alternatives Considered**: Single monolithic test file — rejected because it makes failure isolation difficult.

3. **Decision**: Gate report as a structured data object, not just pytest output.
   - **Reason**: Provides a machine-readable pass/fail summary that can be checked in CI or used to block Milestone 5 PRs.
   - **Alternatives Considered**: Relying solely on pytest exit code — rejected because it doesn't distinguish between individual path failures.

4. **Decision**: Cross-cutting concerns (propagation, tool scoping, streaming) verified within path tests, not as separate isolated tests.
   - **Reason**: These concerns manifest during actual path execution. Isolated tests would not catch integration issues.
   - **Alternatives Considered**: Separate isolated tests — rejected because they don't verify the real interaction patterns.

5. **Decision**: Environment-variable-based LLM configuration.
   - **Reason**: Developers can point verification at any local endpoint without code changes. Supports vLLM, Ollama, LM Studio, and other OpenAI-compatible servers.
   - **Alternatives Considered**: Hardcoded endpoint — rejected because it limits developer flexibility.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Local LLM too slow for CI verification runs | High | Medium | Allow longer timeouts; document hardware recommendations; provide skip mechanism for fast iteration |
| Local LLM insufficient capability for complex paths | Medium | High | Document minimum model requirements; test with multiple models; provide fallback mock-LLM path |
| Verification tests are flaky due to LLM non-determinism | Medium | Medium | Use temperature=0; add retry logic to tests; assert on structural outcomes not exact text |
| Gate blocks development due to pre-existing bugs | Low | High | Run verification against current branch state; fix bugs before marking gate as passed |
| Test fixtures become outdated as architecture evolves | Low | Medium | Gate tests reference design docs; update fixtures when architecture changes |

---

## Open Questions _(optional)_

1. **Should the gate report be committed to the repo or generated fresh each time?**
   - Current thinking: Generated fresh. The report is an artifact of the verification run, not a source-of-truth document.

2. **Should verification tests be part of the regular CI pipeline or run separately?**
   - Current thinking: Run separately with a dedicated `make verify-gate` target. Regular CI runs faster unit/integration tests; gate verification is a heavier, less frequent check.

3. **What happens if a path fails due to a bug in a prior milestone's implementation?**
   - Current thinking: The gate correctly identifies the failure. The fix should go into the appropriate milestone's branch, not this one. This branch only adds verification tests.

---

## References

- Spec: [./spec.md](./spec.md)
- Roadmap issue: https://github.com/VJyzCELERY/TINYCUA/issues/87 (Milestone 4.5)
- Design docs covered:
  - `docs/design/loops/overview.md` — full architecture flow
  - `docs/design/loops/tinycua_loop.md` — loop behavior
  - `docs/design/loops/node_queue.md` — queue mechanics
  - `docs/design/loops/query_analyst.md` — passthrough/worker routing
  - `docs/design/loops/worker.md` — worker decision routing
  - `docs/design/loops/task_create.md` — root task creation
  - `docs/design/loops/task_analyzer.md` — analysis modes
  - `docs/design/loops/task_assessor.md` — effort loop selection
  - `docs/design/loops/task_executor.md` — ReAct execution
  - `docs/design/loops/result_reviewer.md` — accept/retry/replan/open_question
  - `docs/design/loops/result_aggregation.md` — BFS consolidation
  - `docs/design/loops/response.md` — final synthesis and digestion suspension
  - `docs/design/loops/information_digester.md` — context gathering
  - `docs/design/loops/propagation.md` — context propagation and dedupe
  - `docs/design/config/node_config.md` — tool/retry/stream policies
  - `docs/design/constants/tools.md` — per-node tool scopes
