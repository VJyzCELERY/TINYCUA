"""Run fixture-driven coding experiments with deterministic evaluators."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import yaml


AGENTS = ("opencode", "hermes", "openclaw", "tinycua")
LOCAL_PYTHON_EVALUATOR_IMAGE = "tinycua-template-tinycua-base"
FIXTURE_ROOT = Path(__file__).with_name("experiment-fixtures") / "experiments-list"
WORKSPACE = "/workspace"
STATE_DIR = "/state"
EVALUATOR_RESULT_DIR = "/result"
DEFAULT_TIMEOUT_SECONDS = 14_400
TIMEOUT_EXIT_CODE = 124
SKIPPED_EVALUATOR_EXIT_CODE = 125
SECRET_ENV_NAME = re.compile(
    r"api.?key|password|token|secret|credential|auth|key", re.IGNORECASE
)
TOKEN_COUNT_NAME = re.compile(
    r"(?:input|output|total|reasoning|cached|cache_read|cache_write)_tokens?",
    re.IGNORECASE,
)
SECRET_ASSIGNMENT = re.compile(
    r"(?P<name>[\"']?[A-Za-z_][A-Za-z0-9_]*[\"']?)\s*"
    r"(?P<separator>=|:)\s*"
    r"(?P<value>\"[^\"\n]*\"|'[^'\n]*'|[^\s,;]+)"
)
SAFE_SUBMISSION_PATH = re.compile(
    r"[A-Za-z0-9][A-Za-z0-9._-]*(/[A-Za-z0-9][A-Za-z0-9._-]*)*"
)
DEPENDENCY_MANIFEST_NAMES = frozenset(("requirements.txt", "pyproject.toml"))
COMPOSE_VARIABLE = re.compile(
    r"\$(?:\{(?P<braced>[A-Za-z_][A-Za-z0-9_]*)(?P<operator>:-|-)?"
    r"(?P<default>[^}]*)\}|(?P<bare>[A-Za-z_][A-Za-z0-9_]*))"
)


def _is_secret_name(name: str) -> bool:
    """Distinguish credentials from non-secret token-count telemetry."""
    return not TOKEN_COUNT_NAME.fullmatch(name) and bool(SECRET_ENV_NAME.search(name))


@dataclass(frozen=True)
class Fixture:
    """A validated coding-task fixture."""

    name: str
    prompt: str
    eval_image: str
    eval_command: tuple[str, ...]
    root: Path
    dockerfile: Path
    submission_dependency_files: tuple[Path, ...] = ()
    submission_dockerfile: Path | None = None
    outcome_group: str = "coding"
    evaluator_dockerfile: Path | None = None
    entrypoint_manages_dependencies: bool = False


@dataclass(frozen=True)
class ScoreCategory:
    """One evaluator-scored category with observable evidence."""

    points: int | float
    max_points: int | float
    evidence: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        """Serialize this category for a portable pair result."""
        return {
            "points": self.points,
            "max_points": self.max_points,
            "evidence": list(self.evidence),
        }


@dataclass(frozen=True)
class Score:
    """A validated optional evaluator score."""

    categories: dict[str, ScoreCategory]
    total: int | float
    pass_threshold: int | float
    critical_categories: tuple[str, ...]
    metrics: dict[str, int | float] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        """Return whether the threshold and every critical check pass."""
        return self.total >= self.pass_threshold and all(
            self.categories[name].points == self.categories[name].max_points
            and self.categories[name].evidence
            for name in self.critical_categories
        )

    def as_dict(self) -> dict[str, object]:
        """Serialize the score using the evaluator score-file protocol."""
        result = {
            "categories": {
                name: category.as_dict() for name, category in self.categories.items()
            },
            "total": self.total,
            "pass_threshold": self.pass_threshold,
            "critical_categories": list(self.critical_categories),
        }
        if self.metrics:
            result["metrics"] = self.metrics
        return result


def _score_number(value: object, field: str) -> int | float:
    """Return one finite non-boolean JSON number."""
    if (
        isinstance(value, bool)
        or not isinstance(value, int | float)
        or not math.isfinite(value)
    ):
        raise ValueError(f"score {field} must be a finite number")
    return value


def parse_score(data: object) -> Score:
    """Validate an evaluator's optional structured score file."""
    if not isinstance(data, dict):
        raise ValueError("score must be a JSON object")
    required = {"categories", "total", "pass_threshold", "critical_categories"}
    if set(data) not in (required, required | {"metrics"}):
        raise ValueError(
            "score must contain categories, total, pass_threshold, critical_categories, and optional metrics"
        )
    raw_categories = data["categories"]
    if not isinstance(raw_categories, dict) or not raw_categories:
        raise ValueError("score categories must be a non-empty object")
    categories: dict[str, ScoreCategory] = {}
    for name, raw_category in raw_categories.items():
        if not isinstance(name, str) or not name.strip():
            raise ValueError("score category names must be non-empty strings")
        if not isinstance(raw_category, dict) or set(raw_category) != {
            "points",
            "max_points",
            "evidence",
        }:
            raise ValueError(
                f"score category {name} must contain points, max_points, and evidence"
            )
        points = _score_number(raw_category["points"], f"category {name} points")
        max_points = _score_number(
            raw_category["max_points"], f"category {name} max_points"
        )
        if points < 0 or max_points <= 0 or points > max_points:
            raise ValueError(
                f"score category {name} points must be between zero and max_points"
            )
        raw_evidence = raw_category["evidence"]
        if not isinstance(raw_evidence, list) or any(
            not isinstance(item, str) or not item.strip() for item in raw_evidence
        ):
            raise ValueError(
                f"score category {name} evidence must be a list of non-empty strings"
            )
        categories[name] = ScoreCategory(points, max_points, tuple(raw_evidence))
    total = _score_number(data["total"], "total")
    maximum = math.fsum(category.max_points for category in categories.values())
    if total < 0 or not math.isclose(
        total, math.fsum(category.points for category in categories.values())
    ):
        raise ValueError("score total must equal the sum of category points")
    pass_threshold = _score_number(data["pass_threshold"], "pass_threshold")
    if pass_threshold < 0 or pass_threshold > maximum:
        raise ValueError(
            "score pass_threshold must be between zero and the maximum points"
        )
    raw_critical_categories = data["critical_categories"]
    if (
        not isinstance(raw_critical_categories, list)
        or len(set(raw_critical_categories)) != len(raw_critical_categories)
        or any(
            not isinstance(name, str) or name not in categories
            for name in raw_critical_categories
        )
    ):
        raise ValueError("score critical_categories must name unique categories")
    raw_metrics = data.get("metrics", {})
    if not isinstance(raw_metrics, dict) or any(
        not isinstance(name, str)
        or not name.strip()
        or isinstance(value, bool)
        or not isinstance(value, int | float)
        or not math.isfinite(value)
        for name, value in raw_metrics.items()
    ):
        raise ValueError("score metrics must map non-empty names to finite numbers")
    return Score(
        categories,
        total,
        pass_threshold,
        tuple(raw_critical_categories),
        raw_metrics,
    )


