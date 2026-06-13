# Design Document: WildClawBench TinyCUA BaseAgent Adapter

**Spec**: [./spec.md](./spec.md)
**Status**: Draft
**Last Updated**: 2026-06-14

---

## Overview

This design implements a `TinyCUAAgent` adapter that implements WildClawBench's `BaseAgent` interface, allowing TinyCUA to be selected as an agent backend for benchmark task execution. The adapter spawns the existing `tinycua run` CLI as a subprocess, handles timeout enforcement, collects usage data, and manages transcript paths. This is the bridge between WildClawBench's task orchestration and TinyCUA's agent execution.

---

## Architecture

### Component Overview

```
WildClawBench run_batch.py
  │
  ├── constructs AgentTaskSpec(task_id, prompt, workspace, output_dir, timeout, model)
  ├── agent = TinyCUAAgent(model_config=...)
  ├── execution = agent.run_task(spec)
  │     │
  │     ├── ensures output_dir exists
  │     ├── builds CLI command: tinycua run <prompt> --timeout <t> --output-dir <d> --workspace <w> --model <m>
  │     ├── spawns subprocess with Popen()
  │     ├── monitors for timeout via threading.Timer or poll()
  │     ├── on timeout: kills subprocess, sets error
  │     ├── on completion: captures elapsed_time
  │     └── returns AgentExecution(elapsed_time, error)
  │
  ├── usage = agent.collect_usage(task_id, output_dir, elapsed_time)
  │     ├── reads agent.log or transcript.jsonl for request/token counts
  │     └── returns {"requests": int, "total_tokens": int|None, "cost": float}
  │
  └── transcript_path = agent.prepare_grading_transcript(task_id)
        └── returns transcript_container_path
```

### Affected Components

| Component | Change Type | Notes |
|-----------|-------------|-------|
| `tinycua/wildclawbench/__init__.py` | New | Package init |
| `tinycua/wildclawbench/agent.py` | New | `TinyCUAAgent` class implementing `BaseAgent` |
| `tinycua/wildclawbench/base_agent.py` | New | Local copy of WildClawBench `BaseAgent` ABC (avoids WildClawBench dependency) |
| `tests/unit/test_wildclawbench_agent.py` | New | Unit tests for adapter |
| `tests/integration/test_wildclawbench_integration.py` | New | Integration test with mock task spec |

---

## Data Model

### Local BaseAgent Copy

To avoid a hard dependency on WildClawBench (which may not be installed in the TinyCUA development environment), we include a local copy of the `BaseAgent` ABC and its associated dataclasses:

```python
# tinycua/wildclawbench/base_agent.py

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
import subprocess
from typing import Any


@dataclass(frozen=True)
class AgentTaskSpec:
    task_id: str
    task: dict[str, Any]  # WildClawBench task metadata (type, category, etc.) — not used by adapter, logged for debugging
    workspace_path: str
    prompt: str
    timeout_seconds: int
    output_dir: Path
    model: str
    thinking: str | None = None
    models_config: dict[str, Any] | None = None
    lobster: dict[str, Any] | None = None


@dataclass
class AgentExecution:
    elapsed_time: float
    error: str | None = None
    gateway_proc: subprocess.Popen[str] | None = None
    agent_proc: subprocess.Popen[str] | None = None


class BaseAgent(ABC):
    @property
    @abstractmethod
    def expects_gateway(self) -> bool:
        """Whether this backend starts a long-running gateway process."""

    @property
    @abstractmethod
    def transcript_container_path(self) -> str:
        """Path to chat transcript inside the runtime container."""

    def prepare_grading_transcript(self, task_id: str) -> str:
        _ = task_id
        return self.transcript_container_path

    @abstractmethod
    def run_task(self, spec: AgentTaskSpec) -> AgentExecution:
        """Execute a task and return process handles, timing and error state."""

    @abstractmethod
    def collect_usage(self, task_id: str, output_dir: Path, elapsed_time: float) -> dict[str, Any]:
        """Collect token usage and cost for one task."""
```

### TinyCUAAgent

