"""Run prompt-list experiments sequentially, judge them, then archive results."""

from __future__ import annotations

import argparse
import json
import re
import shlex
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from run_experiment import AGENTS, parse_agents

Experiment = tuple[int, str]
LINE_RE = re.compile(r"^Experiment[_ -]?(\d+)\s*:\s*(.+)$", re.IGNORECASE)
SCRIPT_DIR = Path(__file__).resolve().parent


def load_experiments(manifest: Path) -> list[Experiment]:
    """Read `Experiment_1: prompt` lines from a manifest file."""
    experiments: list[Experiment] = []
    seen: set[int] = set()
    for line_no, raw_line in enumerate(manifest.read_text().splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = LINE_RE.match(line)
        if not match:
            msg = f"bad manifest line {line_no}: {raw_line}"
            raise ValueError(msg)
        num = int(match.group(1))
        prompt = match.group(2).strip()
        if num in seen:
            msg = f"duplicate experiment number: {num}"
            raise ValueError(msg)
        seen.add(num)
        experiments.append((num, prompt))
    if not experiments:
        msg = "no experiments found in manifest"
        raise ValueError(msg)
    return experiments


def archive_results(
    output_root: Path,
    archive_root: Path,
    experiments: list[Experiment],
    manifest: Path,
    archive_name: str | None = None,
    agents: tuple[str, ...] = AGENTS,
) -> Path:
    """Move requested experiment results into one archive directory."""
    name = archive_name or datetime.now(UTC).strftime("batch-%Y%m%d-%H%M%SZ")
    archive_dir = archive_root / name
    if archive_dir.exists():
        msg = f"archive already exists: {archive_dir}"
        raise FileExistsError(msg)
    archive_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(manifest, archive_dir / "manifest.txt")

    wanted = {num for num, _ in experiments}
    for agent in agents:
        agent_dir = output_root / agent
        for num in wanted:
            src = agent_dir / f"experiment-{num}"
            if not src.exists():
                continue
            dst = archive_dir / "results" / agent / src.name
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), dst)
        if agent_dir.exists() and not any(agent_dir.iterdir()):
            agent_dir.rmdir()
    return archive_dir


def _run(command: list[str], *, dry_run: bool) -> int:
    """Run one command, or print it during dry run."""
    print("$ " + shlex.join(command), flush=True)
    if dry_run:
        return 0
    return subprocess.run(command, cwd=SCRIPT_DIR).returncode


def _run_setup(*, dry_run: bool) -> int:
    """Run existing Docker/setup script once when present."""
    setup = SCRIPT_DIR / "scripts" / "setup.sh"
    if not setup.exists():
        return 0
    return _run(["bash", "scripts/setup.sh"], dry_run=dry_run)


def _run_experiment(
    num: int,
    prompt: str,
    output_root: Path,
    timeout_seconds: int | None,
    agents: tuple[str, ...],
    *,
    dry_run: bool,
) -> int:
    """Invoke the existing single-experiment runner."""
    command = [
        "uv",
        "run",
        "python",
        "run_experiment.py",
        "--num",
        str(num),
        "--prompt",
        prompt,
        "--output-root",
        str(output_root),
        "--overwrite",
        "--agents",
        ",".join(agents),
    ]
    if timeout_seconds is not None:
        command += ["--timeout-seconds", str(timeout_seconds)]
    return _run(command, dry_run=dry_run)


def _run_judge(
    num: int,
    output_root: Path,
    agents: tuple[str, ...],
    *,
    dry_run: bool,
) -> int:
    """Invoke the existing LLM judge for one experiment."""
    return _run(
        [
            "uv",
            "run",
            "python",
            "judge.py",
            "--num",
            str(num),
            "--output-root",
            str(output_root),
            "--agents",
            ",".join(agents),
        ],
        dry_run=dry_run,
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, default=Path("results"))
    parser.add_argument("--archive-root", type=Path, default=Path("archives"))
    parser.add_argument("--timeout-seconds", type=int)
    parser.add_argument("--skip-setup", action="store_true")
    parser.add_argument("--fail-fast", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--agents",
        help="Comma-separated harnesses to run/judge (default: all). Example: tinycua",
    )
    args = parser.parse_args(argv)
    if args.timeout_seconds is not None and args.timeout_seconds < 1:
        parser.error("--timeout-seconds must be positive")
    try:
        args.agents = parse_agents(args.agents)
    except ValueError as error:
        parser.error(str(error))
    return args


def main(argv: list[str] | None = None) -> int:
    """Run the batch."""
    args = parse_args(argv)
    manifest = args.manifest if args.manifest.is_absolute() else SCRIPT_DIR / args.manifest
    output_root = (
        args.output_root if args.output_root.is_absolute() else SCRIPT_DIR / args.output_root
    )
    archive_root = (
        args.archive_root if args.archive_root.is_absolute() else SCRIPT_DIR / args.archive_root
    )
    try:
        experiments = load_experiments(manifest)
    except (OSError, ValueError) as error:
        print(error, file=sys.stderr)
        return 2

    failures: list[dict[str, int | str]] = []
    if not args.skip_setup:
        code = _run_setup(dry_run=args.dry_run)
        if code:
            return code

    for num, prompt in experiments:
        print(f"\n=== Experiment {num}: run ===", flush=True)
        code = _run_experiment(
            num,
            prompt,
            output_root,
            args.timeout_seconds,
            args.agents,
            dry_run=args.dry_run,
        )
        if code:
            failures.append({"phase": "run", "experiment": num, "exit_code": code})
            if args.fail_fast:
                return code

    for num, _ in experiments:
        print(f"\n=== Experiment {num}: judge ===", flush=True)
        code = _run_judge(num, output_root, args.agents, dry_run=args.dry_run)
        if code:
            failures.append({"phase": "judge", "experiment": num, "exit_code": code})
            if args.fail_fast:
                return code

    if args.dry_run:
        return 1 if failures else 0

    archive_dir = archive_results(
        output_root,
        archive_root,
        experiments,
        manifest,
        agents=args.agents,
    )
    (archive_dir / "summary.json").write_text(
        json.dumps({"failures": failures}, indent=2) + "\n"
    )
    print(f"\narchived: {archive_dir}", flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
