# Design Document: WildClawBench TinyCUA BaseAgent Adapter

**Spec**: [./spec.md](./spec.md)
**Status**: Draft
**Last Updated**: 2026-06-14

---

## Overview

This design implements a WildClawBench-compatible BaseAgent adapter for TinyCUA, enabling TinyCUA to participate in WildClawBench benchmark evaluation. The adapter wraps TinyCUA's agent factory and execution flow to conform to WildClawBench's `BaseAgent` interface while preserving TinyCUA's internal architecture.

---

## Architecture

### Component Overview

```
WildClawBench Runner
        |
        v
TinyCUAAgent (BaseAgent adapter)
        |
        v
create_tinycua_agent(...) (existing factory)
        |
        v
Agent(loop=TinyCUALoop(...)) (existing SDK integration)
        |
        v
TinyCUA Node Execution Flow (existing architecture)
```

### Affected Components

| Component | Change Type | Notes |
|-----------|-------------|-------|
| `src/tinycua/adapters/wildclawbench.py` | New | Main adapter class implementing BaseAgent |
| `src/tinycua/adapters/__init__.py` | New | Package init for adapters module |
| `src/tinycua/config/wildclawbench.py` | New | Configuration for WildClawBench integration |

---

## Data Model

### New Entities

```python
# WildClawBench BaseAgent interface (conceptual)
class BaseAgent:
    expects_gateway: bool
    transcript_container_path: str
    
    def run_task(spec: AgentTaskSpec) -> AgentExecution
    def collect_usage(task_id: str, output_dir: str, elapsed_time: float) -> dict
    def prepare_grading_transcript(...) -> None  # optional

# TinyCUA adapter (conceptual)
class TinyCUAAgent(BaseAgent):
    expects_gateway = False
    transcript_container_path = "/tmp_workspace/transcript.jsonl"
    
    def __init__(self, model_endpoint: str, model_name: str):
        # Configure TinyCUA with local model endpoint
        pass
    
    def run_task(self, spec: AgentTaskSpec) -> AgentExecution:
        # Execute task using TinyCUA architecture flow
        pass
    
    def collect_usage(self, task_id: str, output_dir: str, elapsed_time: float) -> dict:
        # Collect usage statistics from TinyCUA execution
        pass
```

### Schema Changes

- No changes to existing TinyCUA data models.
- Adapter creates mapping between WildClawBench `AgentTaskSpec` and TinyCUA input formats.
- Adapter maps TinyCUA execution results to WildClawBench `AgentExecution` format.

---

## API / Interface Contracts

### New / Modified Endpoints or Functions

```python
class TinyCUAAgent(BaseAgent):
    """
    WildClawBench-compatible adapter for TinyCUA agent harness.
    
    Wraps TinyCUA's agent factory and execution flow to conform to
    WildClawBench's BaseAgent interface while preserving TinyCUA's
    internal architecture.
    """
    
    def __init__(
        self,
        model_endpoint: str = "http://localhost:8000/v1",
        model_name: str = "local-model",
        workspace_path: str = "/tmp_workspace",
        timeout: int = 300
    ):
        """
        Initialize the TinyCUA adapter with local model configuration.
        
        Args:
            model_endpoint: OpenAI-compatible endpoint for local model
            model_name: Model name to use for TinyCUA execution
            workspace_path: Working directory for task execution
            timeout: Default timeout for task execution
        """
    
    @property
    def expects_gateway(self) -> bool:
        """Returns False - TinyCUA uses local model endpoints."""
        return False
    
    @property
    def transcript_container_path(self) -> str:
        """Returns path for transcript file storage."""
        return f"{self.workspace_path}/transcript.jsonl"
    
    def run_task(self, spec: AgentTaskSpec) -> AgentExecution:
        """
        Execute a WildClawBench task using TinyCUA architecture flow.
        
        Args:
            spec: WildClawBench task specification
            
        Returns:
            AgentExecution with status, transcript path, and output directory
        """
    
    def collect_usage(
        self,
        task_id: str,
        output_dir: str,
        elapsed_time: float
    ) -> dict:
        """
        Collect usage statistics from task execution.
        
        Args:
            task_id: Identifier for the completed task
            output_dir: Directory containing task outputs
            elapsed_time: Total execution time in seconds
            
        Returns:
            Dictionary with request count, tokens, and cost information
        """
    
    def prepare_grading_transcript(
        self,
        transcript_path: str,
        output_path: str
    ) -> None:
        """
        Prepare transcript for WildClawBench grading.
        
        Args:
            transcript_path: Path to raw TinyCUA transcript
            output_path: Path to write grading-compatible transcript
        """
```

