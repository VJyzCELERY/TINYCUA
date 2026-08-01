"""Run fixture-driven coding experiments with deterministic evaluators."""

from __future__ import annotations

import argparse
import copy
import fcntl
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

import yaml


AGENTS = ("tinycua", "opencode", "hermes", "openclaw")
TINYCUA_VARIANTS = {
    "tinycua": (False, False),
    "tinycua-nr": (False, True),
    "tinycua-nd": (True, False),
    "tinycua-nd-nr": (True, True),
}
SUPPORTED_AGENTS = (*AGENTS, "tinycua-nr", "tinycua-nd", "tinycua-nd-nr")
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
SCHEMA_VERSION = 2
BUILDKIT_EVALUATOR_MIGRATION_REVISION = (
    "81eb29778cb601374d933eed8140ce0a24a9a07d13a4b57715abb56e08eca1af"
)
BUILDKIT_EVALUATOR_MIGRATION_ID = "fixture-scoped-evaluator-images-v1"
TRIAL_POLICY = {
    "pass_at_k": 1,
    "trials_per_pair": 1,
    "retries": 0,
    "execution_order": "sequential",
}
CONTROLLED_AGENT_SETTINGS = frozenset(
    {
        "EXPERIMENT_LLM_BASE_URL",
        "EXPERIMENT_LLM_MODEL",
        "EXPERIMENT_LLM_PROVIDER",
        "EXPERIMENT_OPENCODE_MODEL",
        "EXPERIMENT_HERMES_PROVIDER",
        "EXPERIMENT_HERMES_MAX_TURNS",
        "EXPERIMENT_HERMES_PROCESS_POLL_TIMEOUT_SECONDS",
        "EXPERIMENT_OPENCLAW_MODEL",
        "EXPERIMENT_OPENCLAW_THINKING",
        "EXPERIMENT_TINYCUA_PROVIDER_TYPE",
        "EXPERIMENT_TINYCUA_MAX_CONTEXT",
        "EXPERIMENT_TINYCUA_RECOVERY_STRATEGY",
        "EXPERIMENT_TIMEOUT_SECONDS",
        "EXPERIMENT_SEARXNG_BASE_URL",
        "SEARXNG_URL",
        "SEARXNG_BASE_URL",
        "TINYCUA_SEARXNG_URL",
    }
)
PRUNED_WORKDIR_DIRECTORIES = frozenset(
    {
        ".venv",
        "venv",
        "node_modules",
        "__pycache__",
        ".pytest_cache",
        ".agent_scripts",
        ".tinycua_context_cache",
        ".tinycua-artifacts",
        ".git",
    }
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
    unknown = [agent for agent in agents if agent not in SUPPORTED_AGENTS]
    if unknown:
        raise ValueError(f"unknown agent(s): {', '.join(unknown)}")
    return agents


def agent_service(agent: str) -> str:
    """Return the physical Compose service for one logical agent identity."""
    return "tinycua" if agent in TINYCUA_VARIANTS else agent


def tinycua_variant(agent: str) -> dict[str, bool]:
    """Return the two runtime ablation settings for a TinyCUA identity."""
    no_digest, no_review = TINYCUA_VARIANTS[agent]
    return {"no_digest": no_digest, "no_review": no_review}


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


def state_volume_name(
    fixture: str, agent: str, campaign_id: str | None = None
) -> str:
    """Return the inspectable volume name for one isolated pair."""
    namespace = f"-{campaign_id}" if campaign_id else ""
    return (
        f"tinycua-template{namespace}-{fixture.encode().hex()}-"
        f"{agent.encode().hex()}"
    )


def workspace_volume_name(
    fixture: str, agent: str, campaign_id: str | None = None
) -> str:
    """Return the disposable live workspace volume for one pair."""
    namespace = f"-{campaign_id}" if campaign_id else ""
    return (
        f"tinycua-template-workspace{namespace}-{fixture.encode().hex()}-"
        f"{agent.encode().hex()}"
    )


def container_name(
    fixture: str, agent: str, role: str, campaign_id: str | None = None
) -> str:
    """Return the deterministic Docker container name for one pair role."""
    namespace = f"-{campaign_id}" if campaign_id else ""
    return (
        f"tinycua-template-{role}{namespace}-{fixture.encode().hex()}-"
        f"{agent.encode().hex()}"
    )


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
        "--provenance=false",
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
    service = agent_service(agent)
    environment = _agent_environment(prompt, agent)
    if service == "opencode":
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
        *([] if service == "opencode" else ["-v", f"{volume}:{STATE_DIR}"]),
        "--workdir",
        WORKSPACE,
        service,
    ]


def _agent_environment(prompt: str, agent: str | None = None) -> dict[str, str]:
    """Return the explicit environment passed to every agent Compose run."""
    environment = {
        "EXPERIMENT_PROMPT": prompt,
        "EXPERIMENT_WORKSPACE": WORKSPACE,
        "HOME": STATE_DIR,
    }
    if agent in TINYCUA_VARIANTS:
        variant = tinycua_variant(agent)
        environment.update(
            {
                "EXPERIMENT_TINYCUA_NO_DIGEST": str(int(variant["no_digest"])),
                "EXPERIMENT_TINYCUA_NO_REVIEW": str(int(variant["no_review"])),
            }
        )
    return environment


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
    env_file: Path, prompt: str, agent: str | None = None
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
    environment.update(_agent_environment(prompt, agent))
    return raw_environment, environment


def agent_compose_environment(
    env_file: Path, prompt: str, agent: str | None = None
) -> dict[str, str]:
    """Build the environment visible to an agent Compose service."""
    _, environment = _agent_compose_environments(env_file, prompt, agent)
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
    submission_mount: str | None = None,
    evaluator_mount: str | None = None,
    agent_stdout_mount: str | None = None,
    result_mount: str | None = None,
) -> list[str]:
    """Build the separate read-only evaluator container command."""
    command = [
        "docker",
        "run",
        "--rm",
        "--name",
        name,
        "-v",
        f"{submission_mount or submission.resolve()}:/submission:ro",
        "-v",
        f"{evaluator_mount or evaluator.resolve()}:/eval:ro",
    ]
    if result_mount is not None or result_directory is not None:
        source = result_mount or str(result_directory.resolve())
        command.extend(["-v", f"{source}:{EVALUATOR_RESULT_DIR}"])
    if agent_stdout_mount is not None:
        command.extend(["-v", f"{agent_stdout_mount}:/agent-output:ro"])
    elif agent_stdout is not None:
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
    failure_stage: str | None = None,
) -> None:
    """Write portable, sanitized evidence and outcome for one pair."""
    snapshot = path.with_name("environment.json")
    secret_values = _secret_values(environment)
    _atomic_write_json(
        snapshot,
        {
            name: "[REDACTED]"
            if _is_secret_name(name)
            else _redact_output(value, secret_values)
            for name, value in sorted(environment.items())
        },
    )
    passed = (
        evaluator_exit_code == 0
        and score_error is None
        and (score is None or score.passed)
        and failure_stage is None
    )
    result: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "fixture": fixture,
        "agent": agent,
        "state_volume": volume,
        "started_at": started_at.isoformat(),
        "ended_at": ended_at.isoformat(),
        "elapsed_prompt_to_finish_seconds": elapsed_prompt_to_finish_seconds,
        "stdout_path": str(stdout.relative_to(path.parent)),
        "stderr_path": str(stderr.relative_to(path.parent)),
        "workdir_path": "workdir",
        "agent_exit_code": agent_exit_code,
        "sanitized_environment": str(snapshot.relative_to(path.parent)),
        "evaluator_exit_code": evaluator_exit_code,
        "evaluator_outcome": "passed" if passed else "failed",
        "passed": passed,
        "status": "passed" if passed else "failed",
    }
    if score is not None:
        result["score"] = score.as_dict()
    if score_error is not None:
        result["score_error"] = score_error
    if failure_stage is not None:
        result["failure_stage"] = failure_stage
    _atomic_write_json(path, result)


def apply_reevaluation(
    result: dict[str, object],
    *,
    evaluator_version: str,
    evaluator_fixture_revision: str,
    evaluator_image: dict[str, object],
    eval_command: tuple[str, ...],
    evaluator_exit_code: int,
    score: Score | None,
    score_error: str | None,
    failure_stage: str | None,
    evaluated_at: str,
) -> dict[str, object]:
    """Return a result updated with one versioned evaluator-only outcome."""
    updated = copy.deepcopy(result)
    if "original_evaluation" not in updated:
        updated["original_evaluation"] = {
            key: copy.deepcopy(updated[key])
            for key in (
                "score",
                "passed",
                "status",
                "evaluator_outcome",
                "evaluator_exit_code",
                "failure_stage",
                "score_error",
            )
            if key in updated
        }
    passed = (
        evaluator_exit_code == 0
        and score_error is None
        and (score is None or score.passed)
        and failure_stage is None
    )
    evaluation: dict[str, object] = {
        "evaluator_version": evaluator_version,
        "evaluator_fixture_revision": evaluator_fixture_revision,
        "evaluator_image": copy.deepcopy(evaluator_image),
        "eval_command": list(eval_command),
        "evaluated_at": evaluated_at,
        "evaluator_exit_code": evaluator_exit_code,
        "passed": passed,
        "status": "passed" if passed else "failed",
    }
    if score is not None:
        evaluation["score"] = score.as_dict()
    if score_error is not None:
        evaluation["score_error"] = score_error
    if failure_stage is not None:
        evaluation["failure_stage"] = failure_stage
    evaluations = updated.setdefault("evaluator_results", [])
    if not isinstance(evaluations, list):
        raise ValueError("result evaluator_results must be a list")
    if any(
        isinstance(item, dict) and item.get("evaluator_version") == evaluator_version
        for item in evaluations
    ):
        raise ValueError(f"evaluator version already recorded: {evaluator_version}")
    evaluations.append(evaluation)
    updated["evaluator_exit_code"] = evaluator_exit_code
    updated["passed"] = passed
    updated["status"] = evaluation["status"]
    updated["evaluator_outcome"] = evaluation["status"]
    if score is not None:
        updated["score"] = score.as_dict()
    else:
        updated.pop("score", None)
    if score_error is not None:
        updated["score_error"] = score_error
    else:
        updated.pop("score_error", None)
    if failure_stage is not None:
        updated["failure_stage"] = failure_stage
    else:
        updated.pop("failure_stage", None)
    return updated


