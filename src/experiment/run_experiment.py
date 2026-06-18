"""Run one prompt across the experiment agent harnesses."""

from __future__ import annotations

import argparse
import json
import queue
import shutil
import subprocess
import sys
import threading
import time
from datetime import UTC, datetime
from pathlib import Path


AGENTS = ("opencode", "hermes", "openclaw", "tinycua")

# Per-agent marker indicating the first LLM call has started.
# Lines matching this substring mark the end of "warmup" (container setup,
# dependency installation, tool loading) and the start of agent runtime.
WARMUP_DONE_MARKERS: dict[str, str] = {
    "opencode": '"type":"step_start"',
    "hermes": "Starting conversation",
    "openclaw": "[model-fetch] start",
    "tinycua": "[query_analyst] start",
}


def load_prompt(prompt: str | None, prompt_file: Path | None) -> str:
    """Load and validate the prompt text."""
    if bool(prompt) == bool(prompt_file):
        msg = "provide exactly one prompt source"
        raise ValueError(msg)
    text = prompt if prompt is not None else prompt_file.read_text().rstrip("\n")
    if not text.strip():
        msg = "prompt must not be empty"
        raise ValueError(msg)
    return text


def prepare_result_dirs(
    output_root: Path,
    experiment_num: int,
    *,
    overwrite: bool,
) -> dict[str, dict[str, Path]]:
    """Create result directories per agent with workdir/ and logs/ subdirs.

    Returns:
        Dict mapping agent name to {"workdir": Path, "logs": Path}.
    """
    result_dirs = {
        agent: output_root / agent / f"experiment-{experiment_num}" for agent in AGENTS
    }
    existing = [p for p in result_dirs.values() if p.exists()]
    if existing and not overwrite:
        msg = f"output exists; rerun with --overwrite: {existing[0]}"
        raise FileExistsError(msg)
    paths = {}
    for agent, result_dir in result_dirs.items():
        if result_dir.exists():
            shutil.rmtree(result_dir)
        workdir = result_dir / "workdir"
        logs = result_dir / "logs"
        workdir.mkdir(parents=True)
        logs.mkdir()
        paths[agent] = {"workdir": workdir, "logs": logs}
    return paths


def build_metadata(
    experiment_num: int,
    agent: str,
    started_at: datetime,
    ended_at: datetime,
    exit_code: int,
    llm_started_at: datetime | None = None,
) -> dict[str, object]:
    """Build JSON-safe run metadata.

    Args:
        llm_started_at: When the first LLM call was made (warmup ends).
            None if no marker was seen — duration falls back to full runtime.
    """
    warmup_seconds: float | None
    duration_seconds: float
    if llm_started_at is not None:
        warmup_seconds = round((llm_started_at - started_at).total_seconds(), 6)
        duration_seconds = round((ended_at - llm_started_at).total_seconds(), 6)
    else:
        warmup_seconds = None
        duration_seconds = round((ended_at - started_at).total_seconds(), 6)
    return {
        "experiment_num": experiment_num,
        "agent": agent,
        "started_at": started_at.isoformat(),
        "llm_started_at": llm_started_at.isoformat() if llm_started_at else None,
        "ended_at": ended_at.isoformat(),
        "warmup_seconds": warmup_seconds,
        "duration_seconds": duration_seconds,
        "exit_code": exit_code,
        "status": "passed" if exit_code == 0 else "failed",
    }


def read_timeout_seconds(env_file: Path = Path(".env"), default: int = 3600) -> int:
    """Read runner timeout from .env without adding dependencies."""
    if not env_file.exists():
        return default
    for raw_line in env_file.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() == "EXPERIMENT_TIMEOUT_SECONDS":
            return int(value.strip())
    return default