### Error Handling

| Error Case | Exception / Response | Notes |
|------------|---------------------|-------|
| Invalid task specification | `ValueError("Invalid task specification")` | Validate input before execution |
| Model endpoint unreachable | `AgentExecution(status="failed", error="...")` | Return failed execution status |
| Task timeout | `AgentExecution(status="timeout", error="...")` | Terminate and return timeout status |
| Tool unavailability | Continue with available tools | Document limitations in transcript |
| Workspace not writable | `PermissionError("Cannot write to workspace")` | Check workspace permissions |

---

## Implementation Phases

### Phase 1 — MVP _(required for initial release)_

- [ ] Create `src/tinycua/adapters/` package structure
- [ ] Implement `TinyCUAAgent` class with BaseAgent interface
- [ ] Implement `run_task(spec)` using TinyCUA agent factory
- [ ] Implement `collect_usage(...)` with basic usage tracking
- [ ] Implement `expects_gateway` and `transcript_container_path` properties
- [ ] Add configuration for local model endpoint
- [ ] Add workspace directory handling (`/tmp_workspace`)
- [ ] Add basic error handling and timeout support
- [ ] Write unit tests for adapter class
- [ ] Write integration tests for task execution flow

### Phase 2 — Enhancements _(post-MVP, only if spec explicitly includes it)_

- [ ] Implement `prepare_grading_transcript(...)` for transcript format compatibility
- [ ] Add detailed usage tracking (tokens, cost estimation)
- [ ] Add transcript event recording for debugging
- [ ] Add configuration validation and diagnostics

> **Note**: Phase 2 must NOT be implemented until Phase 1 is complete and reviewed.

---

## Technical Decisions

Document key decisions and the reasoning behind them:

1. **Decision**: Implement adapter as a separate module (`src/tinycua/adapters/`) rather than modifying existing code.
   - **Reason**: Keeps WildClawBench integration isolated from core TinyCUA architecture, allowing easier maintenance and future changes.
   - **Alternatives Considered**: Modifying existing agent factory — rejected because it would mix concerns and complicate the core architecture.

2. **Decision**: Use local model endpoint configuration instead of gateway dependency.
   - **Reason**: WildClawBench evaluation should use local models for fair comparison with other harnesses.
   - **Alternatives Considered**: Using OpenRouter — rejected per project constraints.

3. **Decision**: Preserve TinyCUA architecture flow within adapter.
   - **Reason**: Ensures adapter tests the real TinyCUA architecture, not a simplified version.
   - **Alternatives Considered**: Creating a simplified execution path — rejected because it wouldn't validate the full architecture.

4. **Decision**: Write transcripts to `/tmp_workspace/transcript.jsonl` by default.
   - **Reason**: Follows WildClawBench conventions for transcript storage location.
   - **Alternatives Considered**: Using TinyCUA's default transcript location — rejected because it doesn't match WildClawBench expectations.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| WildClawBench BaseAgent interface changes | Low | Medium | Pin to specific WildClawBench version, document interface assumptions |
| Local model endpoint performance | High | Medium | Add timeout handling, document performance characteristics |
| Transcript format incompatibility | Medium | High | Implement format validation, add fallback transcript generation |
| Tool availability gaps | Medium | Medium | Document available tools, handle missing tools gracefully |
| Workspace permission issues | Low | Medium | Add workspace validation, provide clear error messages |

---

## Open Questions _(optional)_

1. **Exact WildClawBench BaseAgent interface requirements**
   - Need to inspect `src/agents/base.py` in WildClawBench repository for exact method signatures and return types.

2. **Transcript format specifications**
   - Need to understand WildClawBench transcript loader expectations for grading compatibility.

3. **Tool mapping between TinyCUA and WildClawBench tasks**
   - Need to identify which TinyCUA tools are required for WildClawBench task categories.

4. **Usage dictionary format**
   - Need to understand exact format expected by WildClawBench for usage reporting.

---

## References

- Spec: `./spec.md` — relative path from this design.md to its spec.md
- WildClawBench GitHub: `https://github.com/InternLM/WildClawBench`
- WildClawBench Paper: `https://arxiv.org/abs/2605.10912`
- WildClawBench Dataset: `https://huggingface.co/datasets/internlm/WildClawBench`
- TinyCUA Design Docs: `src/tinycua/docs/design/`
- Tracking Issue: `https://github.com/VJyzCELERY/TINYCUA/issues/87`
