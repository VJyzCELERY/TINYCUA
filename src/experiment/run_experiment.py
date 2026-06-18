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


def run_agent(agent: str, experiment_num: int, prompt: str, result_dir: Path) -> int:
    """Run one Docker Compose service and write its artifacts."""
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
        f"{result_dir}:{workspace}",
        "--workdir",
        workspace,
        agent,
    ]
    started = datetime.now(UTC)
    try:
        result = subprocess.run(command, text=True, capture_output=True, check=False)
        exit_code = result.returncode
        stdout = result.stdout
        stderr = result.stderr
    except FileNotFoundError as error:
        exit_code = 127
        stdout = ""
        stderr = f"{error}\n"
    ended = datetime.now(UTC)

    (result_dir / "stdout.log").write_text(stdout)
    (result_dir / "stderr.log").write_text(stderr)
    metadata = build_metadata(experiment_num, agent, started, ended, exit_code)
    (result_dir / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
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
    args = parser.parse_args(argv)
    if args.num < 1:
        parser.error("--num must be positive")
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
    except (OSError, ValueError) as error:
        print(error, file=sys.stderr)
        return 2

    exit_codes = [run_agent(agent, args.num, prompt, paths[agent]) for agent in AGENTS]
    return 1 if any(exit_codes) else 0


if __name__ == "__main__":
    raise SystemExit(main())
