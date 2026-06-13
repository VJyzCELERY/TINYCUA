# Implementation: End-to-End TinyCUA Architecture Verification Gate

Build a standalone verification gate that proves all 12 TinyCUA architecture paths work correctly with a local LLM. This is a verification-only milestone — no source code modifications, only new test infrastructure.

## Context

- **Spec Reference**: `src/tinycua/specs/4.5-architecture-gate/spec.md`
- **Design Reference**: `src/tinycua/docs/prototype/design/4.5-architecture-gate/design.md`
- **Priority**: P1
- **Estimated Effort**: L

## Environment Pre-requisites

### Configuration

- [ ] **.env.test** — needs to be created based on `.env.test.example`; required variables:
  ```
  OPENAI_CHAT_COMPLETIONS_BASE_URL=http://localhost:1234/v1
  OPENAI_CHAT_COMPLETIONS_MODEL=qwen/qwen3.5-4b
  OPENAI_CHAT_COMPLETIONS_API_KEY=not-needed
  ```
- [x] **Environment variables** — already documented in existing `.env.example` files
- [x] **None** — no additional secrets needed

### Running Services

| Service | Required | How to Start | Health Check |
|---------|----------|--------------|--------------|
| Local LLM server | Yes | `ollama serve` or equivalent | `curl localhost:1234/v1/models` |
| [x] **None else** — no other services needed | | | |

### Data / Fixtures

- [x] **None** — no data or fixtures needed. Each path creates its own session.

### Developer Tooling

- [x] **Runtime**: Python 3.11+, uv
- [x] **Package manager**: uv
- [x] **None** — no special tooling required

---

## Success Criteria — Integration Tests (TDD First)

The verification gate IS the integration test. All tests run against the real local LLM via NodeQueue.

```python
# Test file: src/tinycua/tests/verification/test_gate.py
"""Integration tests for the architecture verification gate."""


def test_gate_all_paths_pass():
    """Verify all 12 architecture paths pass against local LLM."""
    gate = VerificationGate(config=GateConfig.from_env())
    report = gate.run_all()
    assert report.overall_status == "pass"
    assert report.passed == 12
    assert report.failed == 0


def test_gate_individual_path_execution():
    """Verify a single path can be run by name."""
    gate = VerificationGate(config=GateConfig.from_env())
    result = gate.run_path("passthrough_simple")
    assert result.status == "pass"
    assert result.duration_seconds > 0


def test_gate_report_json_output():
    """Verify JSON report is well-formed and contains all fields."""
    gate = VerificationGate(config=GateConfig.from_env())
    report = gate.run_all()
    json_output = ReportGenerator().generate_json(report)
    import json
    data = json.loads(json_output)
    assert "overall_status" in data
    assert "path_results" in data
    assert len(data["path_results"]) == 12


def test_gate_human_readable_summary():
    """Verify human-readable summary is generated."""
    gate = VerificationGate(config=GateConfig.from_env())
    report = gate.run_all()
    summary = ReportGenerator().generate_summary(report)
    assert len(summary) > 0
    assert "PASS" in summary or "FAIL" in summary


def test_gate_failure_report_includes_llm_logs():
    """Verify failed paths include full LLM interaction logs."""
    gate = VerificationGate(config=GateConfig.from_env())
    result = gate.run_path("passthrough_simple")
    # Even passing paths should have interaction logs
    assert result.llm_interactions is not None


def test_gate_timeout_handling():
    """Verify per-path timeouts are respected."""
    config = GateConfig.from_env()
    config.default_timeout_seconds = 1  # Very short timeout
    gate = VerificationGate(config=config)
    # This should timeout or pass quickly
    result = gate.run_path("passthrough_simple")
    assert result.status in ("pass", "timeout")


def test_gate_llm_unavailable_fails_gracefully():
    """Verify gate fails gracefully when LLM endpoint is unreachable."""
    config = GateConfig.from_env()
    config.local_model_config.base_url = "http://localhost:99999/v1"  # Bad endpoint
    gate = VerificationGate(config=config)
    report = gate.run_all()
    assert report.overall_status == "fail"
    assert report.failed == 12
```

### Key Test Scenarios

- [x] **All 12 paths pass**: Primary success criterion — proves complete architecture works
- [x] **Individual path execution**: Enables targeted debugging
- [x] **JSON output format**: CI integration and machine consumption
- [x] **Human-readable summary**: Developer debugging
- [x] **LLM interaction logs**: Debugging failed paths
- [x] **Timeout handling**: Prevents indefinite hangs
- [x] **LLM unavailable**: Graceful failure with clear error

## Verification Plan

### Automated Tests

- [x] Integration tests (defined above) — these must pass for implementation to be complete
- [x] Each path validates node execution, session state, and LLM interactions
- [x] Existing test suite — confirm no regressions: `cd src/tinycua && uv run pytest`

### Manual Verification

- [x] Run verification gate against local LLM and confirm all 12 paths pass
- [x] Verify JSON output is well-formed and contains all expected fields
- [x] Verify human-readable report is clear and actionable
- [x] Test failure reporting by temporarily misconfiguring a path

---

## Proposed Changes

### Verification Infrastructure

#### NEW `src/tinycua/tests/verification/__init__.py`

- **Description**: Package init for verification module
- **Dependencies**: None

#### NEW `src/tinycua/tests/verification/config.py`