def _atomic_write_json(path: Path, value: object) -> None:
    """Durably replace one JSON artifact without exposing a partial file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w") as stream:
            json.dump(value, stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        parent_descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(parent_descriptor)
        finally:
            os.close(parent_descriptor)
    finally:
        temporary.unlink(missing_ok=True)


def prune_workdir(workdir: Path) -> None:
    """Remove generated dependency and harness directories from a submission."""
    if not workdir.is_dir():
        return
    for root, directories, _files in os.walk(workdir):
        for name in tuple(directories):
            if name in PRUNED_WORKDIR_DIRECTORIES:
                shutil.rmtree(Path(root) / name, ignore_errors=True)
                directories.remove(name)


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
    stage: str | None = None,
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
        _write_log(
            stdout,
            _redact_output(_captured_text(error.stdout), secret_values),
            stage,
        )
        _write_log(
            stderr,
            f"{_redact_output(_captured_text(error.stderr), secret_values)}"
            f"Timed out after {timeout_seconds} seconds\n{cleanup_message}",
            stage,
        )
        return TIMEOUT_EXIT_CODE, cleanup_error
    _write_log(stdout, _redact_output(result.stdout, secret_values), stage)
    _write_log(stderr, _redact_output(result.stderr, secret_values), stage)
    return result.returncode, None


def _write_log(path: Path, text: str, stage: str | None = None) -> None:
    """Write one sanitized command stream, appending when it is consolidated."""
    mode = "a" if stage is not None else "w"
    with path.open(mode) as stream:
        if stage is not None:
            stream.write(f"=== {stage} ===\n")
        stream.write(text)
        if text and not text.endswith("\n"):
            stream.write("\n")


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

    stdout = log_root / "stdout.log"
    stderr = log_root / "stderr.log"
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
        stdout,
        stderr,
        timeout_seconds,
        secret_values,
        container,
        f"workspace/{operation}/create",
    )
    if code:
        return f"workspace {operation} setup failed with exit code {code}"
    code, _ = _run(
        ["docker", "cp", copy_source, copy_destination],
        stdout,
        stderr,
        timeout_seconds,
        secret_values,
        container,
        f"workspace/{operation}/copy",
    )
    remove_code, _ = _run(
        ["docker", "rm", "--force", container],
        stdout,
        stderr,
        timeout_seconds,
        secret_values,
        stage=f"workspace/{operation}/remove",
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
    except OSError as error:
        return f"workspace volume cleanup failed removing {name}: {error}"
    if removed.returncode and "No such volume" not in removed.stderr:
        return f"workspace volume cleanup failed removing {name}"
    return None


def _write_override(path: Path, agent: str, image: str) -> None:
    """Point one unchanged Compose service at the selected built image."""
    path.write_text(f"services:\n  {agent}:\n    build: null\n    image: {image}\n")


@contextmanager
def campaign_lock(root: Path):
    """Hold a Linux advisory lock on the result root without a lock artifact."""
    descriptor = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise OSError(f"campaign is already running: {root}") from error
        yield
    finally:
        os.close(descriptor)


def _remove_state_volume(name: str, timeout_seconds: int) -> str | None:
    """Remove one harness state volume before or after an actual pair."""
    try:
        removed = subprocess.run(
            ["docker", "volume", "rm", "--force", name],
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        return f"state volume cleanup timed out removing {name}"
    except OSError as error:
        return f"state volume cleanup failed removing {name}: {error}"
    if removed.returncode and "No such volume" not in removed.stderr:
        return f"state volume cleanup failed removing {name}"
    return None


def _ensure_searxng_ready(
    stdout: Path,
    stderr: Path,
    secret_values: tuple[str, ...],
) -> int:
    """Start SearXNG if needed and require healthy readiness."""
    code, _ = _run(
        [
            "docker",
            "compose",
            "up",
            "-d",
            "--wait",
            "searxng",
        ],
        stdout,
        stderr,
        60,
        secret_values,
        stage="service/searxng-ready",
    )
    return code


def tree_revision(root: Path) -> str:
    """Return a deterministic SHA-256 revision for one file tree."""
    digest = hashlib.sha256()
    for path in sorted(path for path in root.rglob("*") if path.is_file()):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _execution_revision() -> str:
    """Hash runner and Docker inputs that can change pair execution."""
    root = Path(__file__).resolve().parent
    digest = hashlib.sha256()
    for path in (Path(__file__).resolve(), root / "docker-compose.yml", root / "docker"):
        digest.update(path.name.encode())
        digest.update(
            tree_revision(path).encode() if path.is_dir() else path.read_bytes()
        )
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


def _model_settings(environment: dict[str, str]) -> dict[str, str]:
    """Return non-secret model and provider controls that freeze a campaign."""
    return {
        name: value
        for name, value in sorted(environment.items())
        if name in CONTROLLED_AGENT_SETTINGS
    }


def _fixture_record(fixture: Fixture) -> dict[str, str]:
    """Return the compatibility fields for one registered fixture."""
    return {
        "outcome_group": fixture.outcome_group,
        "fixture_revision": tree_revision(fixture.root),
        "evaluator_revision": tree_revision(fixture.root / "eval"),
    }


def _agent_configuration(agent: str) -> dict[str, object]:
    """Return the stable logical configuration for one agent identity."""
    configuration: dict[str, object] = {"service": agent_service(agent)}
    if agent in TINYCUA_VARIANTS:
        configuration.update(tinycua_variant(agent))
    return configuration


def _new_metadata(
    timeout_seconds: int, environment: dict[str, str]
) -> dict[str, object]:
    """Create the empty aggregate record for a controlled campaign."""
    result_generation_commit = _git_value("rev-parse", "HEAD")
    return {
        "schema_version": SCHEMA_VERSION,
        "campaign_id": str(uuid4()),
        "result_generation_commit": result_generation_commit,
        "result_generation_revision": _execution_revision(),
        "working_tree_dirty": bool(_git_value("status", "--porcelain")),
        "selected_fixtures": [],
        "selected_agents": [],
        "agent_configurations": {},
        "fixtures": {},
        "pairs": [],
        "pair_result_generation_revisions": {},
        "invocations": [],
        "images": {
            "harnesses": {},
            "evaluators": {},
            "decorators": {},
            "candidates": {},
        },
        "harness_versions": {
            "opencode": "opencode-ai@1.18.4",
            "hermes": "hermes-agent==0.16.0",
            "openclaw": "openclaw@2026.7.1-2",
            "tinycua": result_generation_commit,
        },
        "model_settings": _model_settings(environment),
        "sampling_settings": {
            "temperature": environment.get("EXPERIMENT_TEMPERATURE"),
            "top_p": environment.get("EXPERIMENT_TOP_P"),
            "seed": environment.get("EXPERIMENT_SEED"),
        },
        "timeout_seconds": timeout_seconds,
        "trial_policy": TRIAL_POLICY,
    }


def _register_invocation(
    metadata: dict[str, object],
    fixtures: tuple[Fixture, ...],
    agents: tuple[str, ...],
    overwrite: bool,
    order_by: str,
) -> None:
    """Aggregate selectors and append one compact invocation record."""
    fixture_records = metadata["fixtures"]
    agent_records = metadata["agent_configurations"]
    pairs = {
        (pair["fixture"], pair["agent"])
        for pair in metadata["pairs"]
    }
    for fixture in fixtures:
        fixture_records[fixture.name] = _fixture_record(fixture)
        pairs.update((fixture.name, agent) for agent in agents)
    for agent in agents:
        agent_records[agent] = _agent_configuration(agent)
    metadata["selected_fixtures"] = sorted(fixture_records)
    metadata["selected_agents"] = sorted(agent_records)
    metadata["pairs"] = [
        {"fixture": fixture, "agent": agent} for fixture, agent in sorted(pairs)
    ]
    started_at = datetime.now(timezone.utc).isoformat()
    for invocation in metadata["invocations"]:
        if "ended_at" not in invocation:
            invocation.update(
                {"ended_at": started_at, "status": "failed", "exit_code": 1}
            )
    metadata["invocations"].append(
        {
            "started_at": started_at,
            "fixtures": [fixture.name for fixture in fixtures],
            "agents": list(agents),
            "order_by": order_by,
            "overwrite": overwrite,
            "result_generation_revision": _execution_revision(),
        }
    )


def _finish_invocation(
    metadata_path: Path,
    metadata: dict[str, object],
    exit_code: int,
) -> None:
    """Record one registered invocation's terminal status."""
    invocation = metadata["invocations"][-1]
    invocation.update(
        {
            "ended_at": datetime.now(timezone.utc).isoformat(),
            "status": "passed" if exit_code == 0 else "failed",
            "exit_code": exit_code,
        }
    )
    _save_metadata(metadata_path, metadata)


