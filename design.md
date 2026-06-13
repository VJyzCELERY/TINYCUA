# Design Document: TinyCUA CLI / Runtime Entry Point for Benchmark Tasks

**Spec**: `./spec.md`
**Status**: Draft
**Last Updated**: 2026-06-13

---

## Overview

This design adds a CLI entry point to TinyCUA that WildClawBench can invoke to run agent tasks. The CLI accepts a task prompt, timeout, workspace directory, output directory, and local model endpoint configuration. It creates a `create_tinycua_agent(...)`, runs it with the provided prompt, respects the timeout, and writes transcript/log artifacts for post-run analysis and grading.

---

## Architecture

### Component Overview

```
CLI Entry Point (tinycua/cli/entry.py)
  │
  ├── Parse arguments → RunConfig
  ├── Create workspace/output directories
  ├── Create agent via create_tinycua_agent(model_endpoint=...)
  ├── Set timeout handler (threading.Timer or signal.alarm)
  ├── Run agent: agent.run(prompt)
  ├── Collect artifacts (transcript events, logs)
  ├── Write artifacts to output directory
  │     ├── transcript.jsonl
  │     └── run_summary.json
  └── Exit with appropriate code
```

### Affected Components

| Component | Change Type | Notes |
|-----------|-------------|-------|
| `tinycua/cli/__init__.py` | New | Package init for CLI module |
| `tinycua/cli/entry.py` | New | Main CLI entry point with argument parsing |
| `tinycua/cli/config.py` | New | RunConfig and RunSummary dataclasses |
| `tinycua/cli/runner.py` | New | Agent execution with timeout and artifact collection |
| `tinycua/cli/artifacts.py` | New | Transcript JSONL and run_summary.json writing |
| `tests/unit/test_cli.py` | New | Unit tests for CLI argument parsing and config |
| `tests/unit/test_cli_runner.py` | New | Unit tests for agent runner with timeout |
| `tests/integration/test_cli_integration.py` | New | Integration tests for full CLI invocation |

---

## Data Model

### RunConfig

```python
@dataclass
class RunConfig:
    """Configuration for a TinyCUA CLI run."""
    prompt: str                          # Task prompt (required)
    timeout: int = 300                   # Timeout in seconds (default: 5 minutes)
    workspace: Path = Path("/tmp_workspace")  # Working directory
    output_dir: Path | None = None       # Output directory (default: <workspace>/results)
    model_endpoint: str | None = None    # Local model endpoint URL
    model_name: str | None = None        # Model name for the endpoint
    verbose: bool = False                # Debug output to stderr
    log_level: str = "INFO"              # Logging level

    def __post_init__(self):
        if self.output_dir is None:
            self.output_dir = self.workspace / "results"
```

### RunSummary

```python
@dataclass
class RunSummary:
    """Result of a TinyCUA CLI run."""
    status: str                          # "success", "error", "timeout", "config_error"
    elapsed_time: float                  # Seconds elapsed
    artifact_paths: dict[str, Path]      # Maps artifact name to file path
    error_message: str | None = None     # Error message if status is not "success"
    task_prompt: str                     # Original task prompt
    model_endpoint: str | None = None    # Model endpoint used

    def to_json(self) -> str:
        """Serialize to JSON for run_summary.json."""
        ...

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        ...
```

### CLI Entry Point

```python
# tinycua/cli/entry.py

import argparse
import sys
from .config import RunConfig

def main(argv: list[str] | None = None) -> int:
    """Main CLI entry point. Returns exit code."""
    parser = argparse.ArgumentParser(
        prog="tinycua",
        description="TinyCUA CLI - Run TinyCUA agent tasks"
    )
    subparsers = parser.add_subparsers(dest="command")

    # tinycua run
    run_parser = subparsers.add_parser("run", help="Run a TinyCUA agent task")
    run_parser.add_argument("--prompt", "-p", type=str, help="Task prompt")
    run_parser.add_argument("--timeout", "-t", type=int, default=300, help="Timeout in seconds")
    run_parser.add_argument("--workspace", "-w", type=Path, default=Path("/tmp_workspace"), help="Workspace directory")
    run_parser.add_argument("--output-dir", "-o", type=Path, default=None, help="Output directory")
    run_parser.add_argument("--model-endpoint", type=str, default=None, help="Local model endpoint URL")
    run_parser.add_argument("--model-name", type=str, default=None, help="Model name")
    run_parser.add_argument("--verbose", "-v", action="store_true", help="Enable debug output")
    run_parser.add_argument("--log-level", type=str, default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])

    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 3  # config_error

    if args.command == "run":
        return _run_command(args)

    return 3  # config_error

def _run_command(args: argparse.Namespace) -> int:
    """Handle 'tinycua run' command."""
    # Read prompt from stdin if not provided
    prompt = args.prompt
    if prompt is None:
        if sys.stdin.isatty():
            print("Error: --prompt is required or provide prompt via stdin", file=sys.stderr)
            return 3
        prompt = sys.stdin.read().strip()
        if not prompt:
            print("Error: Empty prompt received from stdin", file=sys.stderr)
            return 3

    config = RunConfig(
        prompt=prompt,
        timeout=args.timeout,
        workspace=args.workspace,
        output_dir=args.output_dir,
        model_endpoint=args.model_endpoint,
        model_name=args.model_name,
        verbose=args.verbose,
        log_level=args.log_level,
    )

    from .runner import run_agent
    return run_agent(config)
```

