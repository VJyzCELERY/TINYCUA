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
        "Evaluate the submission against every criterion. You may test code "
        "using Docker containers (e.g. `docker run --rm -v \"$(pwd):/work\" "
        "-w /work python:3.12-slim python app.py`) to verify correctness — "
        "do not run code directly on the host. Write your verdict as markdown.\n"
        "Be concise, fair, and objective. Do not speculate about which tool "
        "produced the work."
    )


def build_cross_judge_prompt(
    task_prompt: str,
    criteria: str,
    submissions: list[tuple[str, Path, bool]],
) -> str:
    """Build the prompt for cross-judging multiple anonymous submissions.

    Args:
        task_prompt: The original task prompt.
        criteria: The judging criteria text.
        submissions: List of (anonymous_label, submission_dir, workdir_empty)
            tuples for each agent's work.

    Returns:
        The judge prompt that asks the judge to compare all submissions.
    """
    submission_descriptions = []
    for label, subdir, workdir_empty in submissions:
        if workdir_empty:
            submission_descriptions.append(
                f"### Submission {label}\n"
                f"Directory: `{subdir}`\n"
                f"This submission's workdir is empty — read `{subdir}/stdout.log` "
                f"to evaluate the agent's conversational response."
            )
        else:
            submission_descriptions.append(
                f"### Submission {label}\n"
                f"Directory: `{subdir}`\n"
                f"Inspect the files in this directory. These are this agent's work products."
            )
    submissions_block = "\n\n".join(submission_descriptions)

    return (
        "You are an impartial judge comparing multiple AI agents' work on the "
        "same task. Each submission is anonymous (labeled A, B, C, etc.).\n\n"
        "## Original Task\n"
        f"{task_prompt}\n\n"
        "## Judging Criteria\n"
        f"{criteria}\n\n"
        "## Submissions\n\n"
        f"{submissions_block}\n\n"
        "## Your Job\n\n"
        "Evaluate each submission against every criterion. Then rank them "
        "from best to worst. Write your verdict as markdown with this format:\n\n"
        "```markdown\n"
        "## Per-Submission Scores\n\n"
        "### Submission X\n"
        "| Criterion | Score | Justification |\n"
        "|-----------|-------|---------------|\n"
        "| Task Completion | X | ... |\n"
        "| Correctness | X | ... |\n"
        "| Quality & Craftsmanship | X | ... |\n"
        "| Autonomy | X | ... |\n"
        "| Completeness & Edge Cases | X | ... |\n"
        "\n**Overall: X/5**\n"
        "\n(Repeat for each submission)\n\n"
        "## Ranking\n\n"
        "1. Submission X (X/5) — best because...\n"
        "2. Submission Y (Y/5) — ...\n"
        "3. Submission Z (Z/5) — ...\n\n"
        "## Summary\n"
        "2-3 sentences comparing the submissions.\n"
        "```\n\n"
        "Rules:\n"
        "- Judge only what is in each submission directory.\n"
        "- Do not speculate about which tool or agent produced each submission.\n"
        "- Be fair and consistent. Rank based on the criteria scores.\n"
        "- You may test code using Docker containers (e.g. "
        "`docker run --rm -v \"$(pwd):/work\" -w /work python:3.12-slim "
        "python app.py`) to verify correctness. Do not run code directly "
        "on the host. Each submission is in a subdirectory — cd into it "
        "before testing.\n"
        "- Do not modify the submission files. Test in a container, then "
        "discard the container.\n"
    )


def _copy_workdir(src: Path, dst: Path) -> bool:
    """Copy workdir contents into dst. Return True if any files were copied."""
    has_files = False
    # Directories that are container-only artifacts — skip them so broken
    # symlinks (venv/bin/python → /usr/bin/python inside Docker) don't crash
    # copytree, and the judge doesn't see build noise.
    _SKIP_DIRS = frozenset({
        "venv", ".venv", "node_modules", "__pycache__",
        ".git", ".tinycua-artifacts", ".tinycua_context_cache",
    })
    for item in src.iterdir():
        if item.name in HARNESS_ARTIFACTS:
            continue
        if item.is_dir():
            if item.name in _SKIP_DIRS:
                continue
            try:
                shutil.copytree(item, dst / item.name, ignore_dangling_symlinks=True)
            except shutil.Error:
                # Broken symlinks inside nested dirs — copy what we can.
                shutil.copytree(
                    item, dst / item.name,
                    ignore_dangling_symlinks=True,
                    dirs_exist_ok=True,
                )
        else:
            try:
                shutil.copy2(item, dst / item.name)
            except (OSError, shutil.SameFileError):
                pass
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