def _pair_directories(output_root: Path) -> list[Path]:
    """Return campaign pair directories while excluding semantic verdicts."""
    return sorted(
        agent_root
        for fixture_root in output_root.iterdir()
        if fixture_root.is_dir()
        for agent_root in fixture_root.iterdir()
        if agent_root.is_dir()
        and agent_root.name != "cross_verdict"
        and not agent_root.name.startswith(".")
    )


def _safe_result_artifact(run_root: Path, value: object) -> Path | None:
    """Resolve a pair-relative result path without allowing traversal."""
    if not isinstance(value, str):
        return None
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        return None
    return run_root / relative


def _valid_pair_result(
    path: Path,
    expected_fixture: str | None = None,
    expected_agent: str | None = None,
) -> dict[str, object] | None:
    """Return a complete pair result, or None for an interrupted pair."""
    try:
        result = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(result, dict):
        return None
    run_root = path.parent
    expected_fixture = expected_fixture or run_root.parent.name
    expected_agent = expected_agent or run_root.name
    if (
        result.get("fixture") != expected_fixture
        or result.get("agent") != expected_agent
        or not isinstance(result.get("passed"), bool)
        or isinstance(result.get("agent_exit_code"), bool)
        or not isinstance(result.get("agent_exit_code"), int)
        or isinstance(result.get("evaluator_exit_code"), bool)
        or not isinstance(result.get("evaluator_exit_code"), int)
    ):
        return None
    schema_version = result.get("schema_version", 1)
    if schema_version not in (1, SCHEMA_VERSION):
        return None
    if schema_version == SCHEMA_VERSION and any(
        result.get(name) != expected
        for name, expected in (
            ("stdout_path", "stdout.log"),
            ("stderr_path", "stderr.log"),
            ("workdir_path", "workdir"),
            ("sanitized_environment", "environment.json"),
        )
    ):
        return None
    if schema_version == SCHEMA_VERSION and not _schema_v2_result_consistent(result):
        return None
    if not _pair_artifacts_complete(run_root, result):
        return None
    return result


def _pair_artifacts_complete(
    run_root: Path, result: dict[str, object]
) -> bool:
    """Validate required result paths and the sanitized environment JSON."""
    artifacts = {}
    for artifact_field, default in {
        "stdout_path": "agent.stdout.log",
        "stderr_path": "agent.stderr.log",
        "sanitized_environment": "container_environment.json",
    }.items():
        artifact = _safe_result_artifact(run_root, result.get(artifact_field, default))
        if artifact is None or not artifact.is_file():
            return False
        artifacts[artifact_field] = artifact
    workdir = _safe_result_artifact(
        run_root, result.get("workdir_path", "workdir")
    )
    legacy_failed_without_workdir = (
        result.get("schema_version", 1) == 1 and result.get("passed") is False
        and result.get("agent_exit_code") == SKIPPED_EVALUATOR_EXIT_CODE
        and result.get("evaluator_exit_code") == SKIPPED_EVALUATOR_EXIT_CODE
    )
    if (workdir is None or not workdir.is_dir()) and not legacy_failed_without_workdir:
        return False
    try:
        environment = json.loads(artifacts["sanitized_environment"].read_text())
    except (OSError, json.JSONDecodeError):
        return False
    return isinstance(environment, dict)


def _schema_v2_result_consistent(result: dict[str, object]) -> bool:
    """Validate an embedded score and all derived terminal outcome fields."""
    score = None
    if "score" in result:
        try:
            score = parse_score(result["score"])
        except ValueError:
            return False
    score_error = result.get("score_error")
    failure_stage = result.get("failure_stage")
    if score_error is not None and not isinstance(score_error, str):
        return False
    if failure_stage is not None and not isinstance(failure_stage, str):
        return False
    passed = (
        result["evaluator_exit_code"] == 0
        and score_error is None
        and (score is None or score.passed)
        and failure_stage is None
    )
    outcome = "passed" if passed else "failed"
    return (
        result.get("passed") is passed
        and result.get("status") == outcome
        and result.get("evaluator_outcome") == outcome
    )


def _load_campaign(output_root: Path) -> tuple[dict[str, object] | None, bool]:
    """Load canonical metadata and validate schema-v1 pair evidence."""
    path = output_root / "run_metadata.json"
    if not path.is_file():
        if _pair_directories(output_root):
            raise ValueError("pair directories require canonical run_metadata.json")
        return None, False
    metadata = _read_metadata(path)
    schema_version = metadata.get("schema_version", 1)
    if schema_version not in (1, SCHEMA_VERSION):
        raise ValueError(f"unsupported run_metadata.json schema_version: {schema_version}")
    if schema_version == 1:
        _validate_legacy_results(output_root)
        _upgrade_metadata_shape(metadata, output_root)
        return metadata, True
    _validate_metadata_shape(metadata)
    return metadata, False


def _read_metadata(path: Path) -> dict[str, object]:
    """Read canonical campaign metadata as one JSON object."""
    try:
        metadata = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid run_metadata.json: {error}") from error
    if not isinstance(metadata, dict):
        raise ValueError("run_metadata.json must contain a JSON object")
    return metadata


def _validate_legacy_results(output_root: Path) -> None:
    """Reject corrupt legacy result files before automatic migration."""
    for run_root in _pair_directories(output_root):
        result_path = run_root / "result.json"
        if result_path.exists() and _valid_pair_result(result_path) is None:
            raise ValueError(f"invalid schema-v1 pair result: {result_path}")


def _validate_metadata_shape(metadata: dict[str, object]) -> None:
    """Validate aggregate metadata containers before using them."""
    try:
        UUID(str(metadata.get("campaign_id")))
    except ValueError as error:
        raise ValueError("run_metadata.json campaign_id must be a UUID") from error
    for metadata_field, expected_type in (
        ("fixtures", dict),
        ("agent_configurations", dict),
        ("pairs", list),
        ("invocations", list),
        ("images", dict),
    ):
        if not isinstance(metadata.get(metadata_field), expected_type):
            raise ValueError(
                f"run_metadata.json {metadata_field} has the wrong type"
            )


def _upgrade_metadata_shape(
    metadata: dict[str, object], output_root: Path
) -> None:
    """Convert validated legacy metadata to the aggregate schema in memory."""
    fixtures = metadata.get("fixtures", {})
    selected_fixtures = metadata.get("selected_fixtures", [])
    selected_agents = metadata.get("selected_agents", [])
    agent_configurations = metadata.setdefault("agent_configurations", {})
    if not isinstance(fixtures, dict) or not isinstance(agent_configurations, dict):
        raise ValueError("invalid schema-v1 campaign registrations")
    if not isinstance(selected_fixtures, list) or not isinstance(selected_agents, list):
        raise ValueError("invalid schema-v1 campaign selectors")
    for agent in selected_agents:
        if isinstance(agent, str):
            agent_configurations.setdefault(agent, _agent_configuration(agent))
    pairs = {
        (fixture, agent)
        for fixture in selected_fixtures
        for agent in selected_agents
        if isinstance(fixture, str) and isinstance(agent, str)
    }
    pairs.update(
        (run_root.parent.name, run_root.name)
        for run_root in _pair_directories(output_root)
        if (run_root / "result.json").is_file()
    )
    metadata.update(
        {
            "schema_version": SCHEMA_VERSION,
            "campaign_id": str(uuid4()),
            "selected_fixtures": sorted(fixtures),
            "selected_agents": sorted(agent_configurations),
            "pairs": [
                {"fixture": fixture, "agent": agent}
                for fixture, agent in sorted(pairs)
            ],
            "pair_result_generation_revisions": {},
            "invocations": [],
            "result_generation_revision": (
                f"legacy:{metadata.get('result_generation_commit', 'unknown')}"
            ),
            "legacy_results": True,
        }
    )
    metadata.pop("overwrite", None)
    metadata.pop("state_reset_on_overwrite", None)
    images = metadata.setdefault("images", {})
    if not isinstance(images, dict):
        raise ValueError("invalid schema-v1 image registrations")
    _upgrade_image_records(images)


def _upgrade_image_records(images: dict[str, object]) -> None:
    """Drop legacy image entries that lack an immutable local identity."""
    for category in ("harnesses", "evaluators", "decorators", "candidates"):
        images.setdefault(category, {})
    for category in ("harnesses", "evaluators", "decorators"):
        records = images[category]
        for key, identity in tuple(records.items()):
            if not isinstance(identity, dict) or not isinstance(identity.get("id"), str):
                del records[key]
    candidates = images["candidates"]
    for fixture, records in tuple(candidates.items()):
        if not isinstance(records, dict):
            del candidates[fixture]
            continue
        for agent, identity in tuple(records.items()):
            if not isinstance(identity, dict) or not isinstance(identity.get("id"), str):
                del records[agent]


