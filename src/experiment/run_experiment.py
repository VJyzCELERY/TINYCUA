"""Run one prompt across the experiment agent harnesses."""

from __future__ import annotations

import argparse
import json
import os
import queue
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
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

# Harnesses that can exit 0 despite producing no user-facing response.
# When this sentinel appears in stdout, the run is treated as failed.
_NO_RESPONSE_SENTINELS: dict[str, str] = {
    "openclaw": "Agent couldn't generate a response",
}

HERMES_PROCESS_POLL_TIMEOUT_ENV = "EXPERIMENT_HERMES_PROCESS_POLL_TIMEOUT_SECONDS"
HERMES_PROCESS_POLL_STARTED_RE = re.compile(
    r"Tool call:\s*process\s+with args:.*\"action\"\s*:\s*\"poll\""
)
HARNESS_ARTIFACTS: dict[str, set[str]] = {
    "openclaw": {
        ".openclaw",
        "AGENTS.md",
        "BOOTSTRAP.md",
        "HEARTBEAT.md",
        "IDENTITY.md",
        "SOUL.md",
        "TOOLS.md",
        "USER.md",
    },
    "tinycua": {".tinycua_context_cache", "tmp", "venv", ".venv", "__pycache__"},
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


def parse_agents(raw: str | None) -> tuple[str, ...]:
    """Parse a comma-separated agent list."""
    if raw is None:
        return AGENTS
    agents = tuple(agent.strip() for agent in raw.split(",") if agent.strip())
    if not agents:
        msg = "agents must not be empty"
        raise ValueError(msg)
    unknown = [agent for agent in agents if agent not in AGENTS]
    if unknown:
        msg = f"unknown agent(s): {', '.join(unknown)}"
        raise ValueError(msg)
    if len(set(agents)) != len(agents):
        msg = "duplicate agents are not allowed"
        raise ValueError(msg)
    return agents


def prepare_result_dirs(
    output_root: Path,
    experiment_num: int,
    *,
    overwrite: bool,
    agents: tuple[str, ...] = AGENTS,
) -> dict[str, dict[str, Path]]:
    """Create result directories per agent with workdir/ and logs/ subdirs.

    Returns:
        Dict mapping agent name to {"workdir": Path, "logs": Path}.
    """
    result_dirs = {
        agent: output_root / agent / f"experiment-{experiment_num}" for agent in agents
    }
    existing = [p for p in result_dirs.values() if p.exists()]
    if existing and not overwrite:
        msg = f"output exists; rerun with --overwrite: {existing[0]}"
        raise FileExistsError(msg)
    paths = {}
    for agent, result_dir in result_dirs.items():
        if result_dir.exists():
            shutil.rmtree(result_dir, ignore_errors=True)
        workdir = result_dir / "workdir"
        logs = result_dir / "logs"
        workdir.mkdir(parents=True, exist_ok=True)
        logs.mkdir(exist_ok=True)
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


def read_int_env(key: str, env_file: Path = Path(".env"), default: int = 0) -> int:
    """Read an integer value from .env without adding dependencies."""
    if not env_file.exists():
        return default
    for raw_line in env_file.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        found_key, value = line.split("=", 1)
        if found_key.strip() == key:
            return int(value.strip())
    return default


def read_str_env(key: str, env_file: Path = Path(".env"), default: str = "") -> str:
    """Read a string value from .env without adding dependencies.

    Sibling to ``read_int_env`` — same line-splitting pattern, returns ``str``.
    Used for ``EXPERIMENT_LLM_BASE_URL``, ``EXPERIMENT_LLM_MODEL``, and the
    optional ``EXPERIMENT_TINYCUA_MAX_CONTEXT`` manual override.
    """
    if not env_file.exists():
        return default
    for raw_line in env_file.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        found_key, value = line.split("=", 1)
        if found_key.strip() == key:
            return value.strip()
    return default


def _to_host_url(base_url: str) -> str:
    """Translate a container-facing base URL to a host-reachable one.

    The harness runs on the host; ``host.docker.internal`` is only valid inside
    Docker containers. Swap it for ``localhost`` and strip the trailing
    ``/v1`` so we can append ``/api/v1/models`` (the LM Studio REST endpoint,
    not the OpenAI-compatible one which omits ``context_length``).
    """
    url = base_url.rstrip("/")
    url = url.replace("host.docker.internal", "localhost")
    # Strip trailing /v1 (OpenAI-compat path) to get the server root.
    if url.endswith("/v1"):
        url = url[:-3]
    return url


def _model_matches(model_obj: dict, target: str) -> bool:
    """Return whether a LM Studio REST model object matches the target name.

    LM Studio's ``/api/v1/models`` returns models identified by ``key``
    (e.g. ``qwen/qwen3.5-9b``) while the OpenAI-compatible endpoint serves
    them under ``loaded_instances[0].id`` (e.g. ``qwen3.5-9b``). Match against
    all identifier fields, case-insensitive, substring either direction, so a
    served name of ``qwen3.5-9b`` finds the model keyed ``qwen/qwen3.5-9b``.
    """
    t = target.lower()
    if not t:
        return False
    # loaded_instances[*].id — the API-facing identifier (best match).
    for inst in model_obj.get("loaded_instances") or []:
        iid = str(inst.get("id", "")).lower()
        if iid and (t == iid or t in iid or iid in t):
            return True
    # key — the model's canonical identifier.
    key = str(model_obj.get("key", "")).lower()
    if key and (t == key or t in key or key in t):
        return True
    # display_name — the human-readable name (weakest match).
    dn = str(model_obj.get("display_name", "")).lower()
    if dn and (t == dn or t in dn or dn in t):
        return True
    return False


def _extract_context_length(model_obj: dict) -> int | None:
    """Extract the effective context length from a LM Studio model object.

    Prefers ``loaded_instances[0].config.context_length`` (the active runtime
    limit — LM Studio may load a 262K model with only 32K to save VRAM) over
    ``max_context_length`` (the model's ceiling). Returns None when neither
    is present or valid.
    """
    for inst in model_obj.get("loaded_instances") or []:
        cfg = inst.get("config") or {}
        cl = cfg.get("context_length")
        if isinstance(cl, (int, float)) and cl > 0:
            return int(cl)
    mcl = model_obj.get("max_context_length")
    if isinstance(mcl, (int, float)) and mcl > 0:
        return int(mcl)
    return None


def probe_lm_studio_context(env_file: Path = Path(".env")) -> int | None:
    """Best-effort probe of LM Studio's REST API for the model's context length.

    Hits ``GET {base}/api/v1/models`` (LM Studio REST, not the OpenAI-compat
    ``/v1/models`` which omits ``context_length``). Reads
    ``EXPERIMENT_LLM_BASE_URL`` and ``EXPERIMENT_LLM_MODEL`` from ``.env``,
    translates ``host.docker.internal`` → ``localhost`` (harness runs on host).

    Returns ``loaded_instances[0].config.context_length`` (the active limit),
    falling back to ``max_context_length`` (the model ceiling), else ``None``.
    Never raises — any failure (server down, parse error, model not found)
    returns ``None`` with a warning printed to stderr.

    Args:
        env_file: Path to the ``.env`` file (default ``./.env``).

    Returns:
        The resolved context length (int > 0), or None when the probe fails
        or the field is absent.
    """
    base_url = read_str_env("EXPERIMENT_LLM_BASE_URL", env_file)
    model_name = read_str_env("EXPERIMENT_LLM_MODEL", env_file)
    if not base_url or not model_name:
        print(
            "[tinycua] max_context probe skipped — EXPERIMENT_LLM_BASE_URL or "
            "EXPERIMENT_LLM_MODEL missing from .env",
            file=sys.stderr,
            flush=True,
        )
        return None

    host_url = _to_host_url(base_url)
    probe_url = f"{host_url}/api/v1/models"
    try:
        req = urllib.request.Request(probe_url, method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:  # noqa: S310 — local server, no user input
            raw = resp.read()
        data = json.loads(raw)
    except (urllib.error.URLError, OSError, json.JSONDecodeError, ValueError) as exc:
        print(
            f"[tinycua] max_context probe failed ({probe_url}): {exc} — "
            f"using SDK default 128000",
            file=sys.stderr,
            flush=True,
        )
        return None

    models = data.get("models") if isinstance(data, dict) else None
    if not isinstance(models, list) or not models:
        print(
            f"[tinycua] max_context probe — no models in response from {probe_url}",
            file=sys.stderr,
            flush=True,
        )
        return None

    # First pass: find the matching model and extract its context length.
    for model_obj in models:
        if not isinstance(model_obj, dict):
            continue
        if _model_matches(model_obj, model_name):
            ctx = _extract_context_length(model_obj)
            if ctx is not None:
                print(
                    f"[tinycua] max_context={ctx} (probed from {probe_url})",
                    file=sys.stderr,
                    flush=True,
                )
                return ctx
            # Matched the model but no context_length field — fall through to
            # the no-context warning below.

    print(
        f"[tinycua] max_context probe — model '{model_name}' not found or "
        f"has no context_length in {probe_url}",
        file=sys.stderr,
        flush=True,
    )
    return None


def read_timeout_seconds(env_file: Path = Path(".env"), default: int = 14400) -> int:
    """Read runner timeout from .env without adding dependencies.

    Default is 14400s (4 hours) — 4× the old 3600s cap. The agent is now
    productive enough (680+ LLM calls per run, 33 executor cycles) that the
    old 1-hour wall clock killed it mid-work. The fair idle timeout
    (--idle-timeout-seconds, default 600s) is the primary "is it stuck?"
    guard; the hard cap is just a safety net for truly runaway processes.
    """
    return read_int_env("EXPERIMENT_TIMEOUT_SECONDS", env_file, default)


def read_hermes_process_poll_timeout_seconds(
    env_file: Path = Path(".env"),
    default: int = 600,
) -> int:
    """Read Hermes process-poll timeout; 0 disables the guard."""
    return read_int_env(HERMES_PROCESS_POLL_TIMEOUT_ENV, env_file, default)


def _hermes_process_poll_started(line: str) -> bool:
    """Return whether a Hermes log line starts a background process poll."""
    return bool(HERMES_PROCESS_POLL_STARTED_RE.search(line))


def _hermes_process_poll_completed(line: str) -> bool:
    """Return whether a Hermes process poll completed."""
    return "tool process completed" in line.lower()


def _no_response_sentinel(agent: str, stdout_text: str) -> bool:
    """Return whether a harness exited 0 despite emitting a no-response marker."""
    sentinel = _NO_RESPONSE_SENTINELS.get(agent)
    return bool(sentinel and sentinel in stdout_text)


def _hermes_poll_timed_out(
    started_at: float | None,
    timeout_seconds: int,
    now: float,
) -> bool:
    """Return whether the Hermes process-poll guard should fire."""
    return bool(started_at is not None and timeout_seconds > 0 and now - started_at >= timeout_seconds)


def sanitize_workdir(agent: str, workdir: Path) -> None:
    """Remove harness identity/cache artifacts before judging."""
    for name in HARNESS_ARTIFACTS.get(agent, set()):
        path = workdir / name
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
        elif path.exists():
            path.unlink(missing_ok=True)


def build_permission_repair_command(result_dir: Path, uid: int, gid: int) -> list[str]:
    """Build a helper-container command that returns mounted results to host ownership."""
    return [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{result_dir.resolve()}:/result",
        "docker.io/library/busybox:1.36",
        "sh",
        "-c",
        f"chown -R {uid}:{gid} /result && chmod -R u+rwX,go+rX /result",
    ]


def repair_result_permissions(result_dir: Path) -> None:
    """Best-effort fix for root-owned files created by containers."""
    if not result_dir.exists():
        return
    command = build_permission_repair_command(result_dir, os.getuid(), os.getgid())
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode:
        print(
            f"[warn] failed to repair permissions for {result_dir}: {result.stderr}",
            file=sys.stderr,
            flush=True,
        )


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
    # ponytail: json.loads succeeds for any valid JSON (bare string/number/
    # list), but the code below assumes an object. opencode occasionally
    # emits a non-object JSON line; pass it through instead of crashing.
    if not isinstance(event, dict):
        return line
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
    if not isinstance(part, dict):
        return f"  . {etype}\n"
    label = part.get("name") or part.get("type") or etype
    return f"  . {label}\n"


def run_agent(
    agent: str,
    experiment_num: int,
    prompt: str,
    workdir: Path,
    logs_dir: Path,
    timeout_seconds: int,
    hermes_process_poll_timeout_seconds: int = 600,
    idle_timeout_seconds: int = 0,
) -> int:
    """Run one Docker Compose service and write its artifacts.

    Args:
        timeout_seconds: Hard wall-clock deadline from start. Always enforced.
        idle_timeout_seconds: Optional "fair clock" — when > 0, the agent is
            only killed if it produces NO output for this many seconds. The
            deadline extends each time output arrives, so an actively-working
            agent never hits the idle timeout; only a truly stuck/hung one
            does. When 0, only the hard wall-clock deadline applies.
    """
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
    ]

    # FR-084 (experiment harness): probe LM Studio's REST API for the served
    # model's real context_length and pass it to the tinycua container so the
    # compaction threshold (0.7 × max_context) tracks the real wall instead of
    # the SDK's 128000 default. Tinycua-only; other harnesses manage their own
    # context windows. A manual EXPERIMENT_TINYCUA_MAX_CONTEXT in .env skips
    # the probe entirely (explicit override > probe > SDK default).
    if agent == "tinycua":
        manual = read_str_env("EXPERIMENT_TINYCUA_MAX_CONTEXT")
        if manual and manual.strip() and manual.strip().isdigit():
            max_ctx = int(manual.strip())
            print(f"[tinycua] max_context={max_ctx} (from .env override)", flush=True)
        else:
            max_ctx = probe_lm_studio_context()
        if max_ctx is not None:
            command.extend(["-e", f"EXPERIMENT_TINYCUA_MAX_CONTEXT={max_ctx}"])
        # FR-087..FR-093: opt-in markdown-synthesis ("lazy") retry strategy.
        # When EXPERIMENT_TINYCUA_RECOVERY_STRATEGY=markdown_synthesis is set
        # in .env, the tinycua container runs with --recovery-strategy
        # markdown_synthesis; otherwise it defaults to standard.
        recovery = read_str_env("EXPERIMENT_TINYCUA_RECOVERY_STRATEGY")
        if recovery and recovery.strip() in {"standard", "markdown_synthesis"}:
            command.extend(["-e", f"EXPERIMENT_TINYCUA_RECOVERY_STRATEGY={recovery.strip()}"])
            print(f"[tinycua] recovery_strategy={recovery.strip()} (from .env)", flush=True)

    command.append(agent)
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
            # Fair clock: when idle_timeout_seconds > 0, the agent is only
            # killed if silent for that long. The deadline extends on every
            # output line, so an actively-working agent (LLM calls, tool
            # output) never hits it — only a stuck/hung one does.
            idle_deadline: float | None = (
                time.monotonic() + idle_timeout_seconds if idle_timeout_seconds > 0 else None
            )
            hermes_poll_started_at: float | None = None
            saw_eof = {"out": False, "err": False}
            try:
                while True:
                    now = time.monotonic()
                    # Hermes poll guard: when hermes polls a never-ending
                    # background process (e.g. a uvicorn server), the poll
                    # blocks forever. Instead of killing the run (exit 124),
                    # send SIGINT so hermes can wrap up its turn and emit
                    # whatever response it has (the app was already built).
                    # If SIGINT doesn't work, the idle timeout or hard cap
                    # handles it. This is the fairness fix: hermes built the
                    # app and was verifying — it shouldn't lose all its work
                    # just because the server poll blocks.
                    if agent == "hermes" and _hermes_poll_timed_out(
                        hermes_poll_started_at,
                        hermes_process_poll_timeout_seconds,
                        now,
                    ):
                        stderr.write(
                            "\nHermes process poll timed out after "
                            f"{hermes_process_poll_timeout_seconds}s — "
                            "sending SIGINT to let it wrap up\n"
                        )
                        try:
                            process.send_signal(signal.SIGINT)
                        except (OSError, ProcessLookupError):
                            pass
                        hermes_poll_started_at = None  # don't re-fire
                        # Give hermes 30s to wrap up after SIGINT, then let the
                        # idle timeout / hard cap handle the rest.
                        last_output = time.monotonic()
                    # Hard wall-clock always applies (cap total runtime).
                    remaining = deadline - now
                    if remaining <= 0:
                        process.kill()
                        process.wait()
                        stderr.write(f"\nTimed out after {timeout_seconds} seconds\n")
                        exit_code = 124
                        break
                    # Fair idle clock: if set, kill only when silent > idle_timeout.
                    if idle_deadline is not None:
                        idle_remaining = idle_deadline - now
                        if idle_remaining <= 0:
                            silent = time.monotonic() - last_output
                            process.kill()
                            process.wait()
                            stderr.write(
                                f"\nIdle timed out after {idle_timeout_seconds}s "
                                f"of no output (silent {silent:.0f}s)\n"
                            )
                            exit_code = 124
                            break
                        wait_for = min(remaining, idle_remaining, 1.0)
                    else:
                        wait_for = min(remaining, 1.0)
                    try:
                        item = line_queue.get(timeout=wait_for)
                    except queue.Empty:
                        silent = time.monotonic() - last_output
                        if silent >= 15:
                            print(f"[{agent}] … ({silent:.0f}s)", flush=True)
                            last_output = time.monotonic()
                            # The "…" tick counts as activity for the silent
                            # indicator but NOT for the fair idle clock (only
                            # real agent output extends the deadline).
                        continue
                    source, line = item
                    if line is None:  # EOF for this stream
                        saw_eof[source] = True
                        if all(saw_eof.values()):
                            exit_code = process.wait()
                            break
                        continue
                    last_output = time.monotonic()
                    # Real agent output → extend the fair idle deadline.
                    if idle_deadline is not None:
                        idle_deadline = time.monotonic() + idle_timeout_seconds
                    # Detect first LLM call to start the runtime timer
                    if llm_started is None and warmup_marker and warmup_marker in line:
                        llm_started = datetime.now(UTC)
                        warmup = (llm_started - started).total_seconds()
                        print(f"[{agent}] ⚡ LLM call started (warmup {warmup:.1f}s)", flush=True)
                    if agent == "hermes":
                        if _hermes_process_poll_started(line):
                            hermes_poll_started_at = time.monotonic()
                        elif _hermes_process_poll_completed(line):
                            hermes_poll_started_at = None
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

    result_dir = logs_dir.parent
    repair_result_permissions(result_dir)
    sanitize_workdir(agent, workdir)
    # ponytail: OpenClaw exits 0 on a no-response turn; override so judging
    # still runs but the batch summary reports the real outcome.
    if exit_code == 0 and _no_response_sentinel(agent, stdout_path.read_text()):
        exit_code = 70
        stderr_path.write_text(
            (stderr_path.read_text() or "") + f"\n[{agent}] no-response sentinel matched\n"
        )
        print(f"[{agent}] no-response sentinel matched; overriding exit 0 -> 70", flush=True)
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
        "--agents",
        help="Comma-separated harnesses to run (default: all). Example: tinycua",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=None,
        help="Hard wall-clock cap per harness (default: EXPERIMENT_TIMEOUT_SECONDS or 14400).",
    )
    parser.add_argument(
        "--idle-timeout-seconds",
        type=int,
        default=None,
        help=(
            "Fair clock: kill the agent only if it produces NO output for this "
            "many seconds (resets on every output line). An actively-working "
            "agent never hits it — only a stuck/hung one does. Default: 0 "
            "(disabled; hard wall-clock only). Env: EXPERIMENT_IDLE_TIMEOUT_SECONDS."
        ),
    )
    args = parser.parse_args(argv)
    if args.num < 1:
        parser.error("--num must be positive")
    if args.timeout_seconds is not None and args.timeout_seconds < 1:
        parser.error("--timeout-seconds must be positive")
    try:
        args.agents = parse_agents(args.agents)
    except ValueError as error:
        parser.error(str(error))
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
        paths = prepare_result_dirs(
            output_root,
            args.num,
            overwrite=args.overwrite,
            agents=args.agents,
        )
        timeout_seconds = args.timeout_seconds or read_timeout_seconds()
        hermes_process_poll_timeout_seconds = read_hermes_process_poll_timeout_seconds()
        idle_timeout_seconds = args.idle_timeout_seconds
        if idle_timeout_seconds is None:
            idle_timeout_seconds = read_int_env("EXPERIMENT_IDLE_TIMEOUT_SECONDS")
    except (OSError, ValueError) as error:
        print(error, file=sys.stderr)
        return 2

    try:
        exit_codes = []
        for i, agent in enumerate(args.agents, 1):
            print(f"\n=== Agent {i}/{len(args.agents)}: {agent} ===", flush=True)
            exit_codes.append(
                run_agent(
                    agent,
                    args.num,
                    prompt,
                    paths[agent]["workdir"],
                    paths[agent]["logs"],
                    timeout_seconds,
                    hermes_process_poll_timeout_seconds,
                    idle_timeout_seconds,
                )
            )
    except KeyboardInterrupt:
        return 130
    print(
        "summary: "
        + ", ".join(
            f"{agent}={'passed' if code == 0 else 'failed'}"
            for agent, code in zip(args.agents, exit_codes, strict=True)
        ),
        flush=True,
    )
    return 1 if any(exit_codes) else 0


if __name__ == "__main__":
    raise SystemExit(main())