### Agent Runner

```python
# tinycua/cli/runner.py

import logging
import time
import threading
from pathlib import Path
from .config import RunConfig, RunSummary
from .artifacts import write_transcript, write_run_summary

logger = logging.getLogger(__name__)

def run_agent(config: RunConfig) -> int:
    """Run the TinyCUA agent with the given configuration. Returns exit code."""
    start_time = time.time()

    # Setup logging
    logging.basicConfig(
        level=getattr(logging, config.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

    # Create directories
    try:
        config.workspace.mkdir(parents=True, exist_ok=True)
        config.output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        logger.error("Failed to create directories: %s", e)
        _write_error_summary(config, start_time, "config_error", str(e))
        return 3

    # Create agent
    try:
        agent = _create_agent(config)
    except Exception as e:
        logger.error("Failed to create agent: %s", e)
        _write_error_summary(config, start_time, "config_error", str(e))
        return 3

    # Run with timeout
    result = {"response": None, "error": None, "timed_out": False}

    def target():
        try:
            result["response"] = agent.run(config.prompt)
        except Exception as e:
            result["error"] = e

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    thread.join(timeout=config.timeout)

    if thread.is_alive():
        result["timed_out"] = True
        logger.warning("Agent timed out after %d seconds", config.timeout)

    elapsed = time.time() - start_time

    # Handle result
    if result["timed_out"]:
        _write_timeout_summary(config, start_time, elapsed)
        return 2
    elif result["error"] is not None:
        _write_error_summary(config, start_time, "error", str(result["error"]))
        return 1
    else:
        # Success — write artifacts
        write_transcript(config.output_dir, result["response"])
        summary = RunSummary(
            status="success",
            elapsed_time=elapsed,
            artifact_paths={"transcript": config.output_dir / "transcript.jsonl"},
            task_prompt=config.prompt,
            model_endpoint=config.model_endpoint,
        )
        write_run_summary(config.output_dir, summary)
        return 0

def _create_agent(config: RunConfig):
    """Create a TinyCUA agent with the given configuration."""
    from tinycua.factory import create_tinycua_agent

    kwargs = {}
    if config.model_endpoint:
        kwargs["model_endpoint"] = config.model_endpoint
    if config.model_name:
        kwargs["model_name"] = config.model_name

    return create_tinycua_agent(**kwargs)
```

### Artifact Writer

```python
# tinycua/cli/artifacts.py

import json
from pathlib import Path
from .config import RunSummary

def write_transcript(output_dir: Path, response: str) -> Path:
    """Write transcript JSONL to output directory."""
    transcript_path = output_dir / "transcript.jsonl"
    # For now, write a simple transcript entry
    # In the future, this will consume StreamEvents from the agent run
    with open(transcript_path, "w") as f:
        entry = {
            "type": "response.completed",
            "content": response,
            "timestamp": __import__("time").time(),
        }
        f.write(json.dumps(entry) + "\n")
    return transcript_path

def write_run_summary(output_dir: Path, summary: RunSummary) -> Path:
    """Write run_summary.json to output directory."""
    summary_path = output_dir / "run_summary.json"
    with open(summary_path, "w") as f:
        json.dump(summary.to_dict(), f, indent=2)
    return summary_path
```

---

## API / Interface Contracts

### CLI Usage

```bash
# Run with explicit prompt
tinycua run --prompt "Create a Python script that prints hello world" --timeout 120

# Run with prompt from stdin
echo "Create a Python script" | tinycua run --timeout 60

# Run with custom workspace and output
tinycua run --prompt "..." --workspace /custom/workspace --output-dir /custom/output

# Run with local model endpoint
tinycua run --prompt "..." --model-endpoint http://localhost:8080/v1 --model-name llama-3

# Verbose mode
tinycua run --prompt "..." --verbose --log-level DEBUG

# Python module invocation
python -m tinycua.cli run --prompt "..."
```

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success — agent completed task |
| 1 | Agent error — agent raised an exception |
| 2 | Timeout — agent exceeded timeout |
| 3 | Configuration error — invalid arguments or missing required input |

### Error Handling

| Error Case | Exit Code | Output |
|------------|-----------|--------|
| Missing --prompt and no stdin | 3 | Error message to stderr |
| Empty prompt from stdin | 3 | Error message to stderr |
| Invalid --timeout (negative) | 3 | argparse error |
| Workspace creation fails | 3 | run_summary.json with config_error |
| Agent creation fails | 3 | run_summary.json with config_error |
| Agent raises exception | 1 | run_summary.json with error + partial transcript |
| Agent times out | 2 | run_summary.json with timeout |
| SIGINT/SIGTERM received | 130 (SIGINT) or 143 (SIGTERM) | Partial artifacts written |