def read_score(path: Path) -> Score | None:
    """Read the optional evaluator score from its dedicated result mount."""
    if not path.is_file():
        return None
    try:
        return parse_score(json.loads(path.read_text()))
    except (OSError, json.JSONDecodeError, ValueError) as error:
        raise ValueError(f"invalid evaluator score: {error}") from error


def parse_agents(raw: str | None) -> tuple[str, ...]:
    """Parse selected existing harness names."""
    if raw is None:
        return AGENTS
    agents = tuple(item.strip() for item in raw.split(",") if item.strip())
    if not agents:
        raise ValueError("agents must not be empty")
    if len(set(agents)) != len(agents):
        raise ValueError("duplicate agents are not allowed")
    unknown = [agent for agent in agents if agent not in AGENTS]
    if unknown:
        raise ValueError(f"unknown agent(s): {', '.join(unknown)}")
    return agents


def evaluator_base_agents(
    fixtures: tuple[Fixture, ...], agents: tuple[str, ...]
) -> tuple[str, ...]:
    """Include the local Python evaluator base when a fixture needs it."""
    if "tinycua" not in agents and any(
        fixture.eval_image == LOCAL_PYTHON_EVALUATOR_IMAGE
        or fixture.evaluator_dockerfile is not None
        for fixture in fixtures
    ):
        return (*agents, "tinycua")
    return agents


def _selected_names(root: Path, raw: str | None) -> tuple[str, ...]:
    """Validate fixture selectors before filesystem or Docker work."""
    available = tuple(sorted(path.name for path in root.iterdir() if path.is_dir()))
    if raw is None:
        if not available:
            raise ValueError("no fixtures found")
        return available
    names = tuple(item.strip() for item in raw.split(",") if item.strip())
    if not names:
        raise ValueError("fixtures must not be empty")
    if len(set(names)) != len(names):
        raise ValueError("duplicate fixtures are not allowed")
    for name in names:
        if Path(name).name != name or name not in available:
            raise ValueError(f"unknown fixture: {name}")
    return names


def _submission_path(value: object, field: str, fixture: str) -> Path:
    """Validate one manifest path relative to the copied submission."""
    if not isinstance(value, str) or not SAFE_SUBMISSION_PATH.fullmatch(value):
        raise ValueError(f"fixture {fixture} {field} must be a safe relative path")
    return Path(value)


def _declared_submission_dependency_files(
    data: dict[object, object], fixture: str
) -> tuple[Path, ...]:
    """Return approved nested submission manifests in deterministic order."""
    field = "submission_dependency_files"
    if field not in data:
        return ()
    values = data[field]
    if not isinstance(values, list):
        raise ValueError(f"fixture {fixture} {field} must be a list")
    paths = tuple(_submission_path(value, field, fixture) for value in values)
    if len(set(paths)) != len(paths):
        raise ValueError(f"fixture {fixture} {field} must not contain duplicates")
    if any(path.parent == Path(".") for path in paths):
        raise ValueError(f"fixture {fixture} {field} must contain nested paths")
    if any(path.name not in DEPENDENCY_MANIFEST_NAMES for path in paths):
        raise ValueError(
            f"fixture {fixture} {field} entries must name requirements.txt or pyproject.toml"
        )
    return tuple(sorted(paths))


def _submission_dockerfile(data: dict[object, object], fixture: str) -> Path | None:
    """Return the optional Dockerfile path relative to the copied submission."""
    field = "submission_dockerfile"
    return _submission_path(data[field], field, fixture) if field in data else None


def _entrypoint_manages_dependencies(
    data: dict[object, object], fixture: str
) -> bool:
    """Return whether a free-form submission owns its dependency setup."""
    field = "entrypoint_manages_dependencies"
    value = data.get(field, False)
    if not isinstance(value, bool):
        raise ValueError(f"fixture {fixture} {field} must be a boolean")
    return value


def _validated_dockerfile(path: Path, description: str) -> None:
    """Require a decorator Dockerfile with the shared base-image contract."""
    if not path.is_file():
        raise ValueError(f"{description} does not exist: {path}")
    lines = [line.strip() for line in path.read_text().splitlines() if line.strip()]
    if lines[:2] != ["ARG BASE_IMAGE", "FROM ${BASE_IMAGE}"]:
        raise ValueError(f"{description} must start with ARG BASE_IMAGE")