def _validate_campaign_compatibility(
    metadata: dict[str, object],
    fixtures: tuple[Fixture, ...],
    timeout_seconds: int,
    environment: dict[str, str],
    compatible_revisions: tuple[str, ...] = (),
) -> None:
    """Reject campaign drift before any Docker command or pair mutation."""
    expected = {
        "model_settings": _model_settings(environment),
        "sampling_settings": {
            "temperature": environment.get("EXPERIMENT_TEMPERATURE"),
            "top_p": environment.get("EXPERIMENT_TOP_P"),
            "seed": environment.get("EXPERIMENT_SEED"),
        },
        "timeout_seconds": timeout_seconds,
        "trial_policy": TRIAL_POLICY,
    }
    for setting, value in expected.items():
        if metadata.get(setting) != value:
            raise ValueError(f"campaign configuration mismatch: {setting}")
    if (
        not metadata.get("legacy_results")
        and metadata.get("result_generation_revision")
        not in (_execution_revision(), *compatible_revisions)
    ):
        raise ValueError("campaign configuration mismatch: result_generation_revision")
    selected = {fixture.name: fixture for fixture in fixtures}
    for name, recorded in metadata["fixtures"].items():
        fixture = selected.get(name)
        if fixture is None:
            try:
                fixture = _load_fixture(FIXTURE_ROOT, name)
            except (OSError, ValueError) as error:
                raise ValueError(f"registered fixture is unavailable: {name}") from error
        if recorded != _fixture_record(fixture):
            raise ValueError(f"campaign fixture revision mismatch: {name}")
    configurations = metadata["agent_configurations"]
    for agent, recorded in configurations.items():
        if agent not in SUPPORTED_AGENTS or recorded != _agent_configuration(agent):
            raise ValueError(f"campaign agent configuration mismatch: {agent}")


def _migrate_buildkit_evaluator_campaign(
    output_root: Path, metadata: dict[str, object]
) -> bool:
    """Migrate the known shared-tag campaign without relabeling valid pairs."""
    migrations = metadata.setdefault("runner_migrations", [])
    existing = next(
        (
            migration
            for migration in migrations
            if migration.get("id") == BUILDKIT_EVALUATOR_MIGRATION_ID
        ),
        None,
    )
    if existing is not None:
        return False
    if (
        metadata.get("result_generation_revision")
        != BUILDKIT_EVALUATOR_MIGRATION_REVISION
    ):
        return False

    preserved: dict[str, str] = {}
    for run_root in _pair_directories(output_root):
        result = _valid_pair_result(run_root / "result.json")
        if result is None:
            continue
        key = f"{result['fixture']}/{result['agent']}"
        preserved[key] = BUILDKIT_EVALUATOR_MIGRATION_REVISION

    current_revision = _execution_revision()
    for invocation in metadata["invocations"]:
        invocation.setdefault(
            "result_generation_revision", BUILDKIT_EVALUATOR_MIGRATION_REVISION
        )
    archived_evaluators = metadata["images"].get("evaluators", {}).copy()
    migration = {
        "id": BUILDKIT_EVALUATOR_MIGRATION_ID,
        "applied_at": datetime.now(timezone.utc).isoformat(),
        "from_result_generation_revision": BUILDKIT_EVALUATOR_MIGRATION_REVISION,
        "to_result_generation_revision": current_revision,
        "preserved_pairs": sorted(preserved),
        "archived_evaluators": archived_evaluators,
    }
    metadata["pair_result_generation_revisions"] = preserved
    metadata["images"]["evaluators"] = {}
    metadata["result_generation_revision"] = current_revision
    migrations.append(migration)
    _save_metadata(output_root / "run_metadata.json", metadata)
    return True


def _consolidate_legacy_logs(directory: Path) -> tuple[Path, ...]:
    """Fold old stage logs into the schema-v2 stdout/stderr streams."""
    all_sources = []
    for stream_name in ("stdout", "stderr"):
        target = directory / f"{stream_name}.log"
        sources = sorted(
            path
            for path in directory.glob(f"*.{stream_name}.log")
            if path != target
        )
        if sources:
            target.write_text("")
        else:
            target.touch()
        for source in sources:
            stage = "agent" if source.name == f"agent.{stream_name}.log" else source.name
            _write_log(target, source.read_text(), stage)
        all_sources.extend(sources)
    return tuple(all_sources)


def _upgrade_campaign_artifacts(
    output_root: Path, metadata: dict[str, object]
) -> None:
    """Normalize validated schema-v1 artifacts to the compact allowlist."""
    root_sources = _consolidate_legacy_logs(output_root)
    for run_root in _pair_directories(output_root):
        result_path = run_root / "result.json"
        result = _valid_pair_result(result_path) if result_path.is_file() else None
        if result is None:
            continue
        if result.get("schema_version", 1) == 1:
            (run_root / "workdir").mkdir(exist_ok=True)
            _consolidate_legacy_logs(run_root)
            environment_source = _safe_result_artifact(
                run_root,
                result.get("sanitized_environment", "container_environment.json"),
            )
            environment = json.loads(environment_source.read_text())
            _atomic_write_json(run_root / "environment.json", environment)
            result.update(
                {
                    "schema_version": SCHEMA_VERSION,
                    "stdout_path": "stdout.log",
                    "stderr_path": "stderr.log",
                    "workdir_path": "workdir",
                    "sanitized_environment": "environment.json",
                    "status": "passed" if result["passed"] else "failed",
                    "evaluator_outcome": "passed" if result["passed"] else "failed",
                }
            )
            _atomic_write_json(result_path, result)
        prune_workdir(run_root / "workdir")
        allowed = {
            "result.json",
            "stdout.log",
            "stderr.log",
            "environment.json",
            "workdir",
        }
        for artifact in tuple(run_root.iterdir()):
            if artifact.name not in allowed:
                shutil.rmtree(artifact) if artifact.is_dir() else artifact.unlink()
    for source in root_sources:
        source.unlink(missing_ok=True)
    metadata["schema_version"] = SCHEMA_VERSION


def _save_metadata(path: Path, metadata: dict[str, object]) -> None:
    """Atomically persist aggregate campaign metadata."""
    _atomic_write_json(path, metadata)


def _ensure_image(
    metadata_path: Path,
    metadata: dict[str, object],
    records: dict[str, object],
    key: str,
    image: str,
    build_command: list[str] | None,
    stdout: Path,
    stderr: Path,
    timeout_seconds: int,
    secret_values: tuple[str, ...],
    stage: str,
) -> int:
    """Reuse one campaign image or build and verify its immutable identity."""
    recorded = records.get(key)
    if recorded is not None and not isinstance(recorded, dict):
        raise ValueError(f"invalid recorded image: {key}")
    current = _image_identity(image)
    recorded_id = recorded.get("id") if isinstance(recorded, dict) else None
    if recorded is not None and not isinstance(recorded_id, str):
        raise ValueError(f"recorded image has no immutable ID: {image}")
    if recorded_id is not None and current.get("id") == recorded_id:
        return 0
    if build_command is None:
        return _ensure_external_image(
            metadata_path,
            metadata,
            records,
            key,
            image,
            current,
            recorded_id,
            stdout,
            stderr,
            timeout_seconds,
            secret_values,
        )
    code, _ = _run(
        build_command,
        stdout,
        stderr,
        timeout_seconds,
        secret_values,
        stage=stage,
    )
    if code:
        return code
    rebuilt = _image_identity(image)
    if not isinstance(rebuilt.get("id"), str):
        raise ValueError(f"built image has no immutable local ID: {image}")
    if recorded_id is not None and rebuilt.get("id") != recorded_id:
        raise ValueError(f"rebuilt image ID changed for campaign image: {image}")
    records[key] = rebuilt
    _save_metadata(metadata_path, metadata)
    return 0


def _ensure_external_image(
    metadata_path: Path,
    metadata: dict[str, object],
    records: dict[str, object],
    key: str,
    image: str,
    current: dict[str, object],
    recorded_id: object,
    stdout: Path,
    stderr: Path,
    timeout_seconds: int,
    secret_values: tuple[str, ...],
) -> int:
    """Materialize and record one immutable external evaluator image."""
    if recorded_id is not None:
        return _restore_external_image(
            records[key],
            str(recorded_id),
            image,
            stdout,
            stderr,
            timeout_seconds,
            secret_values,
        )
    if current.get("id") is None:
        code, _ = _run(
            ["docker", "pull", image],
            stdout,
            stderr,
            timeout_seconds,
            secret_values,
            stage=f"pull/{image}",
        )
        if code:
            return code
        current = _image_identity(image)
    if not isinstance(current.get("id"), str):
        raise ValueError(f"image has no immutable local ID after pull: {image}")
    records[key] = current
    _save_metadata(metadata_path, metadata)
    return 0


def _restore_external_image(
    recorded: dict[str, object],
    recorded_id: str,
    image: str,
    stdout: Path,
    stderr: Path,
    timeout_seconds: int,
    secret_values: tuple[str, ...],
) -> int:
    """Restore one missing external image without accepting different bytes."""
    digest_target = "@sha256:" in image
    source = (
        recorded_id
        if not digest_target
        and _image_identity(recorded_id).get("id") == recorded_id
        else None
    )
    digests = recorded.get("repo_digests", [])
    if source is None and isinstance(digests, list):
        source = next((digest for digest in digests if isinstance(digest, str)), None)
        if source is not None:
            code, _ = _run(
                ["docker", "pull", source],
                stdout,
                stderr,
                timeout_seconds,
                secret_values,
                stage=f"pull/{source}",
            )
            if code or _image_identity(image).get("id") == recorded_id:
                return code
    if source is None:
        raise ValueError(f"recorded image ID mismatch or unavailable: {image}")
    code, _ = _run(
        ["docker", "image", "tag", source, image],
        stdout,
        stderr,
        timeout_seconds,
        secret_values,
        stage=f"tag/{image}",
    )
    if not code and _image_identity(image).get("id") != recorded_id:
        raise ValueError(f"rematerialized image ID changed: {image}")
    return code


