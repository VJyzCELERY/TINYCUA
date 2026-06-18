"""Run one prompt across the experiment agent harnesses."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path


AGENTS = ("opencode", "hermes", "openclaw", "tinycua")


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
) -> dict[str, Path]:
    """Create one result directory per agent."""
    paths = {
        agent: output_root / agent / f"experiment-{experiment_num}" for agent in AGENTS
    }
    existing = [path for path in paths.values() if path.exists()]
    if existing and not overwrite:
        msg = f"output exists; rerun with --overwrite: {existing[0]}"
        raise FileExistsError(msg)
    for path in paths.values():
        if path.exists():
            shutil.rmtree(path)
        path.mkdir(parents=True)
    return paths


def build_metadata(
    experiment_num: int,
    agent: str,
    started_at: datetime,
    ended_at: datetime,
    exit_code: int,
) -> dict[str, object]:
    """Build JSON-safe run metadata."""
    return {
        "experiment_num": experiment_num,
        "agent": agent,
        "started_at": started_at.isoformat(),
        "ended_at": ended_at.isoformat(),
        "duration_seconds": round((ended_at - started_at).total_seconds(), 6),
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
) -> dict[str, object]:
    """Write run metadata and return it."""
    metadata = build_metadata(experiment_num, agent, started, datetime.now(UTC), exit_code)
    (result_dir / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    return metadata


def run_agent(
    agent: str,
    experiment_num: int,
    prompt: str,
    result_dir: Path,
    timeout_seconds: int,
) -> int:
    """Run one Docker Compose service and write its artifacts."""
    print(f"[{agent}] starting experiment-{experiment_num}", flush=True)
    (result_dir / "prompt.txt").write_text(prompt)
    env_file = Path(".env")
    if env_file.exists():
        (result_dir / "container.env").write_text(env_file.read_text())
    workspace = f"/workspace/experiment-{experiment_num}"
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
        f"EXPERIMENT_WORKSPACE={workspace}",
        "-v",
        f"{result_dir.resolve()}:{workspace}",
        "--workdir",
        workspace,
        agent,
    ]
    started = datetime.now(UTC)
    stdout_path = result_dir / "stdout.log"
    stderr_path = result_dir / "stderr.log"
    try:
        with stdout_path.open("w") as stdout, stderr_path.open("w") as stderr:
            process = subprocess.Popen(command, text=True, stdout=stdout, stderr=stderr)
            try:
                exit_code = process.wait(timeout=timeout_seconds)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                stderr.write(f"\nTimed out after {timeout_seconds} seconds\n")
                exit_code = 124
            except KeyboardInterrupt:
                process.kill()
                process.wait()
                stderr.write("\nInterrupted by user\n")
                _write_metadata(result_dir, experiment_num, agent, started, 130)
                print(f"[{agent}] interrupted exit_code=130", flush=True)
                raise
    except FileNotFoundError as error:
        exit_code = 127
        stdout_path.write_text("")
        stderr_path.write_text(f"{error}\n")

    metadata = _write_metadata(result_dir, experiment_num, agent, started, exit_code)
    print(f"[{agent}] {metadata['status']} exit_code={exit_code}", flush=True)
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
        exit_codes = [
            run_agent(agent, args.num, prompt, paths[agent], timeout_seconds)
            for agent in AGENTS
        ]
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