def _load_fixture(root: Path, name: str) -> Fixture:
    """Validate one fixture's required files and manifest."""
    fixture = root / name
    manifest = fixture / "manifest.yaml"
    required = (manifest, fixture / "workdir", fixture / "eval")
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise ValueError(f"fixture {name} is missing: {', '.join(missing)}")
    if not (fixture / "workdir").is_dir() or not (fixture / "eval").is_dir():
        raise ValueError(f"fixture {name} workdir and eval must be directories")
    try:
        data = yaml.safe_load(manifest.read_text())
    except yaml.YAMLError as error:
        raise ValueError(f"invalid manifest for {name}: {error}") from error
    if not isinstance(data, dict):
        raise ValueError(f"fixture {name} manifest must be a mapping")
    prompt = data.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError(f"fixture {name} prompt must be a non-empty string")
    eval_image = data.get("eval_image")
    if not isinstance(eval_image, str) or not eval_image.strip():
        raise ValueError(f"fixture {name} eval_image must be a non-empty string")
    eval_command = data.get("eval_command")
    if (
        not isinstance(eval_command, list)
        or not eval_command
        or any(not isinstance(item, str) or not item.strip() for item in eval_command)
    ):
        raise ValueError(f"fixture {name} eval_command must be a non-empty string list")
    submission_dependency_files = _declared_submission_dependency_files(data, name)
    submission_dockerfile = _submission_dockerfile(data, name)
    entrypoint_manages_dependencies = _entrypoint_manages_dependencies(data, name)
    outcome_group = data.get("outcome_group", "coding")
    if outcome_group not in {"coding", "research", "conversation"}:
        raise ValueError(
            f"fixture {name} outcome_group must be coding, research, or conversation"
        )
    evaluator_dockerfile = None
    if "eval_dockerfile" in data:
        evaluator_dockerfile = fixture / _submission_path(
            data["eval_dockerfile"], "eval_dockerfile", name
        )
        _validated_dockerfile(
            evaluator_dockerfile, f"fixture {name} evaluator Dockerfile"
        )
    dockerfile = fixture / "docker" / "Dockerfile"
    if dockerfile.exists():
        _validated_dockerfile(dockerfile, f"fixture {name} Dockerfile")
    return Fixture(
        name,
        prompt,
        eval_image,
        tuple(eval_command),
        fixture,
        dockerfile,
        submission_dependency_files,
        submission_dockerfile,
        outcome_group,
        evaluator_dockerfile,
        entrypoint_manages_dependencies,
    )


def discover_fixtures(root: Path, raw: str | None = None) -> tuple[Fixture, ...]:
    """Discover and validate selected repository fixtures."""
    if not root.is_dir():
        raise ValueError(f"fixture root does not exist: {root}")
    return tuple(_load_fixture(root, name) for name in _selected_names(root, raw))


def state_volume_name(fixture: str, agent: str) -> str:
    """Return the inspectable volume name for one isolated pair."""
    return f"tinycua-template-{fixture.encode().hex()}-{agent.encode().hex()}"


def workspace_volume_name(fixture: str, agent: str) -> str:
    """Return the disposable live workspace volume for one pair."""
    return f"tinycua-template-workspace-{fixture.encode().hex()}-{agent.encode().hex()}"


def container_name(fixture: str, agent: str, role: str) -> str:
    """Return the deterministic Docker container name for one pair role."""
    return f"tinycua-template-{role}-{fixture.encode().hex()}-{agent.encode().hex()}"


def build_base_command(agent: str, image: str) -> list[str]:
    """Build one existing harness Dockerfile under a controlled tag."""
    return [
        "docker",
        "build",
        "--tag",
        image,
        "--file",
        f"docker/{agent}.Dockerfile",
        "../..",
    ]


def build_decorator_command(dockerfile: Path, base_image: str, image: str) -> list[str]:
    """Build the optional shared fixture layer on a harness base image."""
    return [
        "docker",
        "build",
        "--tag",
        image,
        "--build-arg",
        f"BASE_IMAGE={base_image}",
        "--file",
        str(dockerfile),
        str(dockerfile.parent),
    ]


def build_submission_command(dockerfile: Path, submission: Path) -> list[str]:
    """Build a copied submission from the host before evaluator execution."""
    return ["docker", "build", "--file", str(dockerfile), str(submission)]


def build_agent_command(
    compose_file: Path,
    override_file: Path,
    agent: str,
    prompt: str,
    workspace_volume: str,
    volume: str,
    name: str,
) -> list[str]:
    """Build a Compose command exposing isolated workspace and state volumes."""
    environment = _agent_environment(prompt)
    if agent == "opencode":
        environment.pop("HOME")
    return [
        "docker",
        "compose",
        "-f",
        str(compose_file),
        "-f",
        str(override_file),
        "run",
        "--rm",
        "--name",
        name,
        "-T",
        *[
            argument
            for name, value in environment.items()
            for argument in ("-e", f"{name}={value}")
        ],
        "-v",
        f"{workspace_volume}:{WORKSPACE}",
        *([] if agent == "opencode" else ["-v", f"{volume}:{STATE_DIR}"]),
        "--workdir",
        WORKSPACE,
        agent,
    ]


def _agent_environment(prompt: str) -> dict[str, str]:
    """Return the explicit environment passed to every agent Compose run."""
    return {
        "EXPERIMENT_PROMPT": prompt,
        "EXPERIMENT_WORKSPACE": WORKSPACE,
        "HOME": STATE_DIR,
    }


def _compose_env_file(env_file: Path) -> tuple[dict[str, str], dict[str, str]]:
    """Return raw and Compose-effective values from one env_file."""
    raw_environment: dict[str, str] = {}
    environment: dict[str, str] = {}
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            name, separator, value = line.removeprefix("export ").partition("=")
            if separator and name:
                name = name.strip()
                raw_environment[name] = value.strip()
                environment[name] = _compose_env_value(
                    raw_environment[name], environment
                )
    return raw_environment, environment


def _compose_env_value(value: str, environment: dict[str, str]) -> str:
    """Resolve the Compose env_file comment and interpolation forms we accept."""
    if value.startswith("'") and value.endswith("'"):
        return value[1:-1]
    if value.startswith('"') and value.endswith('"'):
        value = value[1:-1]
    else:
        value = re.split(r"\s+#", value, maxsplit=1)[0].rstrip()

    def replace(match: re.Match[str]) -> str:
        name = match["braced"] or match["bare"]
        resolved = environment.get(name, os.environ.get(name))
        if match["operator"] == ":-":
            return resolved or match["default"]
        if match["operator"] == "-":
            return resolved if resolved is not None else match["default"]
        return resolved or ""

    return COMPOSE_VARIABLE.sub(replace, value)