def _record_candidate_image(
    metadata_path: Path,
    metadata: dict[str, object],
    fixture: str,
    agent: str,
    identity: dict[str, object],
) -> None:
    """Register one logical pair's already-verified physical image."""
    candidates = metadata["images"]["candidates"]
    candidates.setdefault(fixture, {})[agent] = identity
    _save_metadata(metadata_path, metadata)


def _record_pair_revision(
    metadata_path: Path,
    metadata: dict[str, object],
    fixture: str,
    agent: str,
) -> None:
    """Record the runner revision that produced one complete pair."""
    metadata.setdefault("pair_result_generation_revisions", {})[
        f"{fixture}/{agent}"
    ] = _execution_revision()
    _save_metadata(metadata_path, metadata)


def write_outcomes(
    path: Path,
    output_root: Path,
    metadata: dict[str, object],
) -> None:
    """Atomically aggregate every complete registered campaign pair."""
    outcomes: dict[str, dict[str, dict[str, object]]] = {
        "coding": {},
        "research": {},
        "conversation": {},
    }
    for fixture_name, fixture_record in metadata["fixtures"].items():
        outcomes[fixture_record["outcome_group"]][fixture_name] = {}
    for pair in metadata["pairs"]:
        fixture_name = pair["fixture"]
        agent = pair["agent"]
        result = _valid_pair_result(
            output_root / fixture_name / agent / "result.json"
        )
        if result is None:
            continue
        score = result.get("score")
        outcome_group = metadata["fixtures"][fixture_name]["outcome_group"]
        outcomes[outcome_group][fixture_name][agent] = {
            "passed": result["passed"],
            "score": score["total"] if isinstance(score, dict) else None,
            "metrics": score.get("metrics", {}) if isinstance(score, dict) else {},
        }
    _atomic_write_json(path, outcomes)


def _write_failed_pair(
    fixture: Fixture,
    agent: str,
    run_root: Path,
    environment: dict[str, str],
    message: str,
    failure_stage: str,
    campaign_id: str,
) -> None:
    """Write one complete failed result when a pair cannot start."""
    run_root.mkdir(parents=True, exist_ok=True)
    (run_root / "workdir").mkdir(exist_ok=True)
    stdout = run_root / "stdout.log"
    stderr = run_root / "stderr.log"
    stdout.touch()
    _write_log(stderr, message + "\n", failure_stage)
    timestamp = datetime.now(timezone.utc)
    write_result(
        run_root / "result.json",
        fixture.name,
        agent,
        state_volume_name(fixture.name, agent, campaign_id),
        timestamp,
        timestamp,
        0.0,
        SKIPPED_EVALUATOR_EXIT_CODE,
        SKIPPED_EVALUATOR_EXIT_CODE,
        stdout,
        stderr,
        environment,
        failure_stage=failure_stage,
    )


def _evaluate_submission(
    fixture: Fixture,
    agent: str,
    submission: Path,
    run_root: Path,
    agent_stdout: Path,
    secret_values: tuple[str, ...],
    timeout_seconds: int,
    campaign_id: str,
    evaluator_image: str,
    workspace: str,
) -> tuple[int, Score | None, str | None, str | None, str | None]:
    """Run one deterministic evaluator and return its validated outcome."""
    evaluator_result = run_root / ".evaluator-result"
    evaluator_result.mkdir()
    evaluator_name = container_name(
        fixture.name, agent, "evaluator", campaign_id
    )
    stdout = run_root / "stdout.log"
    stderr = run_root / "stderr.log"
    failure_stage = None
    score = None
    score_error = None
    cleanup_error = None
    retain_result_volume = False
    volumes_cleaned = False
    input_volume = f"{workspace}-evaluator-input"
    result_volume = f"{workspace}-evaluator-result"
    evaluator_input = run_root / ".evaluator-input"
    try:
        shutil.rmtree(evaluator_input, ignore_errors=True)
        shutil.copytree(fixture.root / "eval", evaluator_input)
        shutil.copy2(agent_stdout, evaluator_input / "agent.stdout.log")
        setup_error = _remove_workspace_volume(
            input_volume, timeout_seconds
        ) or _remove_workspace_volume(result_volume, timeout_seconds)
        if setup_error is None:
            setup_error = _seed_workspace_volume(
                evaluator_input,
                input_volume,
                evaluator_image,
                container_name(
                    fixture.name, agent, "evaluator-input", campaign_id
                ),
                run_root,
                timeout_seconds,
                secret_values,
            )
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
            failure_stage = "evaluator_setup"
            _write_log(stderr, f"Evaluator setup failed: {error}\n", failure_stage)
        else:
            build_code = SKIPPED_EVALUATOR_EXIT_CODE if setup_error else 0
            if setup_error:
                evaluator_code = SKIPPED_EVALUATOR_EXIT_CODE
                failure_stage = "evaluator_setup"
                _write_log(
                    stderr, f"Evaluator setup failed: {setup_error}\n", failure_stage
                )
            if fixture.submission_dockerfile is not None and setup_error is None:
                build_code, _ = _run(
                    build_submission_command(
                        submission / fixture.submission_dockerfile, submission
                    ),
                    stdout,
                    stderr,
                    timeout_seconds,
                    secret_values,
                    stage="submission-build",
                )
                if build_code:
                    evaluator_code = SKIPPED_EVALUATOR_EXIT_CODE
                    failure_stage = "submission_build"
                    _write_log(
                        stderr,
                        "Evaluator skipped: submission Docker build failed "
                        f"with exit code {build_code}\n",
                        failure_stage,
                    )
            if not build_code:
                retain_result_volume = True
                evaluator_code, cleanup_error = _run(
                    build_evaluator_command(
                        evaluator_image,
                        fixture.eval_command,
                        submission,
                        fixture.root / "eval",
                        evaluator_name,
                        dependency_files,
                        agent_stdout,
                        evaluator_result,
                        not fixture.entrypoint_manages_dependencies,
                        workspace,
                        input_volume,
                        input_volume,
                        result_volume,
                    ),
                    stdout,
                    stderr,
                    timeout_seconds,
                    secret_values,
                    evaluator_name,
                    "evaluator",
                )
                if cleanup_error:
                    failure_stage = "evaluator_cleanup"
                export_error = _export_workspace_volume(
                    result_volume,
                    evaluator_image,
                    container_name(
                        fixture.name, agent, "evaluator-result", campaign_id
                    ),
                    evaluator_result,
                    run_root,
                    timeout_seconds,
                    secret_values,
                )
                if export_error:
                    cleanup_error = cleanup_error or export_error
                    failure_stage = "evaluator_result_export"
                    _write_log(
                        stderr,
                        "Evaluator result retained in Docker volume "
                        f"{result_volume}: {export_error}\n",
                        failure_stage,
                    )
                else:
                    retain_result_volume = False
        try:
            score = read_score(evaluator_result / "score.json")
        except ValueError as error:
            score_error = str(error)
            failure_stage = "score"
            _write_log(
                stderr, f"Evaluator score rejected: {error}\n", failure_stage
            )
        if evaluator_code != 0 and failure_stage is None:
            failure_stage = "evaluator"
        cleanup_volumes = [input_volume]
        if not retain_result_volume:
            cleanup_volumes.append(result_volume)
        volume_errors = tuple(
            error
            for volume in cleanup_volumes
            if (error := _remove_workspace_volume(volume, timeout_seconds))
        )
        if volume_errors:
            cleanup_error = cleanup_error or volume_errors[0]
            failure_stage = "evaluator_cleanup"
        else:
            volumes_cleaned = True
        return evaluator_code, score, score_error, failure_stage, cleanup_error
    finally:
        if not volumes_cleaned:
            _remove_workspace_volume(input_volume, timeout_seconds)
            if not retain_result_volume:
                _remove_workspace_volume(result_volume, timeout_seconds)
        shutil.rmtree(evaluator_input, ignore_errors=True)
        shutil.rmtree(evaluator_result, ignore_errors=True)


def _reevaluation_agent_stdout(run_root: Path, scratch: Path) -> Path:
    """Extract the original agent stream for evaluators that consume it."""
    text = (run_root / "stdout.log").read_text()
    marker = "=== agent ===\n"
    if marker in text:
        text = text.split(marker, 1)[1]
        text = text.split("\n=== ", 1)[0]
    path = scratch / "agent.stdout.log"
    path.write_text(text)
    return path


def _reevaluation_image_tag(prefix: str, revision: str) -> str:
    """Return a local image tag scoped to one immutable reevaluation revision."""
    return f"tinycua-template-reeval-{prefix}-{revision[:12]}"