def _write_metadata(
    result_dir: Path,
    experiment_num: int,
    agent: str,
    started: datetime,
    exit_code: int,
    llm_started: datetime | None = None,
) -> dict[str, object]:
    """Write run metadata and return it."""
    metadata = build_metadata(
        experiment_num, agent, started, datetime.now(UTC), exit_code, llm_started
    )
    (result_dir / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    return metadata


def _format_stream_line(line: str) -> str:
    """Collapse opencode JSON events to one-line summaries; pass through other output."""
    stripped = line.strip()
    if not stripped:
        return line
    try:
        event = json.loads(stripped)
    except json.JSONDecodeError:
        return line  # Not JSON — hermes/openclaw/tinycua human-readable output
    part = event.get("part", {})
    etype = event.get("type", "unknown")
    if etype == "text":
        return f"  | {part.get('text', '')}\n"
    if etype == "reasoning":
        text = part.get("text", "").replace("\n", " ")[:120]
        return f"  ~ {text}\n"
    if etype == "step_start":
        return "  > step\n"
    if etype == "step_finish":
        return "  < step done\n"
    # Unknown JSON event (tool_call, etc.) — show type label
    label = part.get("name") or part.get("type") or etype
    return f"  . {label}\n"


def run_agent(
    agent: str,
    experiment_num: int,
    prompt: str,
    workdir: Path,
    logs_dir: Path,
    timeout_seconds: int,
) -> int:
    """Run one Docker Compose service and write its artifacts."""
    print(f"[{agent}] starting experiment-{experiment_num}", flush=True)
    (logs_dir / "prompt.txt").write_text(prompt)
    env_file = Path(".env")
    if env_file.exists():
        (logs_dir / "container.env").write_text(env_file.read_text())
    container_workspace = f"/workspace/experiment-{experiment_num}"
    command = [
        "docker",
        "compose",
        "run",
        "--rm",
        "-T",
        "-e",
        f"EXPERIMENT_NUM={experiment_num}",
        "-e",
        f"EXPERIMENT_PROMPT={prompt}",
        "-e",
        f"EXPERIMENT_WORKSPACE={container_workspace}",
        "-v",
        f"{workdir.resolve()}:{container_workspace}",
        "--workdir",
        container_workspace,
        agent,
    ]
    started = datetime.now(UTC)
    llm_started: datetime | None = None
    warmup_marker = WARMUP_DONE_MARKERS.get(agent, "")
    stdout_path = logs_dir / "stdout.log"
    stderr_path = logs_dir / "stderr.log"
    try:
        with stdout_path.open("w") as stdout, stderr_path.open("w") as stderr:
            process = subprocess.Popen(
                command,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
            )
            # Both streams enqueued with a source tag so the main loop can
            # print them live (stdout formatted, stderr raw) and write raw to logs.
            # Use readline() — `for line in` uses a read-ahead buffer that blocks
            # until 8KB fills, even when complete lines are available.
            line_queue: queue.Queue[tuple[str, str] | None] = queue.Queue()

            def enqueue(stream, source: str) -> None:
                while True:
                    line = stream.readline()
                    if not line:
                        line_queue.put((source, None))  # EOF sentinel
                        break
                    line_queue.put((source, line))

            stdout_thread = threading.Thread(
                target=enqueue, args=(process.stdout, "out"), daemon=True
            )
            stderr_thread = threading.Thread(
                target=enqueue, args=(process.stderr, "err"), daemon=True
            )
            stdout_thread.start()
            stderr_thread.start()

            deadline = time.monotonic() + timeout_seconds
            exit_code: int | None = None
            last_output = time.monotonic()
            saw_eof = {"out": False, "err": False}
            try:
                while True:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        process.kill()
                        process.wait()
                        stderr.write(f"\nTimed out after {timeout_seconds} seconds\n")
                        exit_code = 124
                        break
                    try:
                        item = line_queue.get(timeout=min(remaining, 1.0))
                    except queue.Empty:
                        silent = time.monotonic() - last_output
                        if silent >= 15:
                            print(f"[{agent}] … ({silent:.0f}s)", flush=True)
                            last_output = time.monotonic()
                        continue
                    source, line = item
                    if line is None:  # EOF for this stream
                        saw_eof[source] = True
                        if all(saw_eof.values()):
                            exit_code = process.wait()
                            break
                        continue
                    last_output = time.monotonic()
                    # Detect first LLM call to start the runtime timer
                    if llm_started is None and warmup_marker and warmup_marker in line:
                        llm_started = datetime.now(UTC)
                        warmup = (llm_started - started).total_seconds()
                        print(f"[{agent}] ⚡ LLM call started (warmup {warmup:.1f}s)", flush=True)
                    if source == "out":
                        stdout.write(line)
                        stdout.flush()
                        print(f"[{agent}] {_format_stream_line(line)}", end="", flush=True)
                    else:
                        stderr.write(line)
                        stderr.flush()
                        print(f"[{agent}] [err] {line}", end="", flush=True)
            except KeyboardInterrupt:
                process.kill()
                process.wait()
                stderr.write("\nInterrupted by user\n")
                _write_metadata(logs_dir, experiment_num, agent, started, 130, llm_started)
                print(f"[{agent}] interrupted exit_code=130", flush=True)
                raise
    except FileNotFoundError as error:
        exit_code = 127
        stdout_path.write_text("")
        stderr_path.write_text(f"{error}\n")

    metadata = _write_metadata(logs_dir, experiment_num, agent, started, exit_code, llm_started)
    warmup_str = f" warmup={metadata['warmup_seconds']:.1f}s" if metadata['warmup_seconds'] else ""
    print(
        f"[{agent}] {metadata['status']} exit_code={exit_code} "
        f"duration={metadata['duration_seconds']:.1f}s{warmup_str}",
        flush=True,
    )
    return exit_code


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--num", type=int, required=True, help="Experiment number.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--prompt", help="Prompt text to send to every harness.")
    source.add_argument("--prompt-file", type=Path, help="File containing prompt text.")
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("results"),
        help="Host-visible result root (default: ./results).",
    )
    parser.add_argument("--overwrite", action="store_true", help="Replace result dirs.")
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=None,
        help="Runner timeout per harness (default: EXPERIMENT_TIMEOUT_SECONDS or 3600).",
    )
    args = parser.parse_args(argv)
    if args.num < 1:
        parser.error("--num must be positive")
    if args.timeout_seconds is not None and args.timeout_seconds < 1:
        parser.error("--timeout-seconds must be positive")
    return args