def _agent_compose_environments(
    env_file: Path, prompt: str
) -> tuple[dict[str, str], dict[str, str]]:
    """Build raw and effective environments for an agent Compose service."""
    raw_environment, environment = _compose_env_file(env_file)
    searxng_url = (
        environment.get("EXPERIMENT_SEARXNG_BASE_URL") or "http://searxng:8080"
    )
    environment.update(
        {
            "SEARXNG_URL": searxng_url,
            "SEARXNG_BASE_URL": searxng_url,
            "TINYCUA_SEARXNG_URL": environment.get("TINYCUA_SEARXNG_URL")
            or "http://searxng:8080/search",
        }
    )
    environment.update(_agent_environment(prompt))
    return raw_environment, environment


def agent_compose_environment(env_file: Path, prompt: str) -> dict[str, str]:
    """Build the environment visible to an agent Compose service."""
    _, environment = _agent_compose_environments(env_file, prompt)
    return environment


def build_evaluator_command(
    image: str,
    eval_command: tuple[str, ...],
    submission: Path,
    evaluator: Path,
    name: str,
    submission_dependency_files: tuple[Path, ...] = (),
    agent_stdout: Path | None = None,
    result_directory: Path | None = None,
    install_submission_dependencies: bool = True,
) -> list[str]:
    """Build the separate read-only evaluator container command."""
    command = [
        "docker",
        "run",
        "--rm",
        "--name",
        name,
        "-v",
        f"{submission.resolve()}:/submission:ro",
        "-v",
        f"{evaluator.resolve()}:/eval:ro",
    ]
    if result_directory is not None:
        command.extend(["-v", f"{result_directory.resolve()}:{EVALUATOR_RESULT_DIR}"])
    if agent_stdout is not None:
        command.extend(
            ["-v", f"{agent_stdout.resolve()}:/agent-output/agent.stdout.log:ro"]
        )
    command.append(image)
    submission_manifests = (
        tuple(
            manifest
            for manifest in (Path("requirements.txt"), *submission_dependency_files)
            if manifest.name == "requirements.txt"
        )
        if install_submission_dependencies
        else ()
    )
    manifests = (
        *(submission / manifest for manifest in submission_manifests),
        evaluator / "requirements.txt",
        evaluator / "pyproject.toml",
    )
    if not any(manifest.is_file() for manifest in manifests):
        return [*command, *eval_command]
    install_dependencies = (
        """set -eu
python_bin="$(command -v python || command -v python3 || true)"
if [ -z "$python_bin" ]; then
  echo "Evaluator dependency installation requires Python, but neither python or python3 is available." >&2
  exit 127
fi
if ! "$python_bin" -m pip --version >/dev/null 2>&1; then
  echo "Evaluator dependency installation requires pip, but python -m pip is unavailable." >&2
  exit 127
fi
"""
        + "".join(
            f"if [ -f /submission/{manifest.as_posix()} ]; then\n"
            f'  "$python_bin" -m pip install -r '
            f"/submission/{manifest.as_posix()}\n"
            "fi\n"
            for manifest in submission_manifests
        )
        + """
if [ -f /eval/requirements.txt ]; then
  "$python_bin" -m pip install -r /eval/requirements.txt
fi
if [ -f /eval/pyproject.toml ]; then
  "$python_bin" -m pip install /eval
fi
exec "$@"
"""
    )
    return [*command, "sh", "-c", install_dependencies, "evaluator", *eval_command]


def _existing_submission_dependency_files(
    submission: Path, declared: tuple[Path, ...]
) -> tuple[Path, ...]:
    """Reject nested manifests unless this fixture explicitly declared them."""
    nested_paths = []
    for path in submission.rglob("*"):
        relative = path.relative_to(submission)
        if ".venv" in relative.parts or path.name not in DEPENDENCY_MANIFEST_NAMES:
            continue
        if path.is_file() and relative.parent != Path("."):
            nested_paths.append(relative)
    nested = tuple(sorted(nested_paths))
    undeclared = tuple(path for path in nested if path not in declared)
    if undeclared:
        paths = ", ".join(path.as_posix() for path in undeclared)
        raise ValueError(
            "undeclared nested submission dependency manifest(s): "
            f"{paths}; declare them in submission_dependency_files"
        )
    return tuple(path for path in declared if (submission / path).is_file())


def write_result(
    path: Path,
    fixture: str,
    agent: str,
    volume: str,
    started_at: datetime,
    ended_at: datetime,
    elapsed_prompt_to_finish_seconds: float,
    agent_exit_code: int,
    evaluator_exit_code: int,
    stdout: Path,
    stderr: Path,
    environment: dict[str, str],
    score: Score | None = None,
    score_error: str | None = None,
) -> None:
    """Write portable, sanitized evidence and outcome for one pair."""
    snapshot = path.with_name("container_environment.json")
    secret_values = _secret_values(environment)
    snapshot.write_text(
        json.dumps(
            {
                name: "[REDACTED]"
                if _is_secret_name(name)
                else _redact_output(value, secret_values)
                for name, value in sorted(environment.items())
            },
            indent=2,
        )
        + "\n"
    )
    passed = (
        evaluator_exit_code == 0
        and score_error is None
        and (score is None or score.passed)
    )
    result: dict[str, object] = {
        "fixture": fixture,
        "agent": agent,
        "state_volume": volume,
        "started_at": started_at.isoformat(),
        "ended_at": ended_at.isoformat(),
        "elapsed_prompt_to_finish_seconds": elapsed_prompt_to_finish_seconds,
        "stdout_path": str(stdout.relative_to(path.parent)),
        "stderr_path": str(stderr.relative_to(path.parent)),
        "agent_exit_code": agent_exit_code,
        "sanitized_environment": str(snapshot.relative_to(path.parent)),
        "evaluator_exit_code": evaluator_exit_code,
        "evaluator_outcome": "passed" if passed else "failed",
        "passed": passed,
    }
    if score is not None:
        result["score"] = score.as_dict()
    if score_error is not None:
        result["score_error"] = score_error
    path.write_text(json.dumps(result, indent=2) + "\n")