def _prepare_reevaluation_images(
    fixtures: tuple[Fixture, ...],
    scratch: Path,
    timeout_seconds: int,
    secret_values: tuple[str, ...],
) -> dict[str, tuple[str, dict[str, object]]]:
    """Build or pull only evaluator images, never agent candidate images."""
    stdout = scratch / "images.stdout.log"
    stderr = scratch / "images.stderr.log"
    needs_tinycua_base = any(
        fixture.evaluator_dockerfile is not None
        or fixture.eval_image == LOCAL_PYTHON_EVALUATOR_IMAGE
        for fixture in fixtures
    )
    base_image = ""
    if needs_tinycua_base:
        base_image = _reevaluation_image_tag("tinycua-base", _execution_revision())
        code, _ = _run(
            build_base_command("tinycua", base_image),
            stdout,
            stderr,
            timeout_seconds,
            secret_values,
            stage="reevaluation/build-base",
        )
        if code:
            raise OSError(f"reevaluation base image build failed exit_code={code}")
    images: dict[str, tuple[str, dict[str, object]]] = {}
    for fixture in fixtures:
        evaluator_revision = tree_revision(fixture.root / "eval")
        if fixture.evaluator_dockerfile is not None:
            image = _reevaluation_image_tag(fixture.name, evaluator_revision)
            code, _ = _run(
                build_decorator_command(fixture.evaluator_dockerfile, base_image, image),
                stdout,
                stderr,
                timeout_seconds,
                secret_values,
                stage=f"reevaluation/build-evaluator/{fixture.name}",
            )
            if code:
                raise OSError(
                    f"reevaluation evaluator image build failed for {fixture.name} "
                    f"exit_code={code}"
                )
        elif fixture.eval_image == LOCAL_PYTHON_EVALUATOR_IMAGE:
            image = base_image
        else:
            image = fixture.eval_image
            code, _ = _run(
                ["docker", "pull", image],
                stdout,
                stderr,
                timeout_seconds,
                secret_values,
                stage=f"reevaluation/pull-evaluator/{fixture.name}",
            )
            if code:
                raise OSError(
                    f"reevaluation evaluator image pull failed for {fixture.name} "
                    f"exit_code={code}"
                )
        identity = _image_identity(image)
        if not isinstance(identity.get("id"), str):
            raise OSError(f"reevaluation evaluator image has no ID: {image}")
        images[fixture.name] = (image, identity)
    return images


