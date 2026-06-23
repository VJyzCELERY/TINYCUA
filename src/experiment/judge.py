"""Judge experiment workdirs using the hermes-judge Docker container.

The judge container is a persistent Hermes Agent instance (configured via
scripts/setup_judge.sh or scripts/reconfigure_judge.sh). Its active model
and provider live in the judge-hermes-home Docker volume; judge.py does
NOT override them — it always uses whatever the container is configured
with, and snapshots that configuration into each verdict dir for audit.

For each agent, copies the workdir to an anonymous tmp dir, runs hermes
as the judge (one-shot, quiet mode), and writes the verdict to
results/{agent}/experiment-{N}/judge_verdict/.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from run_experiment import parse_agents

# The judge container is defined in docker-compose.yml. judge.py shells out to
# `docker compose exec`, so it must run from the experiment dir (where the
# compose file lives).
EXPERIMENT_DIR = Path(__file__).parent
JUDGE_TIMEOUT_SECONDS = 600
CROSS_JUDGE_TIMEOUT_SECONDS = 900
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


def extract_hermes_verdict(raw_output: str) -> str:
    """Pull the verdict out of `hermes chat -Q -q` quiet-mode output.

    Hermes quiet mode prints `session_id: <id>\\n<final response>`. We drop
    the leading session_id line and return the rest. If the session_id
    line is absent (e.g. an error path), return the raw output stripped.
    """
    stripped = raw_output.strip()
    if not stripped:
        return ""
    # Drop the leading `session_id: ...` line. The verdict is everything after.
    first_nl = stripped.find("\n")
    if first_nl == -1:
        # Single line — if it's a session_id line, there's no verdict.
        if stripped.startswith("session_id:"):
            return ""
        return stripped
    first_line = stripped[:first_nl]
    if first_line.startswith("session_id:"):
        return stripped[first_nl + 1 :].strip()
    return stripped


def _container_path(host_path: Path) -> str:
    """Map a host path under the experiment dir to its /workspace view.

    The judge container mounts the experiment dir at /workspace, so a host
    path like /repo/src/experiment/tmp/judge-2/submission becomes
    /workspace/tmp/judge-2/submission inside the container.
    """
    try:
        rel = host_path.relative_to(EXPERIMENT_DIR)
    except ValueError:
        # Not under the experiment dir — fall back to the host path. The
        # judge won't be able to read it, but at least the error is visible.
        return str(host_path)
    return f"/workspace/{rel}"


_MODEL_BLOCK_RE = re.compile(r"Model:\s*(\{[^}]*\})", re.MULTILINE)

_FAILED_FIELDS = {
    "judge_model": "(snapshot failed)",
    "judge_provider": "(snapshot failed)",
    "judge_base_url": "(snapshot failed)",
}


def parse_model_snapshot(config_show_stdout: str) -> dict[str, str]:
    """Parse the ◆ Model block from `hermes config show` output.

    The block looks like:
        Model: {'default': 'gpt-5.5', 'provider': 'openai-codex', 'base_url': '...'}
    Returns a dict with judge_model, judge_provider, judge_base_url. On any
    failure (no match, bad literal), returns the failed-fields marker dict.
    """
    match = _MODEL_BLOCK_RE.search(config_show_stdout)
    if not match:
        return dict(_FAILED_FIELDS)
    try:
        model_dict = ast.literal_eval(match.group(1))
    except (ValueError, SyntaxError):
        return dict(_FAILED_FIELDS)
    if not isinstance(model_dict, dict):
        return dict(_FAILED_FIELDS)
    return {
        "judge_model": str(model_dict.get("default", "")) or "(unset)",
        "judge_provider": str(model_dict.get("provider", "")) or "(unset)",
        "judge_base_url": str(model_dict.get("base_url", "")) or "(unset)",
    }


def snapshot_judge_model() -> tuple[dict[str, str], str]:
    """Capture the judge container's active model/provider/base_url.

    Runs `hermes config show` inside the judge container and parses the
    `◆ Model` block via :func:`parse_model_snapshot`. Returns
    (parsed_fields, raw_stdout). On subprocess failure, fields carry the
    "(snapshot failed)" marker and raw_stdout may be empty.
    """
    try:
        result = subprocess.run(
            [
                "docker", "compose", "exec", "-T", "judge",
                "hermes", "config", "show",
            ],
            capture_output=True, text=True, timeout=30, cwd=EXPERIMENT_DIR,
        )
    except (subprocess.SubprocessError, OSError):
        return dict(_FAILED_FIELDS), ""
    if result.returncode != 0:
        return dict(_FAILED_FIELDS), result.stdout
    return parse_model_snapshot(result.stdout), result.stdout


def _judge_container_running() -> bool:
    """Return True if the judge container is up and ready for exec.

    Uses `docker compose ps judge` (exit 0 + a running state line). Cheap,
    no hermes invocation — just checks the container exists and is running.
    """
    try:
        result = subprocess.run(
            ["docker", "compose", "ps", "judge"],
            capture_output=True, text=True, timeout=15, cwd=EXPERIMENT_DIR,
        )
    except (subprocess.SubprocessError, OSError):
        return False
    if result.returncode != 0:
        return False
    # `docker compose ps` prints a header line then one row per running service.
    # A running judge container yields at least one non-header row mentioning
    # "Up" (the status column). If the container is stopped/absent, the row
    # is absent or shows a non-Up status.
    return any("Up" in line for line in result.stdout.splitlines()[1:])


def build_judge_prompt(task_prompt: str, *, workdir_empty: bool, submission_dir_container: str) -> str:
    """Build the prompt for the judge agent.

    The rubric (scoring scale, criteria, rules) lives in the judge profile's
    SOUL.md, so it is NOT injected here — only the task and the submission
    location. submission_dir_container is the /workspace/... path the judge
    reads (the container mounts the experiment dir at /workspace).
    """
    if workdir_empty:
        source_note = (
            f"The workdir at `{submission_dir_container}` is empty — read "
            f"`{submission_dir_container}/stdout.log` to evaluate the agent's "
            "conversational response to the task."
        )
    else:
        source_note = (
            f"Inspect the files in `{submission_dir_container}`. These are the "
            "agent's work products."
        )
    return (
        "You are an impartial judge evaluating an AI agent's work on a task.\n\n"
        "## Original Task\n"
        f"{task_prompt}\n\n"
        "## Your Job\n"
        f"{source_note}\n\n"
        "Evaluate the submission against every criterion in your judging "
        "rubric. You may test code using Docker containers (e.g. "
        "`docker run --rm -v \"$(pwd):/work\" -w /work python:3.12-slim "
        "python app.py`) to verify correctness — do not run code directly "
        "on the host. Write your verdict as markdown.\n"
        "Be concise, fair, and objective. Do not speculate about which tool "
        "produced the work."
    )


def build_cross_judge_prompt(
    task_prompt: str,
    submissions: list[tuple[str, str, bool]],
) -> str:
    """Build the prompt for cross-judging multiple anonymous submissions.

    Args:
        task_prompt: The original task prompt.
        submissions: List of (anonymous_label, submission_dir_container,
            workdir_empty) tuples — submission_dir_container is the
            /workspace/... path the judge reads.

    Returns:
        The judge prompt that asks the judge to compare all submissions.
        The comparative output format is specified here (not in SOUL.md)
        because it's tightly coupled to the dynamic A/B/C labels.
    """
    submission_descriptions = []
    for label, subdir, workdir_empty in submissions:
        if workdir_empty:
            submission_descriptions.append(
                f"### Submission {label}\n"
                f"Directory: `{subdir}`\n"
                f"This submission's workdir is empty — read "
                f"`{subdir}/stdout.log` to evaluate the agent's "
                "conversational response."
            )
        else:
            submission_descriptions.append(
                f"### Submission {label}\n"
                f"Directory: `{subdir}`\n"
                "Inspect the files in this directory. These are this agent's work products."
            )
    submissions_block = "\n\n".join(submission_descriptions)

    return (
        "You are an impartial judge comparing multiple AI agents' work on the "
        "same task. Each submission is anonymous (labeled A, B, C, etc.).\n\n"
        "## Original Task\n"
        f"{task_prompt}\n\n"
        "## Submissions\n\n"
        f"{submissions_block}\n\n"
        "## Your Job\n\n"
        "Evaluate each submission against every criterion in your judging "
        "rubric. Then rank them from best to worst. Write your verdict as "
        "markdown with this format:\n\n"
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
    tmp_base: Path,
) -> int:
    """Judge one agent's workdir anonymously using the hermes-judge container."""
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

    submission_dir_container = _container_path(submission_dir)
    judge_prompt = build_judge_prompt(
        prompt, workdir_empty=not has_files,
        submission_dir_container=submission_dir_container,
    )

    print(f"[{agent}] judging via hermes-judge container…", flush=True)
    started = datetime.now(UTC)

    command = [
        "docker", "compose", "exec",
        "-T",
        "judge",
        "hermes", "-p", "judge", "chat", "-Q", "-q",
        judge_prompt,
    ]

    try:
        result = subprocess.run(
            command, capture_output=True, text=True,
            timeout=JUDGE_TIMEOUT_SECONDS, cwd=EXPERIMENT_DIR,
        )
    except subprocess.TimeoutExpired:
        print(f"[{agent}] judge timed out after {JUDGE_TIMEOUT_SECONDS}s", flush=True)
        return 124

    verdict_dir.mkdir(parents=True, exist_ok=True)
    (verdict_dir / "raw_output.log").write_text(result.stdout)
    if result.stderr:
        (verdict_dir / "raw_stderr.log").write_text(result.stderr)

    verdict = extract_hermes_verdict(result.stdout)
    if not verdict:
        verdict = f"(No text output from judge. See raw_output.log. Exit code: {result.returncode})"

    (verdict_dir / "verdict.md").write_text(verdict + "\n")

    # Snapshot the judge's active model/provider into the verdict dir for audit.
    model_fields, raw_snapshot = snapshot_judge_model()
    if raw_snapshot:
        (verdict_dir / "judge_model_snapshot.txt").write_text(raw_snapshot)

    elapsed = (datetime.now(UTC) - started).total_seconds()
    metadata = {
        "experiment_num": experiment_num,
        "agent": agent,
        **model_fields,
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
        task_prompt,
        [(label, _container_path(subdir), empty) for label, subdir, empty, _ in submissions],
    )

    print("  judging via hermes-judge container…", flush=True)
    started = datetime.now(UTC)
    command = [
        "docker", "compose", "exec",
        "-T",
        "judge",
        "hermes", "-p", "judge", "chat", "-Q", "-q",
        judge_prompt,
    ]

    try:
        result = subprocess.run(
            command, capture_output=True, text=True,
            timeout=CROSS_JUDGE_TIMEOUT_SECONDS, cwd=EXPERIMENT_DIR,
        )
    except subprocess.TimeoutExpired:
        print(f"  cross-judge timed out after {CROSS_JUDGE_TIMEOUT_SECONDS}s", flush=True)
        return 124

    # Write verdict to a cross-verdict directory at the experiment level.
    # Pick the first agent's exp_dir as the canonical location.
    first_agent = submissions[0][3]
    verdict_dir = result_root / first_agent / f"experiment-{experiment_num}" / "cross_verdict"
    verdict_dir.mkdir(parents=True, exist_ok=True)

    (verdict_dir / "raw_output.log").write_text(result.stdout)
    if result.stderr:
        (verdict_dir / "raw_stderr.log").write_text(result.stderr)

    verdict = extract_hermes_verdict(result.stdout)
    if not verdict:
        verdict = f"(No text output from judge. See raw_output.log. Exit code: {result.returncode})"

    (verdict_dir / "verdict.md").write_text(verdict + "\n")

    # Snapshot the judge's active model/provider for audit.
    model_fields, raw_snapshot = snapshot_judge_model()
    if raw_snapshot:
        (verdict_dir / "judge_model_snapshot.txt").write_text(raw_snapshot)

    # Write the anonymous→agent mapping (for de-anonymization after judging).
    mapping = {
        "experiment_num": experiment_num,
        **model_fields,
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

    # Fail fast if the hermes-judge container isn't running — judging shells
    # out to `docker compose exec judge hermes ...`, which hangs/errors
    # cryptically if the container is down. Point the user at setup_judge.sh.
    if not _judge_container_running():
        print(
            "ERROR: hermes-judge container is not running.\n"
            "Start it with: bash scripts/setup_judge.sh\n"
            "Or restart an existing one: docker compose up -d judge",
            file=sys.stderr,
        )
        return 3

    # ponytail: tmp_base under ./tmp which is gitignored; cleaned up after judging
    tmp_base = Path.cwd() / "tmp" / f"judge-{args.num}"
    tmp_base.mkdir(parents=True, exist_ok=True)

    print(f"Judge: hermes-judge container (active model from setup_judge.sh)", flush=True)
    print(f"Experiment: {args.num}", flush=True)

    if args.cross_judge:
        exit_code = cross_judge_experiment(
            args.num, agents, result_root, tmp_base
        )
        shutil.rmtree(tmp_base, ignore_errors=True)
        return exit_code

    exit_codes = []
    for i, agent in enumerate(agents, 1):
        print(f"\n=== Judging {i}/{len(agents)}: {agent} ===", flush=True)
        exit_codes.append(
            judge_agent(
                agent, args.num, result_root, tmp_base
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