```python
# tinycua/wildclawbench/agent.py

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from tinycua.wildclawbench.base_agent import (
    AgentExecution,
    AgentTaskSpec,
    BaseAgent,
)

logger = logging.getLogger(__name__)


class TinyCUAAgent(BaseAgent):
    """WildClawBench adapter for TinyCUA agents.

    Wraps the `tinycua run` CLI as a subprocess to execute benchmark tasks
    with process-level isolation, matching the execution model of other
    WildClawBench backends.
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        tinycua_bin: str = "tinycua",
    ) -> None:
        """Initialize TinyCUAAgent adapter.

        Args:
            base_url: Override for TINYCUA_BASE_URL env var.
            api_key: Override for TINYCUA_API_KEY env var.
            model: Override for TINYCUA_MODEL env var (default: from env or "llama3").
            tinycua_bin: Path or name of the tinycua CLI binary.
        """
        self._base_url = base_url
        self._api_key = api_key
        self._model = model
        self._tinycua_bin = tinycua_bin

    @property
    def expects_gateway(self) -> bool:
        return False

    @property
    def transcript_container_path(self) -> str:
        return "/tmp_workspace/results/transcript.jsonl"

    def prepare_grading_transcript(self, task_id: str) -> str:
        return self.transcript_container_path

    def run_task(self, spec: AgentTaskSpec) -> AgentExecution:
        """Execute a benchmark task via tinycua run subprocess.

        Spawns `tinycua run` with the task prompt, workspace, output directory,
        timeout, and model configuration. Monitors for timeout and returns
        timing/error state.
        """
        output_dir = Path(spec.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        workspace = Path(spec.workspace_path)
        workspace.mkdir(parents=True, exist_ok=True)

        # Build CLI command
        cmd = [
            self._tinycua_bin,
            "run",
            spec.prompt,
            "--timeout", str(spec.timeout_seconds),
            "--output-dir", str(output_dir),
            "--workspace", str(workspace),
            "--model", spec.model,
        ]
        if self._base_url:
            cmd.extend(["--base-url", self._base_url])
        if self._api_key:
            cmd.extend(["--api-key", self._api_key])

        # Set environment for the subprocess
        env = os.environ.copy()
        if self._base_url:
            env["TINYCUA_BASE_URL"] = self._base_url
        if self._api_key:
            env["TINYCUA_API_KEY"] = self._api_key
        if spec.model:
            env["TINYCUA_MODEL"] = spec.model

        start_time = time.monotonic()
        error = None

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(workspace),
                env=env,
                text=True,
            )

            try:
                _, stderr = proc.communicate(timeout=spec.timeout_seconds)
                elapsed = time.monotonic() - start_time

                if proc.returncode != 0 and proc.returncode != 124:
                    error = f"tinycua exited with code {proc.returncode}: {stderr.strip()}"
                elif proc.returncode == 124:
                    error = f"tinycua timed out after {spec.timeout_seconds}s"
            except subprocess.TimeoutExpired:
                elapsed = time.monotonic() - start_time
                proc.kill()
                proc.wait()
                error = f"tinycua timed out after {spec.timeout_seconds}s"

        except FileNotFoundError:
            elapsed = time.monotonic() - start_time
            error = f"tinycua binary not found: {self._tinycua_bin}"
        except Exception as e:
            elapsed = time.monotonic() - start_time
            error = f"Failed to run tinycua: {e}"

        return AgentExecution(
            elapsed_time=elapsed,
            error=error,
        )

    def collect_usage(
        self,
        task_id: str,
        output_dir: Path,
        elapsed_time: float,
    ) -> dict[str, Any]:
        """Collect usage data from the completed task.

        Reads the transcript.jsonl file for request counts and token usage.
        Returns a dict with requests, total_tokens, and cost keys.
        """
        transcript_path = Path(output_dir) / "transcript.jsonl"

        requests_count = 0
        total_tokens: int | None = None

        if transcript_path.exists():
            try:
                import json

                with open(transcript_path) as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        event = json.loads(line)
                        event_type = event.get("type", "")
                        if "llm" in event_type or "response" in event_type:
                            requests_count += 1
                        # Try to extract token usage from usage fields
                        usage = event.get("usage", {})
                        if "total_tokens" in usage:
                            if total_tokens is None:
                                total_tokens = 0
                            total_tokens += usage["total_tokens"]
            except Exception as e:
                logger.warning("Failed to parse transcript for usage: %s", e)

        return {
            "requests": requests_count,
            "total_tokens": total_tokens,
            "cost": 0.0,  # Local model — no cost
        }
```

---

## API / Interface Contracts

### Constructor

```python
TinyCUAAgent(
    base_url: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
    tinycua_bin: str = "tinycua",
)
```

### run_task

```python
def run_task(self, spec: AgentTaskSpec) -> AgentExecution:
    """
    Spawns: tinycua run <prompt> --timeout <t> --output-dir <d> --workspace <w> --model <m>
    Returns: AgentExecution(elapsed_time, error)
    """
```

### collect_usage

```python
def collect_usage(self, task_id: str, output_dir: Path, elapsed_time: float) -> dict[str, Any]:
    """
    Returns: {"requests": int, "total_tokens": int | None, "cost": float}
    """
```

### Error Handling

| Error Case | Exception / Response | Notes |
|------------|---------------------|-------|
| tinycua binary not found | `AgentExecution(error="tinycua binary not found: ...")` | Non-fatal — WildClawBench logs the error |
| tinycua returns non-zero exit | `AgentExecution(error="tinycua exited with code ...")` | Include stderr in error message |
| tinycua times out | `AgentExecution(error="tinycua timed out after ...")` | Process killed, elapsed_time set |
| Output dir not writable | `AgentExecution(error="Failed to run tinycua: ...")` | Caught by generic exception handler |
| Transcript file missing | Usage returns zeroed values | Graceful degradation |

