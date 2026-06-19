"""Judge experiment workdirs using opencode as an impartial evaluator.

Reads JUDGE_MODEL and JUDGE_VARIANT from .env (defaults: openai/gpt-5.4, high).
For each agent, copies the workdir to an anonymous tmp dir, runs opencode as
the judge, and writes the verdict to results/{agent}/experiment-{N}/judge_verdict/.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from run_experiment import parse_agents

DEFAULT_JUDGE_MODEL = "openai/gpt-5.4"
DEFAULT_JUDGE_VARIANT = "high"
CRITERIA_FILE = Path(__file__).parent / "judge_criteria.md"
HARNESS_ARTIFACTS = {
    ".openclaw",
    ".tinycua_context_cache",
    "AGENTS.md",
    "BOOTSTRAP.md",
    "HEARTBEAT.md",
    "IDENTITY.md",
    "SOUL.md",
    "TOOLS.md",
    "USER.md",
}


def read_env(key: str, default: str = "", env_file: Path = Path(".env")) -> str:
    """Read a value from .env, falling back to default."""
    if not env_file.exists():
        return default
    for raw_line in env_file.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        if k.strip() == key:
            return v.strip()
    return default


def extract_verdict_text(raw_json_lines: str) -> str:
    """Pull text events from opencode JSON output, concatenate into verdict."""
    parts = []
    for line in raw_json_lines.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "text":
            text = event.get("part", {}).get("text", "")
            if text:
                parts.append(text)
    return "\n\n".join(parts)


def build_judge_prompt(task_prompt: str, criteria: str, *, workdir_empty: bool) -> str:
    """Build the prompt for the judge agent."""
    source_note = (
        "The workdir is empty — read `stdout.log` to evaluate the agent's "
        "conversational response to the task."
        if workdir_empty
        else "Inspect the files in the current directory. These are the agent's work products."
    )
    return (
        "You are an impartial judge evaluating an AI agent's work on a task.\n\n"
        "## Original Task\n"
        f"{task_prompt}\n\n"
        "## Judging Criteria\n"
        f"{criteria}\n\n"
        "## Your Job\n"
        f"{source_note}\n\n"
        "Evaluate the submission against every criterion. Write your verdict as markdown.\n"
        "Be concise, fair, and objective. Do not speculate about which tool produced the work."
    )


def _copy_workdir(src: Path, dst: Path) -> bool:
    """Copy workdir contents into dst. Return True if any files were copied."""
    has_files = False
    for item in src.iterdir():
        if item.name in HARNESS_ARTIFACTS:
            continue
        if item.is_dir():
            shutil.copytree(item, dst / item.name)
        else:
            shutil.copy2(item, dst / item.name)
        has_files = True
    return has_files


def judge_agent(
    agent: str,
    experiment_num: int,
    result_root: Path,
    judge_model: str,
    judge_variant: str,
    criteria: str,
    tmp_base: Path,
) -> int:
    """Judge one agent's workdir anonymously."""
    exp_dir = result_root / agent / f"experiment-{experiment_num}"
    workdir = exp_dir / "workdir"
    logs_dir = exp_dir / "logs"
    verdict_dir = exp_dir / "judge_verdict"

    if not exp_dir.exists():
        print(f"[{agent}] no experiment-{experiment_num} found, skipping", flush=True)
        return 1

    prompt = (logs_dir / "prompt.txt").read_text() if (logs_dir / "prompt.txt").exists() else ""

    # Anonymous submission dir — judge must not see the agent name
    submission_dir = tmp_base / "submission"
    if submission_dir.exists():
        shutil.rmtree(submission_dir)
    submission_dir.mkdir(parents=True)

    has_files = _copy_workdir(workdir, submission_dir) if workdir.exists() else False
    if not has_files:
        stdout_log = logs_dir / "stdout.log"
        if stdout_log.exists():
            shutil.copy2(stdout_log, submission_dir / "stdout.log")

    judge_prompt = build_judge_prompt(prompt, criteria, workdir_empty=not has_files)

    print(f"[{agent}] judging with {judge_model}/{judge_variant}…", flush=True)
    started = datetime.now(UTC)

    command = [
        "opencode", "run",
        "--pure",
        "--dangerously-skip-permissions",
        "--format", "json",
        "-m", judge_model,
        "--variant", judge_variant,
        "--dir", str(submission_dir),
        judge_prompt,
    ]

    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=600)
    except subprocess.TimeoutExpired:
        print(f"[{agent}] judge timed out after 600s", flush=True)
        return 124

    verdict_dir.mkdir(parents=True, exist_ok=True)
    (verdict_dir / "raw_output.log").write_text(result.stdout)
    if result.stderr:
        (verdict_dir / "raw_stderr.log").write_text(result.stderr)

    verdict = extract_verdict_text(result.stdout)
    if not verdict:
        verdict = f"(No text output from judge. See raw_output.log. Exit code: {result.returncode})"

    (verdict_dir / "verdict.md").write_text(verdict + "\n")

    elapsed = (datetime.now(UTC) - started).total_seconds()
    metadata = {
        "experiment_num": experiment_num,
        "agent": agent,
        "judge_model": judge_model,
        "judge_variant": judge_variant,
        "started_at": started.isoformat(),
        "duration_seconds": round(elapsed, 2),
        "exit_code": result.returncode,
        "workdir_empty": not has_files,
    }
    (verdict_dir / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")

    status = "passed" if result.returncode == 0 else "failed"
    print(f"[{agent}] {status} verdict written ({elapsed:.1f}s)", flush=True)
    return result.returncode


def main(argv: list[str] | None = None) -> int:
    """Run the judge on an experiment."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--num", type=int, required=True, help="Experiment number to judge.")
    parser.add_argument("--output-root", type=Path, default=Path("results"))
    parser.add_argument("--model", help=f"Judge model (default: {DEFAULT_JUDGE_MODEL})")
    parser.add_argument("--variant", help=f"Judge variant (default: {DEFAULT_JUDGE_VARIANT})")
    parser.add_argument(
        "--agents",
        help="Comma-separated harnesses to judge (default: all). Example: tinycua",
    )
    args = parser.parse_args(argv)

    if args.num < 1:
        parser.error("--num must be positive")
    try:
        agents = parse_agents(args.agents)
    except ValueError as error:
        parser.error(str(error))

    result_root = (
        args.output_root if args.output_root.is_absolute() else Path.cwd() / args.output_root
    )

    judge_model = args.model or read_env("JUDGE_MODEL", DEFAULT_JUDGE_MODEL)
    judge_variant = args.variant or read_env("JUDGE_VARIANT", DEFAULT_JUDGE_VARIANT)

    if not CRITERIA_FILE.exists():
        print(f"criteria file not found: {CRITERIA_FILE}", file=sys.stderr)
        return 2
    criteria = CRITERIA_FILE.read_text()

    # ponytail: tmp_base under ./tmp which is gitignored; cleaned up after judging
    tmp_base = Path.cwd() / "tmp" / f"judge-{args.num}"
    tmp_base.mkdir(parents=True, exist_ok=True)

    print(f"Judge: {judge_model}/{judge_variant}", flush=True)
    print(f"Experiment: {args.num}", flush=True)

    exit_codes = []
    for i, agent in enumerate(agents, 1):
        print(f"\n=== Judging {i}/{len(agents)}: {agent} ===", flush=True)
        exit_codes.append(
            judge_agent(
                agent, args.num, result_root, judge_model, judge_variant, criteria, tmp_base
            )
        )

    shutil.rmtree(tmp_base, ignore_errors=True)

    print(
        "\nsummary: "
        + ", ".join(
            f"{agent}={'ok' if code == 0 else 'fail'}"
            for agent, code in zip(agents, exit_codes, strict=True)
        ),
        flush=True,
    )
    return 1 if any(exit_codes) else 0


if __name__ == "__main__":
    raise SystemExit(main())