def main(argv: list[str] | None = None) -> int:
    """Run the experiment."""
    args = parse_args(argv)
    try:
        prompt = load_prompt(args.prompt, args.prompt_file)
        output_root = (
            args.output_root
            if args.output_root.is_absolute()
            else Path.cwd() / args.output_root
        )
        paths = prepare_result_dirs(output_root, args.num, overwrite=args.overwrite)
        timeout_seconds = args.timeout_seconds or read_timeout_seconds()
    except (OSError, ValueError) as error:
        print(error, file=sys.stderr)
        return 2

    try:
        exit_codes = []
        for i, agent in enumerate(AGENTS, 1):
            print(f"\n=== Agent {i}/{len(AGENTS)}: {agent} ===", flush=True)
            exit_codes.append(
                run_agent(
                    agent,
                    args.num,
                    prompt,
                    paths[agent]["workdir"],
                    paths[agent]["logs"],
                    timeout_seconds,
                )
            )
    except KeyboardInterrupt:
        return 130
    print(
        "summary: "
        + ", ".join(
            f"{agent}={'passed' if code == 0 else 'failed'}"
            for agent, code in zip(AGENTS, exit_codes, strict=True)
        ),
        flush=True,
    )
    return 1 if any(exit_codes) else 0


if __name__ == "__main__":
    raise SystemExit(main())