- **Description**: Configuration module — reads from environment variables, constructs `LocalModelConfig` (from `tinycua.config.local_model`) for LLM endpoint, model, and API key, then wraps it in `GateConfig` with verification-specific settings (default_timeout_seconds, output_dir)
- **Dependencies**: `tinycua.config.local_model.LocalModelConfig`
- **Rationale**: Reuses existing TinyCUA config mechanism to ensure verification tests the real LLM integration path. `GateConfig` adds verification-specific fields on top of `LocalModelConfig`.

#### NEW `src/tinycua/tests/verification/paths.py`

- **Description**: Path definitions and registry — defines all 12 architecture paths with node sequences, expected outcomes, and validation criteria
- **Dependencies**: None (pure data definitions)
- **Rationale**: Declarative definitions are easier to review, modify, and extend

#### NEW `src/tinycua/tests/verification/executor.py`

- **Description**: Path execution engine — instantiates actual TinyCUA nodes and runs them through NodeQueue
- **Dependencies**: `tinycua.loops.node.NodeQueue`, `tinycua.config.local_model.LocalModelConfig`, all node classes
- **Rationale**: Uses the real execution engine to verify actual architecture, not a test harness imitation

#### NEW `src/tinycua/tests/verification/reporter.py`

- **Description**: Result collection and reporting — generates JSON and human-readable summary reports
- **Dependencies**: None (operates on result data structures)
- **Rationale**: Separates reporting from execution for clarity

#### NEW `src/tinycua/tests/verification/gate.py`

- **Description**: Main gate orchestrator — runs all paths and produces aggregate pass/fail verdict
- **Dependencies**: `executor.py`, `reporter.py`, `paths.py`, `config.py`
- **Rationale**: Single entry point for the verification gate

#### NEW `src/tinycua/tests/verification/cross_cutting.py`

- **Description**: Cross-cutting concern verification — validates propagation, dedupe, tool scoping, retry, streaming during path execution
- **Dependencies**: `executor.py`
- **Rationale**: Verifies cross-cutting concerns as part of path execution, not as separate paths

#### NEW `src/tinycua/tests/verification/test_gate.py`

- **Description**: Pytest entry point — parameterized tests that run the verification gate
- **Dependencies**: `gate.py`, `pytest`
- **Rationale**: pytest provides fixtures, parameterization, and reporting out of the box

---

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `src/tinycua/tests/verification/` | New | Verification gate test infrastructure |
| `src/tinycua/tests/verification/__init__.py` | New | Package init |
| `src/tinycua/tests/verification/gate.py` | New | Main gate orchestrator |
| `src/tinycua/tests/verification/paths.py` | New | Path definitions and registry |
| `src/tinycua/tests/verification/executor.py` | New | Path execution engine using NodeQueue |
| `src/tinycua/tests/verification/reporter.py` | New | Result collection and reporting |
| `src/tinycua/tests/verification/config.py` | New | Configuration — reads from env, constructs LocalModelConfig, wraps in GateConfig |
| `src/tinycua/tests/verification/test_gate.py` | New | Pytest entry point |
| `src/tinycua/tests/verification/cross_cutting.py` | New | Cross-cutting concern verification |

## Data Model Changes

```python
# New types for verification infrastructure

ArchitecturePath:
    name: str                          # e.g., "passthrough_simple"
    description: str                   # Human-readable description
    node_sequence: list[str]           # Ordered node IDs to execute
    expected_nodes: list[str]          # Nodes that must execute
    expected_outcome: str              # "success", "hitl", "failure"
    timeout_seconds: int               # Per-path timeout
    setup_fn: Callable | None          # Optional setup
    validation_fn: Callable | None     # Optional custom validation

PathResult:
    path_name: str                     # Name of the path
    status: str                        # "pass", "fail", "timeout", "error"
    duration_seconds: float            # Execution time
    llm_interactions: list[dict]       # Full LLM interaction log
    node_outputs: dict[str, Any]       # Output from each node
    session_state: dict                # Final session state
    error: str | None                  # Error message if failed
    error_traceback: str | None        # Full traceback if exception

VerificationReport:
    overall_status: str                # "pass" or "fail"
    total_paths: int                   # 12
    passed: int                        # Count of passing paths
    failed: int                        # Count of failing paths
    timed_out: int                     # Count of timed-out paths
    path_results: list[PathResult]     # Per-path results
    summary: str                       # Human-readable summary
    timestamp: str                     # ISO 8601 timestamp
    llm_model: str                     # Model used for verification
```

## Dependencies

### External Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| pytest | ^8.0.0 | Test runner (already in project) |

### Internal Dependencies

- [x] Depends on existing `tinycua.loops.node.NodeQueue` — the real execution engine
- [x] Depends on existing `tinycua.config.local_model.LocalModelConfig` — LLM configuration
- [x] Depends on all existing node classes (`TinyCUAQueryAnalystNode`, etc.)
- [x] Blocks nothing — this is verification-only, no downstream dependencies

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Local LLM produces inconsistent results | Medium | Run each path once initially; report variance; use deterministic temperature settings |
| LLM resource exhaustion during long test runs | Low | Sequential execution default; configurable delays between paths |
| Path timeout too aggressive for complex paths | Medium | Generous default timeouts (120s); configurable per-path overrides |
| LLM endpoint configuration varies by environment | High | Config reads from env vars with clear defaults; clear error messages |
| Verification gate itself has bugs | Medium | Gate is small, focused code; manual verification of gate logic |

---

*Generated from spec.md and design.md*
*Last updated: 2026-06-13*