---

## Implementation Phases

Implementation tracking is maintained in `task.md`. The phases defined there (TDD → Implementation → Testing → Verification → Documentation → Review) serve as the single source of truth for implementation progress.

> **Note**: Phase 3 must NOT be implemented until Phase 2 is complete and reviewed.

---

## Technical Decisions

1. **Decision**: Use subprocess (`tinycua run`) instead of calling `create_tinycua_agent()` directly.
   - **Reason**: WildClawBench expects process-level isolation. The CLI already handles timeout, workspace setup, output directory creation, and transcript writing. This matches how other WildClawBench backends work (they spawn agent processes).
   - **Alternatives Considered**: In-process agent creation — rejected because it doesn't provide process isolation and would require reimplementing timeout/workspace/transcript logic.

2. **Decision**: Include a local copy of `BaseAgent` ABC rather than importing from WildClawBench.
   - **Reason**: WildClawBench may not be installed in the TinyCUA development environment. A local copy avoids a hard dependency while maintaining interface compatibility. The local copy is identical to WildClawBench's `src/agents/base.py`.
   - **Alternatives Considered**: WildClawBench as a dependency — rejected because it pulls in WildClawBench's full dependency tree and creates a circular dependency risk.

3. **Decision**: Use `subprocess.Popen` with `communicate(timeout=...)` for timeout enforcement.
   - **Reason**: Simple, cross-platform, and sufficient for prototype scope. The CLI already has internal timeout handling, so this is a secondary safety net.
   - **Alternatives Considered**: `asyncio.create_subprocess_exec` — rejected because `run_task()` is synchronous per the `BaseAgent` interface.

4. **Decision**: Parse transcript JSONL for usage data rather than requiring a separate usage output format.
   - **Reason**: The transcript already contains LLM call events with optional `usage` fields. Parsing it avoids adding a new output format. For local models where token counts may not be available, the adapter returns `None` for `total_tokens` and `0.0` for `cost`.
   - **Alternatives Considered**: Separate usage JSON file — rejected because it adds complexity and the transcript already has the data.

5. **Decision**: `transcript_container_path` returns `/tmp_workspace/results/transcript.jsonl`.
    - **Reason**: WildClawBench tasks run in Docker with `/tmp_workspace` as the standard workspace. The transcript is written to the results subdirectory by the existing CLI. This path is used by `prepare_grading_transcript()` and is the Docker-container-relative path that WildClawBench uses to locate the transcript.
    - **Relationship to `collect_usage()`**: `collect_usage()` receives `output_dir` as a parameter and reads from `output_dir / "transcript.jsonl"` — this is the local filesystem path where the CLI writes the transcript. In the WildClawBench Docker context, `output_dir` maps to the container path, so both paths resolve to the same file. Locally, `collect_usage()` uses the local `output_dir` directly, which is correct.
    - **Alternatives Considered**: Configurable path — deferred to post-MVP; the default path works for all standard WildClawBench tasks.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| WildClawBench `BaseAgent` interface changes | Low | Medium | Local copy is easy to update; pin to known version |
| `tinycua run` CLI output format changes break usage parsing | Medium | Low | Usage parsing is best-effort; returns zeroed values on failure |
| Subprocess timeout doesn't kill child processes cleanly | Low | Medium | Use `proc.kill()` + `proc.wait()`; monitor for zombie processes |
| Local model endpoint unreachable from subprocess | Medium | High | Subprocess inherits env vars; error captured and returned in `AgentExecution` |
| WildClawBench transcript loader expects specific JSONL schema | Medium | Medium | Design events to match common JSONL format; test with actual WildClawBench loader |

---

## Open Questions _(optional)_

1. **Should the adapter support `thinking` and `lobster` fields from `AgentTaskSpec`?**
   - Current thinking: Log them as unsupported for now. Add support when TinyCUA supports thinking/reasoning modes.

2. **Should `collect_usage()` also parse `agent.log` for additional metrics?**
   - Current thinking: Start with transcript-only parsing. Add log parsing in Phase 3 if needed.

---

## References

- Spec: [./spec.md](./spec.md)
- WildClawBench BaseAgent: `https://github.com/InternLM/WildClawBench/blob/main/src/agents/base.py`
- Issue: https://github.com/VJyzCELERY/TINYCUA/issues/87 (Milestone 5.2)
- Existing CLI: `src/tinycua/tinycua/cli/run.py` — `run_command()` function
- Existing factory: `src/tinycua/tinycua/factory.py` — `create_tinycua_agent()`
- Existing config: `src/tinycua/tinycua/cli/config.py` — `load_config()`