---

## Implementation Phases

### Phase 1 — CLI Argument Parsing and RunConfig (required)

- [ ] Create `tinycua/cli/__init__.py`
- [ ] Create `tinycua/cli/config.py` with `RunConfig` and `RunSummary` dataclasses
- [ ] Create `tinycua/cli/entry.py` with argument parsing and `main()` function
- [ ] Add `__main__.py` for `python -m tinycua.cli` support

### Phase 2 — Agent Runner with Timeout (required)

- [ ] Create `tinycua/cli/runner.py` with `run_agent()` function
- [ ] Implement timeout handling via `threading.Thread.join(timeout=...)`
- [ ] Implement agent creation via `create_tinycua_agent()`
- [ ] Implement graceful shutdown on SIGINT/SIGTERM

### Phase 3 — Artifact Writing (required)

- [ ] Create `tinycua/cli/artifacts.py` with `write_transcript()` and `write_run_summary()`
- [ ] Implement transcript JSONL writing (simple format for now, will be enhanced in Milestone 5.4)
- [ ] Implement `run_summary.json` writing with status, elapsed_time, artifact_paths

### Phase 4 — Tests (required)

- [ ] Unit tests for CLI argument parsing
- [ ] Unit tests for RunConfig and RunSummary
- [ ] Unit tests for agent runner with mock agent
- [ ] Unit tests for timeout handling
- [ ] Unit tests for artifact writing
- [ ] Integration tests for full CLI invocation

---

## Technical Decisions

1. **Decision**: Use `threading.Thread.join(timeout=...)` for timeout rather than `signal.alarm`.
   - **Reason**: Cross-platform compatibility (works on Windows where `signal.alarm` is not available). Threading approach is more portable for a research prototype.
   - **Alternatives Considered**: `signal.alarm` — rejected for cross-platform issues. `asyncio.wait_for` — rejected because the agent run is synchronous.

2. **Decision**: Write transcript as simple JSONL with one entry for now, to be enhanced in Milestone 5.4.
   - **Reason**: Milestone 5.1 focuses on the CLI entry point. Transcript format will be finalized when WildClawBench artifact compatibility is implemented.
   - **Alternatives Considered**: Full JSONL with all StreamEvents — deferred to Milestone 5.4.

3. **Decision**: Use separate `tinycua/cli/` package rather than adding CLI code to `tinycua/__init__.py`.
   - **Reason**: Clean separation of concerns. CLI is a separate entry point that imports from the core library.
   - **Alternatives Considered**: Single-file CLI in `__init__.py` — rejected for maintainability.

4. **Decision**: Default workspace to `/tmp_workspace` (WildClawBench convention) rather than current directory.
   - **Reason**: Primary use case is WildClawBench benchmark runs where `/tmp_workspace` is the standard working directory.
   - **Alternatives Considered**: Default to `.` (current directory) — rejected because it doesn't match WildClawBench conventions.

5. **Decision**: Use `threading.Thread` with `daemon=True` for timeout rather than killing the thread.
   - **Reason**: Thread killing is not safe in Python. Daemon thread will be terminated when the main process exits, which happens after timeout handling.
   - **Alternatives Considered**: `ctypes` thread killing — rejected as unsafe and non-portable.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Threading timeout doesn't kill LLM HTTP requests | Medium | Medium | Agent thread is daemon; main process exits after timeout, killing the thread |
| Transcript format changes between Milestone 5.1 and 5.4 | High | Low | Use simple format now; Milestone 5.4 will finalize WildClawBench-compatible format |
| Agent factory creates sessions that persist after timeout | Low | Low | Session cleanup is handled by TinyCUALoop lifecycle; no durable state to clean up |
| Signal handling conflicts with threading | Low | Low | Use `signal.signal()` in main thread only; daemon thread handles cleanup |

---

## Open Questions _(optional)_

1. **Should the CLI support `--config-file` for loading RunConfig from a JSON/YAML file?**
   - **Current thinking**: Not in this milestone. Keep it simple — CLI flags are sufficient for WildClawBench.

2. **Should the CLI write stderr/stdout to separate log files?**
   - **Current thinking**: Not in this milestone. Logging via `logging` module is sufficient; file logging can be added later if needed.

---

## References

- Spec: [./spec.md](./spec.md)
- Milestone 5.1 from roadmap issue: https://github.com/VJyzCELERY/TINYCUA/issues/87
- Design docs:
  - `src/tinycua/docs/design/loops/tinycua_loop.md` — TinyCUALoop execution
  - `src/tinycua/docs/design/config/session_config.md` — Session configuration
  - `src/tinycua/docs/design/models/session.md` — Session model
- Existing implementation:
  - `tinycua/factory.py` — `create_tinycua_agent()` factory
  - `tinycua/loops/tinycua_loop.py` — TinyCUALoop with streaming support
  - `tinycua/cli/` — existing CLI directory (may need review)