def _reevaluation_version(
    fixture: Fixture, image: dict[str, object]
) -> str:
    """Fingerprint evaluator inputs independently from the original campaign."""
    payload = {
        "runner_revision": _execution_revision(),
        "fixture_revision": tree_revision(fixture.root),
        "evaluator_fixture_revision": tree_revision(fixture.root / "eval"),
        "eval_command": fixture.eval_command,
        "image": image,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _evaluate_existing_pair(
    fixture: Fixture,
    agent: str,
    run_root: Path,
    image: str,
    image_identity: dict[str, object],
    scratch: Path,
    timeout_seconds: int,
    secret_values: tuple[str, ...],
    invocation_id: str,
) -> dict[str, object]:
    """Run an evaluator against one saved workdir without invoking its agent."""
    pair_scratch = scratch / fixture.name / agent
    pair_scratch.mkdir(parents=True)
    agent_stdout = _reevaluation_agent_stdout(run_root, pair_scratch)
    evaluator_result = pair_scratch / "result"
    evaluator_result.mkdir()
    stdout = pair_scratch / "stdout.log"
    stderr = pair_scratch / "stderr.log"
    dependency_files = (
        ()
        if fixture.entrypoint_manages_dependencies
        else _existing_submission_dependency_files(
            run_root / "workdir", fixture.submission_dependency_files
        )
    )
    command = build_evaluator_command(
        image,
        fixture.eval_command,
        run_root / "workdir",
        fixture.root / "eval",
        container_name(fixture.name, agent, "reevaluator", invocation_id),
        dependency_files,
        agent_stdout,
        evaluator_result,
        not fixture.entrypoint_manages_dependencies,
    )
    evaluator_code, cleanup_error = _run(
        command,
        stdout,
        stderr,
        timeout_seconds,
        secret_values,
        container_name(fixture.name, agent, "reevaluator", invocation_id),
        "reevaluation/evaluator",
    )
    if cleanup_error:
        raise OSError(cleanup_error)
    try:
        score = read_score(evaluator_result / "score.json")
    except ValueError as error:
        raise OSError(f"reevaluation produced no valid score: {error}") from error
    return {
        "evaluator_version": _reevaluation_version(fixture, image_identity),
        "evaluator_fixture_revision": tree_revision(fixture.root / "eval"),
        "evaluator_image": image_identity,
        "eval_command": fixture.eval_command,
        "evaluator_exit_code": evaluator_code,
        "score": score,
        "score_error": None,
        "failure_stage": None,
    }


def _execute_pair(
    fixture: Fixture,
    agent: str,
    image: str,
    run_root: Path,
    timeout_seconds: int,
    campaign_id: str,
    evaluator_image: str | None = None,
) -> tuple[bool, bool]:
    """Run one fresh pair, clean its volumes, and retain only durable evidence."""
    run_root.mkdir(parents=True)
    stdout = run_root / "stdout.log"
    stderr = run_root / "stderr.log"
    stdout.touch()
    stderr.touch()
    agent_stdout = run_root / ".agent.stdout.log"
    agent_stderr = run_root / ".agent.stderr.log"
    raw_environment, environment = _agent_compose_environments(
        Path(".env"), fixture.prompt, agent
    )
    secret_values = _secret_values(raw_environment, environment)
    volume = state_volume_name(fixture.name, agent, campaign_id)
    workspace = workspace_volume_name(fixture.name, agent, campaign_id)
    override = run_root / ".compose-image.yaml"
    _write_override(override, agent_service(agent), image)
    state_error = (
        None if agent == "opencode" else _remove_state_volume(volume, timeout_seconds)
    )
    workspace_error = _remove_workspace_volume(workspace, timeout_seconds)
    started_at = datetime.now(timezone.utc)
    started_time = time.monotonic()
    cleanup_error = state_error or workspace_error
    failure_stage = "state_setup" if state_error else None
    if workspace_error:
        failure_stage = "workspace_setup"
    try:
        seed_error = cleanup_error or _seed_workspace_volume(
            fixture.root / "workdir",
            workspace,
            image,
            container_name(fixture.name, agent, "workspace-seed", campaign_id),
            run_root,
            timeout_seconds,
            secret_values,
        )
        if seed_error:
            agent_code = SKIPPED_EVALUATOR_EXIT_CODE
            cleanup_error = seed_error
            failure_stage = failure_stage or "workspace_setup"
            _write_log(stderr, f"Agent skipped: {seed_error}\n", failure_stage)
        else:
            agent_name = container_name(
                fixture.name, agent, "agent", campaign_id
            )
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
            _write_log(stdout, agent_stdout.read_text(), "agent")
            _write_log(stderr, agent_stderr.read_text(), "agent")
            if cleanup_error:
                failure_stage = "agent_cleanup"
            else:
                cleanup_error = _export_workspace_volume(
                    workspace,
                    image,
                    container_name(
                        fixture.name, agent, "workspace-export", campaign_id
                    ),
                    run_root / "workdir",
                    run_root,
                    timeout_seconds,
                    secret_values,
                )
                if cleanup_error:
                    failure_stage = "workspace_export"
        ended_at = datetime.now(timezone.utc)
        elapsed = time.monotonic() - started_time
        if cleanup_error:
            evaluator_code = SKIPPED_EVALUATOR_EXIT_CODE
            score = None
            score_error = None
            _write_log(
                stderr,
                f"Evaluator skipped: {cleanup_error}\n",
                failure_stage or "cleanup",
            )
        else:
            (
                evaluator_code,
                score,
                score_error,
                failure_stage,
                cleanup_error,
            ) = _evaluate_submission(
                fixture,
                agent,
                run_root / "workdir",
                run_root,
                agent_stdout,
                secret_values,
                timeout_seconds,
                campaign_id,
                evaluator_image or fixture.eval_image,
                workspace,
            )
        prune_workdir(run_root / "workdir")
    finally:
        final_errors = [
            error
            for error in (
                _remove_workspace_volume(workspace, timeout_seconds),
                None
                if agent == "opencode"
                else _remove_state_volume(volume, timeout_seconds),
            )
            if error
        ]
        override.unlink(missing_ok=True)
        agent_stdout.unlink(missing_ok=True)
        agent_stderr.unlink(missing_ok=True)
    if final_errors:
        cleanup_error = cleanup_error or final_errors[0]
        failure_stage = "cleanup"
        _write_log(stderr, "\n".join(final_errors) + "\n", failure_stage)
    write_result(
        run_root / "result.json",
        fixture.name,
        agent,
        volume,
        started_at,
        ended_at,
        elapsed,
        agent_code,
        evaluator_code,
        stdout,
        stderr,
        environment,
        score,
        score_error,
        failure_stage,
    )
    passed = (
        evaluator_code == 0
        and score_error is None
        and (score is None or score.passed)
        and failure_stage is None
    )
    return not passed, cleanup_error is not None


def _selected_campaign_failed(
    output_root: Path, fixtures: tuple[Fixture, ...], agents: tuple[str, ...]
) -> bool:
    """Return whether any complete currently selected pair failed."""
    return any(
        result is not None and not result["passed"]
        for fixture in fixtures
        for agent in agents
        if (
            result := _valid_pair_result(
                output_root / fixture.name / agent / "result.json"
            )
        )
        is not None
    )


def _prepare_campaign_metadata(
    output_root: Path,
    fixtures: tuple[Fixture, ...],
    agents: tuple[str, ...],
    overwrite: bool,
    timeout_seconds: int,
    environment: dict[str, str],
    order_by: str = "fixture",
) -> dict[str, object]:
    """Load, validate, migrate, and register one campaign invocation."""
    metadata, migrated = _load_campaign(output_root)
    if metadata is None:
        metadata = _new_metadata(timeout_seconds, environment)
    else:
        compatible_revisions = (
            (BUILDKIT_EVALUATOR_MIGRATION_REVISION,)
            if metadata.get("result_generation_revision")
            == BUILDKIT_EVALUATOR_MIGRATION_REVISION
            else ()
        )
        _validate_campaign_compatibility(
            metadata,
            fixtures,
            timeout_seconds,
            environment,
            compatible_revisions,
        )
        _recover_registered_pairs(output_root, metadata)
        _migrate_buildkit_evaluator_campaign(output_root, metadata)
        if metadata.get("legacy_results") and (
            overwrite
            or any(
                _valid_pair_result(
                    output_root / fixture.name / agent / "result.json"
                )
                is None
                for fixture in fixtures
                for agent in agents
            )
        ):
            raise ValueError("legacy campaign results are sealed; use a new output root")
        if migrated:
            _upgrade_campaign_artifacts(output_root, metadata)
    _register_invocation(metadata, fixtures, agents, overwrite, order_by)
    _save_metadata(output_root / "run_metadata.json", metadata)
    return metadata


def _select_pending_pairs(
    output_root: Path,
    fixtures: tuple[Fixture, ...],
    agents: tuple[str, ...],
    overwrite: bool,
    order_by: str = "fixture",
) -> list[tuple[Fixture, str]]:
    """Skip complete results and clean every selected pair that must run."""
    if order_by not in ("fixture", "agent"):
        raise ValueError(f"unsupported pair order: {order_by}")
    ordered_pairs = (
        ((fixture, agent) for fixture in fixtures for agent in agents)
        if order_by == "fixture"
        else ((fixture, agent) for agent in agents for fixture in fixtures)
    )
    pending = []
    for fixture, agent in ordered_pairs:
        run_root = output_root / fixture.name / agent
        complete = _valid_pair_result(run_root / "result.json") is not None
        if complete and not overwrite:
            print(f"[{fixture.name}/{agent}] skipped complete", flush=True)
            continue
        pending.append((fixture, agent))
    return pending


def _replacement_paths(run_root: Path) -> tuple[Path, Path]:
    """Return hidden staging and previous siblings for one public pair."""
    return (
        run_root.with_name(f".{run_root.name}.staging"),
        run_root.with_name(f".{run_root.name}.previous"),
    )


def _recover_previous_pair(run_root: Path, fixture: str, agent: str) -> None:
    """Restore a valid hidden previous pair left by interrupted publication."""
    staging, previous = _replacement_paths(run_root)
    current_valid = _valid_pair_result(
        run_root / "result.json", fixture, agent
    )
    previous_valid = _valid_pair_result(
        previous / "result.json", fixture, agent
    )
    if current_valid is not None:
        shutil.rmtree(previous, ignore_errors=True)
    elif previous_valid is not None:
        shutil.rmtree(run_root, ignore_errors=True)
        previous.replace(run_root)
    else:
        shutil.rmtree(previous, ignore_errors=True)
    shutil.rmtree(staging, ignore_errors=True)


def _recover_registered_pairs(output_root: Path, metadata: dict[str, object]) -> None:
    """Recover interrupted publication for every registered campaign pair."""
    for pair in metadata["pairs"]:
        fixture = pair["fixture"]
        agent = pair["agent"]
        _recover_previous_pair(output_root / fixture / agent, fixture, agent)


def _publish_replacement(run_root: Path, fixture: str, agent: str) -> None:
    """Atomically replace a public pair while retaining a recoverable previous."""
    staging, previous = _replacement_paths(run_root)
    if _valid_pair_result(staging / "result.json", fixture, agent) is None:
        raise OSError(f"replacement pair is incomplete: {staging}")
    shutil.rmtree(previous, ignore_errors=True)
    if run_root.exists():
        run_root.replace(previous)
    try:
        staging.replace(run_root)
    except OSError:
        if previous.exists() and not run_root.exists():
            previous.replace(run_root)
        raise
    shutil.rmtree(previous, ignore_errors=True)


def _build_campaign_images(
    pending: list[tuple[Fixture, str]],
    metadata_path: Path,
    metadata: dict[str, object],
    stdout: Path,
    stderr: Path,
    timeout_seconds: int,
    secret_values: tuple[str, ...],
) -> tuple[dict[str, str], int]:
    """Build or reuse every base and evaluator image needed by pending pairs."""
    fixtures = tuple(dict.fromkeys(fixture for fixture, _agent in pending))
    agents = tuple(dict.fromkeys(agent for _fixture, agent in pending))
    services = {agent_service(agent) for agent in agents}
    if any(
        fixture.eval_image == LOCAL_PYTHON_EVALUATOR_IMAGE
        or fixture.evaluator_dockerfile is not None
        for fixture in fixtures
    ):
        services.add("tinycua")
    base_images = {
        service: f"tinycua-template-{service}-base" for service in sorted(services)
    }
    records = metadata["images"]
    for service, image in base_images.items():
        code = _ensure_image(
            metadata_path,
            metadata,
            records["harnesses"],
            service,
            image,
            build_base_command(service, image),
            stdout,
            stderr,
            timeout_seconds,
            secret_values,
            f"build/harness/{service}",
        )
        if code:
            return base_images, code
    return base_images, 0


def _ensure_evaluator_image(
    fixture: Fixture,
    base_images: dict[str, str],
    metadata_path: Path,
    metadata: dict[str, object],
    stdout: Path,
    stderr: Path,
    timeout_seconds: int,
    secret_values: tuple[str, ...],
) -> tuple[str, int]:
    """Prepare the evaluator immediately before its fixture executes."""
    image = (
        f"{fixture.eval_image}-{fixture.name}"
        if fixture.evaluator_dockerfile is not None
        else fixture.eval_image
    )
    command = (
        build_decorator_command(
            fixture.evaluator_dockerfile,
            base_images["tinycua"],
            image,
        )
        if fixture.evaluator_dockerfile is not None
        else None
    )
    return (
        image,
        _ensure_image(
            metadata_path,
            metadata,
            metadata["images"]["evaluators"],
            fixture.name,
            image,
            command,
            stdout,
            stderr,
            timeout_seconds,
            secret_values,
            f"build/evaluator/{image}",
        ),
    )


def _candidate_image(
    fixture: Fixture,
    agent: str,
    base_images: dict[str, str],
    metadata_path: Path,
    metadata: dict[str, object],
    stdout: Path,
    stderr: Path,
    timeout_seconds: int,
    secret_values: tuple[str, ...],
) -> tuple[str, dict[str, object], int]:
    """Return one pair's verified base or fixture-decorated image."""
    service = agent_service(agent)
    image = base_images[service]
    records = metadata["images"]
    identity = records["harnesses"][service]
    if not fixture.dockerfile.exists():
        return image, identity, 0
    image = f"tinycua-template-{fixture.name}-{service}"
    key = f"{fixture.name}/{service}"
    code = _ensure_image(
        metadata_path,
        metadata,
        records["decorators"],
        key,
        image,
        build_decorator_command(fixture.dockerfile, base_images[service], image),
        stdout,
        stderr,
        timeout_seconds,
        secret_values,
        f"build/decorator/{key}",
    )
    return image, records["decorators"].get(key, identity), code


def _run_pending_pairs(
    pending: list[tuple[Fixture, str]],
    output_root: Path,
    base_images: dict[str, str],
    metadata: dict[str, object],
    timeout_seconds: int,
    secret_values: tuple[str, ...],
    overwrite: bool,
) -> bool:
    """Run pending pairs and return whether cleanup requires an early stop."""
    metadata_path = output_root / "run_metadata.json"
    stdout = output_root / "stdout.log"
    stderr = output_root / "stderr.log"
    campaign_id = metadata["campaign_id"]
    for fixture, agent in pending:
        print(f"[{fixture.name}/{agent}] starting", flush=True)
        public_root = output_root / fixture.name / agent
        evaluator_image, code = _ensure_evaluator_image(
            fixture,
            base_images,
            metadata_path,
            metadata,
            stdout,
            stderr,
            timeout_seconds,
            secret_values,
        )
        if code:
            return True
        image, identity, code = _candidate_image(
            fixture,
            agent,
            base_images,
            metadata_path,
            metadata,
            stdout,
            stderr,
            timeout_seconds,
            secret_values,
        )
        if code:
            message = f"fixture image build failed exit_code={code}"
            print(f"[{fixture.name}/{agent}] {message}", flush=True)
            if overwrite:
                return True
            _, environment = _agent_compose_environments(
                Path(".env"), fixture.prompt, agent
            )
            shutil.rmtree(public_root, ignore_errors=True)
            _write_failed_pair(
                fixture,
                agent,
                public_root,
                environment,
                message,
                "fixture_image_build",
                campaign_id,
            )
            _record_pair_revision(
                metadata_path, metadata, fixture.name, agent
            )
            write_outcomes(output_root / "outcomes.json", output_root, metadata)
            continue
        if not overwrite and _valid_pair_result(
            public_root / "result.json", fixture.name, agent
        ) is not None:
            print(f"[{fixture.name}/{agent}] recovered complete", flush=True)
            continue
        run_root = _replacement_paths(public_root)[0] if overwrite else public_root
        shutil.rmtree(run_root, ignore_errors=True)
        _record_candidate_image(
            metadata_path, metadata, fixture.name, agent, identity
        )
        failed, cleanup_failed = _execute_pair(
            fixture,
            agent,
            image,
            run_root,
            timeout_seconds,
            campaign_id,
            evaluator_image,
        )
        if overwrite:
            if failed or cleanup_failed:
                shutil.rmtree(run_root, ignore_errors=True)
                return True
            _publish_replacement(public_root, fixture.name, agent)
        _record_pair_revision(metadata_path, metadata, fixture.name, agent)
        write_outcomes(output_root / "outcomes.json", output_root, metadata)
        print(
            f"[{fixture.name}/{agent}] {'failed' if failed else 'passed'}",
            flush=True,
        )
        if cleanup_failed:
            return True
    return False


def _continue_campaign(
    fixtures: tuple[Fixture, ...],
    agents: tuple[str, ...],
    output_root: Path,
    overwrite: bool,
    timeout_seconds: int,
    metadata: dict[str, object],
    configured_secrets: tuple[str, ...],
    order_by: str = "fixture",
) -> int:
    """Execute one already-registered compatible campaign invocation."""
    metadata_path = output_root / "run_metadata.json"
    pending = _select_pending_pairs(
        output_root, fixtures, agents, overwrite, order_by
    )
    write_outcomes(output_root / "outcomes.json", output_root, metadata)
    if not pending:
        return int(_selected_campaign_failed(output_root, fixtures, agents))

    root_stdout = output_root / "stdout.log"
    root_stderr = output_root / "stderr.log"
    root_stdout.touch()
    root_stderr.touch()
    if searxng_code := _ensure_searxng_ready(
        root_stdout, root_stderr, configured_secrets
    ):
        return searxng_code
    base_images, build_code = _build_campaign_images(
        pending,
        metadata_path,
        metadata,
        root_stdout,
        root_stderr,
        timeout_seconds,
        configured_secrets,
    )
    if build_code:
        return build_code
    if _run_pending_pairs(
        pending,
        output_root,
        base_images,
        metadata,
        timeout_seconds,
        configured_secrets,
        overwrite,
    ):
        return 1
    return int(_selected_campaign_failed(output_root, fixtures, agents))


def _reevaluation_pairs(
    metadata: dict[str, object],
    fixtures_raw: str | None,
    agents_raw: str | None,
) -> tuple[tuple[Fixture, str], ...]:
    """Resolve registered saved pairs selected for evaluator-only execution."""
    pairs = metadata.get("pairs")
    if not isinstance(pairs, list):
        raise ValueError("run_metadata.json pairs has the wrong type")
    registered = {
        (str(pair.get("fixture")), str(pair.get("agent")))
        for pair in pairs
        if isinstance(pair, dict)
        and isinstance(pair.get("fixture"), str)
        and isinstance(pair.get("agent"), str)
    }
    if not registered:
        raise ValueError("campaign has no registered pairs to re-evaluate")
    fixtures = (
        tuple(item.strip() for item in fixtures_raw.split(",") if item.strip())
        if fixtures_raw is not None
        else tuple(sorted({fixture for fixture, _agent in registered}))
    )
    agents = (
        parse_agents(agents_raw)
        if agents_raw is not None
        else tuple(sorted({agent for _fixture, agent in registered}))
    )
    if not fixtures or len(set(fixtures)) != len(fixtures):
        raise ValueError("fixtures must select unique registered fixtures")
    selected = tuple(
        (fixture, agent)
        for fixture, agent in sorted(registered)
        if fixture in fixtures and agent in agents
    )
    if not selected:
        raise ValueError("no registered pairs match the reevaluation selectors")
    if any(fixture not in {name for name, _agent in registered} for fixture in fixtures):
        raise ValueError("reevaluation selected an unregistered fixture")
    return tuple((_load_fixture(FIXTURE_ROOT, fixture), agent) for fixture, agent in selected)


def _run_reevaluation_campaign(
    output_root: Path,
    fixtures_raw: str | None,
    agents_raw: str | None,
    timeout_seconds: int,
) -> int:
    """Re-evaluate saved artifacts without starting any harness agent."""
    metadata, migrated = _load_campaign(output_root)
    if metadata is None or migrated or metadata.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("--re-evaluate requires an existing schema-v2 campaign")
    selected = _reevaluation_pairs(metadata, fixtures_raw, agents_raw)
    for fixture, agent in selected:
        result_path = output_root / fixture.name / agent / "result.json"
        if _valid_pair_result(result_path, fixture.name, agent) is None:
            raise ValueError(f"invalid saved pair result: {result_path}")
    invocation_id = str(uuid4())
    scratch = output_root / f".reevaluation-{invocation_id}"
    raw_environment, environment = _agent_compose_environments(Path(".env"), "")
    secret_values = _secret_values(raw_environment, environment)
    started_at = datetime.now(timezone.utc)
    try:
        scratch.mkdir()
        unique_fixtures = tuple(dict.fromkeys(fixture for fixture, _agent in selected))
        images = _prepare_reevaluation_images(
            unique_fixtures, scratch, timeout_seconds, secret_values
        )
        updates: list[tuple[Path, dict[str, object]]] = []
        any_failed = False
        for fixture, agent in selected:
            result_path = output_root / fixture.name / agent / "result.json"
            original = _valid_pair_result(result_path, fixture.name, agent)
            assert original is not None
            image, identity = images[fixture.name]
            outcome = _evaluate_existing_pair(
                fixture,
                agent,
                result_path.parent,
                image,
                identity,
                scratch,
                timeout_seconds,
                secret_values,
                invocation_id,
            )
            evaluator_version = str(outcome["evaluator_version"])
            prior = original.get("evaluator_results", [])
            if any(
                isinstance(item, dict) and item.get("evaluator_version") == evaluator_version
                for item in prior
                if isinstance(prior, list)
            ):
                continue
            updated = apply_reevaluation(
                original,
                evaluator_version=evaluator_version,
                evaluator_fixture_revision=str(outcome["evaluator_fixture_revision"]),
                evaluator_image=identity,
                eval_command=fixture.eval_command,
                evaluator_exit_code=int(outcome["evaluator_exit_code"]),
                score=outcome["score"] if isinstance(outcome["score"], Score) else None,
                score_error=outcome["score_error"] if isinstance(outcome["score_error"], str) else None,
                failure_stage=outcome["failure_stage"] if isinstance(outcome["failure_stage"], str) else None,
                evaluated_at=datetime.now(timezone.utc).isoformat(),
            )
            any_failed = any_failed or not bool(updated["passed"])
            updates.append((result_path, updated))
        for result_path, updated in updates:
            _atomic_write_json(result_path, updated)
        write_outcomes(output_root / "outcomes.json", output_root, metadata)
        records = metadata.setdefault("reevaluation_invocations", [])
        if not isinstance(records, list):
            raise ValueError("run_metadata.json reevaluation_invocations has the wrong type")
        records.append(
            {
                "id": invocation_id,
                "started_at": started_at.isoformat(),
                "ended_at": datetime.now(timezone.utc).isoformat(),
                "pairs": [
                    {"fixture": fixture.name, "agent": agent}
                    for fixture, agent in selected
                ],
                "status": "failed" if any_failed else "passed",
                "exit_code": int(any_failed),
            }
        )
        _save_metadata(output_root / "run_metadata.json", metadata)
        return int(any_failed)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def _run_campaign(
    fixtures: tuple[Fixture, ...],
    agents: tuple[str, ...],
    output_root: Path,
    overwrite: bool,
    timeout_seconds: int,
    order_by: str = "fixture",
) -> int:
    """Resume one compatible controlled campaign under a single writer."""
    metadata_path = output_root / "run_metadata.json"
    raw_environment, configured_environment = _agent_compose_environments(
        Path(".env"), ""
    )
    configured_secrets = _secret_values(raw_environment, configured_environment)
    metadata = _prepare_campaign_metadata(
        output_root,
        fixtures,
        agents,
        overwrite,
        timeout_seconds,
        configured_environment,
        order_by,
    )
    exit_code = 1
    try:
        exit_code = _continue_campaign(
            fixtures,
            agents,
            output_root,
            overwrite,
            timeout_seconds,
            metadata,
            configured_secrets,
            order_by,
        )
    except (OSError, ValueError):
        exit_code = 2
        raise
    except KeyboardInterrupt:
        exit_code = 130
        raise
    finally:
        _finish_invocation(metadata_path, metadata, exit_code)
    return exit_code


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
        "--order-by",
        choices=("fixture", "agent"),
        default="fixture",
        help="Run all agents per fixture or all fixtures per agent (default: fixture).",
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
        "--re-evaluate",
        action="store_true",
        help="Run current evaluators against saved workdirs without invoking agents.",
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
    if args.re_evaluate and args.overwrite:
        parser.error("--re-evaluate cannot be combined with --overwrite")
    return args


def main(argv: list[str] | None = None) -> int:
    """Run selected controlled coding experiments."""
    args = parse_args(argv)
    try:
        output_root = args.output_root.resolve()
        if args.re_evaluate:
            if not output_root.is_dir():
                raise ValueError("--re-evaluate requires an existing --output-root")
            with campaign_lock(output_root):
                return _run_reevaluation_campaign(
                    output_root,
                    args.fixtures,
                    args.agents,
                    args.timeout_seconds,
                )
        fixtures = discover_fixtures(FIXTURE_ROOT, args.fixtures)
        agents = parse_agents(args.agents)
        output_root.mkdir(parents=True, exist_ok=True)
        with campaign_lock(output_root):
            return _run_campaign(
                fixtures,
                agents,
                output_root,
                args.overwrite,
                args.timeout_seconds,
                args.order_by,
            )
    except (OSError, ValueError) as error:
        print(error, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