def _captured_text(value: str | bytes | None) -> str:
    """Normalize subprocess output retained after a timeout."""
    return value.decode(errors="replace") if isinstance(value, bytes) else value or ""


def _secret_values(*environments: dict[str, str]) -> tuple[str, ...]:
    """Return configured secret values longest-first for literal redaction."""
    return tuple(
        sorted(
            (
                value
                for environment in environments
                for name, value in environment.items()
                if _is_secret_name(name) and value
            ),
            key=len,
            reverse=True,
        )
    )


def _redact_output(text: str, secret_values: tuple[str, ...]) -> str:
    """Redact configured secrets and sensitive assignments from retained output."""
    for value in secret_values:
        text = text.replace(value, "[REDACTED]")

    def redact_assignment(match: re.Match[str]) -> str:
        if _is_secret_name(match["name"].strip("\"'")):
            return f"{match['name']}{match['separator']}[REDACTED]"
        return match[0]

    return SECRET_ASSIGNMENT.sub(redact_assignment, text)


def _remove_container(name: str, timeout_seconds: int) -> str | None:
    """Force-remove a timed-out container and confirm it is gone."""
    try:
        removed = subprocess.run(
            ["docker", "rm", "--force", name],
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        return f"Container cleanup timed out removing {name}"
    if removed.returncode:
        return f"Container cleanup failed removing {name}"
    try:
        present = subprocess.run(
            [
                "docker",
                "container",
                "ls",
                "--all",
                "--filter",
                f"name=^/{name}$",
                "--format",
                "{{.Names}}",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        return f"Container cleanup timed out verifying removal of {name}"
    if present.returncode:
        return f"Container cleanup failed verifying removal of {name}"
    if name in present.stdout.splitlines():
        return f"Container cleanup failed: {name} is still present"
    return None


def _run(
    command: list[str],
    stdout: Path,
    stderr: Path,
    timeout_seconds: int,
    secret_values: tuple[str, ...] = (),
    name: str | None = None,
) -> tuple[int, str | None]:
    """Run one Docker command and retain its diagnostics."""
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            stdin=subprocess.DEVNULL,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as error:
        cleanup_error = (
            _remove_container(name, timeout_seconds) if name is not None else None
        )
        cleanup_message = f"{cleanup_error}\n" if cleanup_error else ""
        stdout.write_text(_redact_output(_captured_text(error.stdout), secret_values))
        stderr.write_text(
            f"{_redact_output(_captured_text(error.stderr), secret_values)}"
            f"Timed out after {timeout_seconds} seconds\n"
            f"{cleanup_message}"
        )
        return TIMEOUT_EXIT_CODE, cleanup_error
    stdout.write_text(_redact_output(result.stdout, secret_values))
    stderr.write_text(_redact_output(result.stderr, secret_values))
    return result.returncode, None


def _transfer_volume(
    image: str,
    volume: str,
    container: str,
    copy_source: str,
    copy_destination: str,
    log_root: Path,
    operation: str,
    timeout_seconds: int,
    secret_values: tuple[str, ...],
) -> str | None:
    """Copy data through a stopped volume-mounted container without host mounts."""

    def logs(step: str) -> tuple[Path, Path]:
        return (
            log_root / f"workspace-{operation}-{step}.stdout.log",
            log_root / f"workspace-{operation}-{step}.stderr.log",
        )

    create_stdout, create_stderr = logs("create")
    code, _ = _run(
        [
            "docker",
            "create",
            "--name",
            container,
            "-v",
            f"{volume}:{WORKSPACE}",
            image,
            "true",
        ],
        create_stdout,
        create_stderr,
        timeout_seconds,
        secret_values,
        container,
    )
    if code:
        return f"workspace {operation} setup failed with exit code {code}"
    copy_stdout, copy_stderr = logs("copy")
    code, _ = _run(
        ["docker", "cp", copy_source, copy_destination],
        copy_stdout,
        copy_stderr,
        timeout_seconds,
        secret_values,
        container,
    )
    remove_stdout, remove_stderr = logs("remove")
    remove_code, _ = _run(
        ["docker", "rm", "--force", container],
        remove_stdout,
        remove_stderr,
        timeout_seconds,
        secret_values,
    )
    if code:
        return f"workspace {operation} copy failed with exit code {code}"
    if remove_code:
        return f"workspace {operation} cleanup failed with exit code {remove_code}"
    return None


def _seed_workspace_volume(
    seed: Path,
    volume: str,
    image: str,
    container: str,
    log_root: Path,
    timeout_seconds: int,
    secret_values: tuple[str, ...],
) -> str | None:
    """Seed one live workspace volume from an immutable fixture tree."""
    return _transfer_volume(
        image,
        volume,
        container,
        f"{seed.resolve()}/.",
        f"{container}:{WORKSPACE}",
        log_root,
        "seed",
        timeout_seconds,
        secret_values,
    )


def _export_workspace_volume(
    volume: str,
    image: str,
    container: str,
    destination: Path,
    log_root: Path,
    timeout_seconds: int,
    secret_values: tuple[str, ...],
) -> str | None:
    """Export a completed workspace volume to host-owned result artifacts."""
    staging = destination.with_name(f".{destination.name}-export")
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)
    error = _transfer_volume(
        image,
        volume,
        container,
        f"{container}:{WORKSPACE}/.",
        str(staging),
        log_root,
        "export",
        timeout_seconds,
        secret_values,
    )
    if error:
        shutil.rmtree(staging, ignore_errors=True)
        return error
    shutil.rmtree(destination, ignore_errors=True)
    staging.replace(destination)
    return None


def _remove_workspace_volume(name: str, timeout_seconds: int) -> str | None:
    """Remove one disposable workspace volume after its artifacts are exported."""
    try:
        removed = subprocess.run(
            ["docker", "volume", "rm", "--force", name],
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        return f"workspace volume cleanup timed out removing {name}"
    if removed.returncode and "No such volume" not in removed.stderr:
        return f"workspace volume cleanup failed removing {name}"
    return None


def _write_override(path: Path, agent: str, image: str) -> None:
    """Point one unchanged Compose service at the selected built image."""
    path.write_text(f"services:\n  {agent}:\n    build: null\n    image: {image}\n")


def _prepare_output(
    root: Path, fixtures: tuple[Fixture, ...], agents: tuple[str, ...], overwrite: bool
) -> None:
    """Reject existing evidence unless its replacement was explicitly requested."""
    existing = [root / fixture.name / agent for fixture in fixtures for agent in agents]
    occupied = next((path for path in existing if path.exists()), None)
    if occupied and not overwrite:
        raise FileExistsError(f"output exists; rerun with --overwrite: {occupied}")
    if overwrite:
        for path in existing:
            shutil.rmtree(path, ignore_errors=True)


def _reset_state_volumes(
    fixtures: tuple[Fixture, ...], agents: tuple[str, ...], timeout_seconds: int
) -> None:
    """Reset stateful harnesses selected for an explicit overwrite."""
    for fixture in fixtures:
        for agent in agents:
            if agent == "opencode":
                continue
            volume = state_volume_name(fixture.name, agent)
            try:
                removed = subprocess.run(
                    ["docker", "volume", "rm", "--force", volume],
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=timeout_seconds,
                )
            except subprocess.TimeoutExpired as error:
                raise OSError(f"timed out resetting state volume {volume}") from error
            if removed.returncode and "No such volume" not in removed.stderr:
                raise OSError(f"failed resetting state volume {volume}")


def _restart_searxng(timeout_seconds: int = 30) -> None:
    """Restart SearXNG once per runner invocation for a clean container state.

    Best-effort: a failure logs a warning and continues so infra never blocks
    a run. # ponytail: a shared public-IP block could still starve results after
    the restart; add a query cache or external proxy if engine rate limits
    persist across restarts.
    """
    try:
        subprocess.run(
            ["docker", "compose", "restart", "searxng"],
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        print("WARNING: searxng restart timed out; continuing", flush=True)
        return
    print("[searxng] restarted for this run", flush=True)


def tree_revision(root: Path) -> str:
    """Return a deterministic SHA-256 revision for one file tree."""
    digest = hashlib.sha256()
    for path in sorted(path for path in root.rglob("*") if path.is_file()):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _image_identity(image: str) -> dict[str, object]:
    """Return the immutable local ID and available registry digests for an image."""
    completed = subprocess.run(
        ["docker", "image", "inspect", image, "--format", "{{json .}}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode or not completed.stdout.strip():
        return {"reference": image, "id": None, "repo_digests": []}
    data = json.loads(completed.stdout)
    return {
        "reference": image,
        "id": data.get("Id"),
        "repo_digests": data.get("RepoDigests") or [],
    }


def _git_value(*arguments: str) -> str:
    """Return one required Git value for run provenance."""
    return subprocess.run(
        ["git", *arguments],
        capture_output=True,
        text=True,
        check=True,
        cwd=Path(__file__).resolve().parent,
    ).stdout.strip()


def write_run_metadata(
    path: Path,
    fixtures: tuple[Fixture, ...],
    agents: tuple[str, ...],
    base_images: dict[str, str],
    timeout_seconds: int,
    overwrite: bool,
    environment: dict[str, str],
) -> None:
    """Freeze the configuration and revisions used to generate one controlled run."""
    evaluator_images = sorted({fixture.eval_image for fixture in fixtures})
    model_settings = {
        name: value
        for name, value in sorted(environment.items())
        if any(
            marker in name
            for marker in (
                "MODEL",
                "PROVIDER",
                "THINKING",
                "MAX_CONTEXT",
                "MAX_TURNS",
                "TIMEOUT_SECONDS",
            )
        )
        and not _is_secret_name(name)
    }
    result_generation_commit = _git_value("rev-parse", "HEAD")
    metadata = {
        "result_generation_commit": result_generation_commit,
        "working_tree_dirty": bool(_git_value("status", "--porcelain")),
        "selected_fixtures": [fixture.name for fixture in fixtures],
        "selected_agents": list(agents),
        "fixtures": {
            fixture.name: {
                "outcome_group": fixture.outcome_group,
                "fixture_revision": tree_revision(fixture.root),
                "evaluator_revision": tree_revision(fixture.root / "eval"),
            }
            for fixture in fixtures
        },
        "images": {
            "harnesses": {
                agent: _image_identity(image) for agent, image in base_images.items()
            },
            "evaluators": {image: _image_identity(image) for image in evaluator_images},
            "candidates": {},
        },
        "harness_versions": {
            "opencode": "opencode-ai@1.18.4",
            "hermes": "hermes-agent==0.16.0",
            "openclaw": "openclaw@2026.7.1-2",
            "tinycua": result_generation_commit,
        },
        "model_settings": model_settings,
        "sampling_settings": {
            "temperature": environment.get("EXPERIMENT_TEMPERATURE"),
            "top_p": environment.get("EXPERIMENT_TOP_P"),
            "seed": environment.get("EXPERIMENT_SEED"),
        },
        "timeout_seconds": timeout_seconds,
        "trial_policy": {
            "pass_at_k": 1,
            "trials_per_pair": 1,
            "retries": 0,
            "execution_order": "sequential",
        },
        "overwrite": overwrite,
        "state_reset_on_overwrite": overwrite,
    }
    path.write_text(json.dumps(metadata, indent=2) + "\n")


def record_candidate_image(path: Path, fixture: str, agent: str, image: str) -> None:
    """Record one final candidate image before its agent starts."""
    metadata = json.loads(path.read_text())
    candidates = metadata["images"]["candidates"]
    candidates.setdefault(fixture, {})[agent] = _image_identity(image)
    path.write_text(json.dumps(metadata, indent=2) + "\n")


def write_outcomes(
    path: Path,
    output_root: Path,
    fixtures: tuple[Fixture, ...],
    agents: tuple[str, ...],
) -> None:
    """Report per-task outcomes in separate non-comparable task groups."""
    outcomes: dict[str, dict[str, dict[str, object]]] = {
        "coding": {},
        "research": {},
        "conversation": {},
    }
    for fixture in fixtures:
        fixture_outcomes: dict[str, object] = {}
        for agent in agents:
            result_path = output_root / fixture.name / agent / "result.json"
            if result_path.is_file():
                result = json.loads(result_path.read_text())
                score = result.get("score")
                fixture_outcomes[agent] = {
                    "passed": result["passed"],
                    "score": score["total"] if isinstance(score, dict) else None,
                    "metrics": score.get("metrics", {})
                    if isinstance(score, dict)
                    else {},
                }
        outcomes[fixture.outcome_group][fixture.name] = fixture_outcomes
    path.write_text(json.dumps(outcomes, indent=2) + "\n")


def run_experiments(
    fixtures: tuple[Fixture, ...],
    agents: tuple[str, ...],
    output_root: Path,
    overwrite: bool,
    timeout_seconds: int,
) -> int:
    """Build selected harnesses and run every fixture/harness pair sequentially."""
    _prepare_output(output_root, fixtures, agents, overwrite)
    if overwrite:
        _reset_state_volumes(fixtures, agents, timeout_seconds)
    _restart_searxng(timeout_seconds)
    raw_environment, configured_environment = _agent_compose_environments(
        Path(".env"), ""
    )
    configured_secrets = _secret_values(raw_environment, configured_environment)
    base_images = {
        agent: f"tinycua-template-{agent}-base"
        for agent in evaluator_base_agents(fixtures, agents)
    }
    for agent, image in base_images.items():
        print(f"[build/{agent}] starting", flush=True)
        code, _ = _run(
            build_base_command(agent, image),
            output_root / f"{agent}-build.stdout.log",
            output_root / f"{agent}-build.stderr.log",
            timeout_seconds,
            configured_secrets,
        )
        if code:
            print(f"[build/{agent}] failed exit_code={code}", flush=True)
            return code
        print(f"[build/{agent}] complete", flush=True)

    built_evaluators: set[str] = set()
    for fixture in fixtures:
        if (
            fixture.evaluator_dockerfile is None
            or fixture.eval_image in built_evaluators
        ):
            continue
        print(f"[build/{fixture.eval_image}] starting", flush=True)
        code, _ = _run(
            build_decorator_command(
                fixture.evaluator_dockerfile,
                base_images["tinycua"],
                fixture.eval_image,
            ),
            output_root / f"{fixture.name}-evaluator-build.stdout.log",
            output_root / f"{fixture.name}-evaluator-build.stderr.log",
            timeout_seconds,
            configured_secrets,
        )
        if code:
            print(f"[build/{fixture.eval_image}] failed exit_code={code}", flush=True)
            return code
        built_evaluators.add(fixture.eval_image)
        print(f"[build/{fixture.eval_image}] complete", flush=True)

    write_run_metadata(
        output_root / "run_metadata.json",
        fixtures,
        agents,
        base_images,
        timeout_seconds,
        overwrite,
        configured_environment,
    )

    failed = False
    for fixture in fixtures:
        for agent in agents:
            print(f"[{fixture.name}/{agent}] starting", flush=True)
            run_root = output_root / fixture.name / agent
            submission = run_root / "workdir"
            run_root.mkdir(parents=True)
            image = base_images[agent]
            if fixture.dockerfile.exists():
                image = f"tinycua-template-{fixture.name}-{agent}"
                code, _ = _run(
                    build_decorator_command(
                        fixture.dockerfile, base_images[agent], image
                    ),
                    run_root / "build.stdout.log",
                    run_root / "build.stderr.log",
                    timeout_seconds,
                    configured_secrets,
                )
                if code:
                    failed = True
                    message = f"fixture image build failed exit_code={code}"
                    print(f"[{fixture.name}/{agent}] {message}", flush=True)
                    agent_stdout = run_root / "agent.stdout.log"
                    agent_stderr = run_root / "agent.stderr.log"
                    evaluator_stdout = run_root / "eval.stdout.log"
                    evaluator_stderr = run_root / "eval.stderr.log"
                    agent_stdout.write_text("")
                    agent_stderr.write_text(f"Agent skipped: {message}\n")
                    evaluator_stdout.write_text("")
                    evaluator_stderr.write_text(f"Evaluator skipped: {message}\n")
                    (run_root / "evaluator-result").mkdir()
                    _, agent_environment = _agent_compose_environments(
                        Path(".env"), fixture.prompt
                    )
                    timestamp = datetime.now(timezone.utc)
                    write_result(
                        run_root / "result.json",
                        fixture.name,
                        agent,
                        state_volume_name(fixture.name, agent),
                        timestamp,
                        timestamp,
                        0.0,
                        SKIPPED_EVALUATOR_EXIT_CODE,
                        SKIPPED_EVALUATOR_EXIT_CODE,
                        agent_stdout,
                        agent_stderr,
                        agent_environment,
                    )
                    continue
            override = run_root / "compose-image.yaml"
            _write_override(override, agent, image)
            record_candidate_image(
                output_root / "run_metadata.json", fixture.name, agent, image
            )
            volume = state_volume_name(fixture.name, agent)
            workspace = workspace_volume_name(fixture.name, agent)
            agent_stdout = run_root / "agent.stdout.log"
            agent_stderr = run_root / "agent.stderr.log"
            raw_environment, agent_environment = _agent_compose_environments(
                Path(".env"), fixture.prompt
            )
            secret_values = _secret_values(raw_environment, agent_environment)
            started_at = datetime.now(timezone.utc)
            started_time = time.monotonic()
            agent_name = container_name(fixture.name, agent, "agent")
            workspace_reset_error = _remove_workspace_volume(workspace, timeout_seconds)
            seed_error = workspace_reset_error or _seed_workspace_volume(
                fixture.root / "workdir",
                workspace,
                image,
                container_name(fixture.name, agent, "workspace-seed"),
                run_root,
                timeout_seconds,
                secret_values,
            )
            if seed_error:
                agent_code = SKIPPED_EVALUATOR_EXIT_CODE
                cleanup_error = seed_error
                agent_stdout.write_text("")
                agent_stderr.write_text(f"Agent skipped: {seed_error}\n")
            else:
                agent_code, cleanup_error = _run(
                    build_agent_command(
                        Path("docker-compose.yml"),
                        override,
                        agent,
                        fixture.prompt,
                        workspace,
                        volume,
                        agent_name,
                    ),
                    agent_stdout,
                    agent_stderr,
                    timeout_seconds,
                    secret_values,
                    agent_name,
                )
                if cleanup_error is None:
                    cleanup_error = _export_workspace_volume(
                        workspace,
                        image,
                        container_name(fixture.name, agent, "workspace-export"),
                        submission,
                        run_root,
                        timeout_seconds,
                        secret_values,
                    )
            ended_at = datetime.now(timezone.utc)
            elapsed_prompt_to_finish_seconds = time.monotonic() - started_time
            print(
                f"[{fixture.name}/{agent}] agent exit_code={agent_code} "
                f"duration={elapsed_prompt_to_finish_seconds:.1f}s",
                flush=True,
            )
            evaluator_name = container_name(fixture.name, agent, "evaluator")
            evaluator_stdout = run_root / "eval.stdout.log"
            evaluator_stderr = run_root / "eval.stderr.log"
            evaluator_result = run_root / "evaluator-result"
            evaluator_result.mkdir()
            if cleanup_error:
                evaluator_code = SKIPPED_EVALUATOR_EXIT_CODE
                evaluator_stdout.write_text("")
                evaluator_stderr.write_text(f"Evaluator skipped: {cleanup_error}\n")
            else:
                try:
                    dependency_files = (
                        ()
                        if fixture.entrypoint_manages_dependencies
                        else _existing_submission_dependency_files(
                            submission, fixture.submission_dependency_files
                        )
                    )
                except ValueError as error:
                    evaluator_code = SKIPPED_EVALUATOR_EXIT_CODE
                    evaluator_stdout.write_text("")
                    evaluator_stderr.write_text(f"Evaluator setup failed: {error}\n")
                else:
                    if fixture.submission_dockerfile is not None:
                        build_code, _ = _run(
                            build_submission_command(
                                submission / fixture.submission_dockerfile, submission
                            ),
                            run_root / "submission-build.stdout.log",
                            run_root / "submission-build.stderr.log",
                            timeout_seconds,
                            secret_values,
                        )
                        if build_code:
                            evaluator_code = SKIPPED_EVALUATOR_EXIT_CODE
                            evaluator_stdout.write_text("")
                            evaluator_stderr.write_text(
                                "Evaluator skipped: submission Docker build failed "
                                f"with exit code {build_code}\n"
                            )
                        else:
                            evaluator_code, cleanup_error = _run(
                                build_evaluator_command(
                                    fixture.eval_image,
                                    fixture.eval_command,
                                    submission,
                                    fixture.root / "eval",
                                    evaluator_name,
                                    dependency_files,
                                    agent_stdout,
                                    evaluator_result,
                                    not fixture.entrypoint_manages_dependencies,
                                ),
                                evaluator_stdout,
                                evaluator_stderr,
                                timeout_seconds,
                                secret_values,
                                evaluator_name,
                            )
                    else:
                        evaluator_code, cleanup_error = _run(
                            build_evaluator_command(
                                fixture.eval_image,
                                fixture.eval_command,
                                submission,
                                fixture.root / "eval",
                                evaluator_name,
                                dependency_files,
                                agent_stdout,
                                evaluator_result,
                                not fixture.entrypoint_manages_dependencies,
                            ),
                            evaluator_stdout,
                            evaluator_stderr,
                            timeout_seconds,
                            secret_values,
                            evaluator_name,
                        )
            score: Score | None = None
            score_error: str | None = None
            try:
                score = read_score(evaluator_result / "score.json")
            except ValueError as error:
                score_error = str(error)
                with evaluator_stderr.open("a") as stream:
                    stream.write(f"Evaluator score rejected: {error}\n")
            workspace_error = _remove_workspace_volume(workspace, timeout_seconds)
            if workspace_error:
                cleanup_error = cleanup_error or workspace_error
                with evaluator_stderr.open("a") as stream:
                    stream.write(f"Workspace cleanup failed: {workspace_error}\n")
            write_result(
                run_root / "result.json",
                fixture.name,
                agent,
                volume,
                started_at,
                ended_at,
                elapsed_prompt_to_finish_seconds,
                agent_code,
                evaluator_code,
                agent_stdout,
                agent_stderr,
                agent_environment,
                score,
                score_error,
            )
            if cleanup_error:
                write_outcomes(
                    output_root / "outcomes.json", output_root, fixtures, agents
                )
                return 1
            failed = (
                failed
                or evaluator_code != 0
                or score_error is not None
                or (score is not None and not score.passed)
            )
            print(
                f"[{fixture.name}/{agent}] "
                f"{'passed' if evaluator_code == 0 and score_error is None and (score is None or score.passed) else 'failed'} "
                f"eval_exit_code={evaluator_code}",
                flush=True,
            )
    write_outcomes(output_root / "outcomes.json", output_root, fixtures, agents)
    return int(failed)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse controlled-runner selectors and output controls."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fixtures", help="Comma-separated fixture names (default: all)."
    )
    parser.add_argument(
        "--agents", help="Comma-separated harness names (default: all)."
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("template-results"),
        help="Result root (default: ./template-results).",
    )
    parser.add_argument(
        "--overwrite", action="store_true", help="Replace selected output directories."
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=f"Docker command deadline in seconds (default: {DEFAULT_TIMEOUT_SECONDS}).",
    )
    args = parser.parse_args(argv)
    if args.timeout_seconds < 1:
        parser.error("--timeout-seconds must be positive")
    return args


def main(argv: list[str] | None = None) -> int:
    """Run selected controlled coding experiments."""
    args = parse_args(argv)
    try:
        fixtures = discover_fixtures(FIXTURE_ROOT, args.fixtures)
        agents = parse_agents(args.agents)
        output_root = args.output_root.resolve()
        output_root.mkdir(parents=True, exist_ok=True)
        return run_experiments(
            fixtures, agents, output_root, args.overwrite, args.timeout_seconds
        )
    except (OSError, ValueError) as error:
        print(error, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