def cross_judge_experiment(
    experiment_num: int,
    agents: tuple[str, ...],
    result_root: Path,
    judge_model: str,
    judge_variant: str,
    criteria: str,
    tmp_base: Path,
) -> int:
    """Cross-judge all agents' submissions for one experiment.

    Copies each agent's workdir into an anonymous submission directory
    (submission-A, submission-B, etc.), presents all to the judge at once,
    and writes the cross-verdict. The mapping (A→agent, B→agent) is saved
    in a mapping file so the user can de-anonymize after judging.
    """
    print(f"\n=== Cross-judging experiment {experiment_num} ===", flush=True)

    # Build anonymous submissions.
    import string
    submissions: list[tuple[str, Path, bool, str]] = []  # (label, dir, empty, agent)
    for i, agent in enumerate(agents):
        label = string.ascii_uppercase[i] if i < 26 else f"Agent-{i}"
        exp_dir = result_root / agent / f"experiment-{experiment_num}"
        if not exp_dir.exists():
            print(f"  [{agent}] no experiment-{experiment_num} found, skipping", flush=True)
            continue
        workdir = exp_dir / "workdir"
        logs_dir = exp_dir / "logs"
        prompt = (logs_dir / "prompt.txt").read_text() if (logs_dir / "prompt.txt").exists() else ""

        submission_dir = tmp_base / f"submission-{label}"
        if submission_dir.exists():
            shutil.rmtree(submission_dir)
        submission_dir.mkdir(parents=True)

        has_files = _copy_workdir(workdir, submission_dir) if workdir.exists() else False
        if not has_files:
            stdout_log = logs_dir / "stdout.log"
            if stdout_log.exists():
                shutil.copy2(stdout_log, submission_dir / "stdout.log")

        submissions.append((label, submission_dir, not has_files, agent))
        print(f"  {label} → {agent}", flush=True)

    if len(submissions) < 2:
        print("  Need at least 2 submissions to cross-judge. Aborting.", flush=True)
        return 1

    # Build the cross-judge prompt.
    task_prompt = ""
    for _, _, _, agent in submissions:
        exp_dir = result_root / agent / f"experiment-{experiment_num}"
        logs_dir = exp_dir / "logs"
        p = (logs_dir / "prompt.txt").read_text() if (logs_dir / "prompt.txt").exists() else ""
        if p:
            task_prompt = p
            break

    judge_prompt = build_cross_judge_prompt(
        task_prompt, criteria,
        [(label, subdir, empty) for label, subdir, empty, _ in submissions],
    )

    # Run the judge from the tmp_base directory so it can access all submissions.
    print(f"  judging with {judge_model}/{judge_variant}…", flush=True)
    started = datetime.now(UTC)
    command = [
        "opencode", "run",
        "--pure",
        "--dangerously-skip-permissions",
        "--format", "json",
        "-m", judge_model,
        "--variant", judge_variant,
        "--dir", str(tmp_base),
        judge_prompt,
    ]

    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=900)
    except subprocess.TimeoutExpired:
        print("  cross-judge timed out after 900s", flush=True)
        return 124

    # Write verdict to a cross-verdict directory at the experiment level.
    # Pick the first agent's exp_dir as the canonical location.
    first_agent = submissions[0][3]
    verdict_dir = result_root / first_agent / f"experiment-{experiment_num}" / "cross_verdict"
    verdict_dir.mkdir(parents=True, exist_ok=True)

    (verdict_dir / "raw_output.log").write_text(result.stdout)
    if result.stderr:
        (verdict_dir / "raw_stderr.log").write_text(result.stderr)

    verdict = extract_verdict_text(result.stdout)
    if not verdict:
        verdict = f"(No text output from judge. See raw_output.log. Exit code: {result.returncode})"

    (verdict_dir / "verdict.md").write_text(verdict + "\n")

    # Write the anonymous→agent mapping (for de-anonymization after judging).
    mapping = {
        "experiment_num": experiment_num,
        "judge_model": judge_model,
        "judge_variant": judge_variant,
        "started_at": started.isoformat(),
        "duration_seconds": round((datetime.now(UTC) - started).total_seconds(), 2),
        "exit_code": result.returncode,
        "mapping": {label: agent for label, _, _, agent in submissions},
    }
    (verdict_dir / "mapping.json").write_text(json.dumps(mapping, indent=2) + "\n")

    elapsed = (datetime.now(UTC) - started).total_seconds()
    status = "passed" if result.returncode == 0 else "failed"
    print(f"  {status} cross-verdict written ({elapsed:.1f}s)", flush=True)
    print(f"  mapping: {verdict_dir / 'mapping.json'}", flush=True)
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
    parser.add_argument(
        "--cross-judge",
        action="store_true",
        default=False,
        help="Cross-judge all agents against each other (anonymous, comparative ranking).",
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

    if args.cross_judge:
        exit_code = cross_judge_experiment(
            args.num, agents, result_root, judge_model, judge_variant, criteria, tmp_base
        )
        shutil.rmtree(tmp_base, ignore_errors=True)
        return exit_code

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
