"""Unit tests for the controlled template experiment runner."""

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest
import run_template_experiment as runner

from run_template_experiment import (
    FIXTURE_ROOT,
    Fixture,
    build_agent_command,
    build_decorator_command,
    build_evaluator_command,
    container_name,
    discover_fixtures,
    evaluator_base_agents,
    parse_score,
    parse_args,
    state_volume_name,
    workspace_volume_name,
    write_result,
)


def make_fixture(root: Path, name: str = "add-greeting") -> Path:
    """Create a valid fixture tree."""
    fixture = root / name
    (fixture / "workdir").mkdir(parents=True)
    (fixture / "eval").mkdir()
    (fixture / "manifest.yaml").write_text(
        "prompt: Add a greeting.\n"
        "outcome_group: coding\n"
        "eval_image: python:3.12-alpine\n"
        "eval_dockerfile: eval/Dockerfile\n"
        "eval_command: [python, /eval/check.py, /submission]\n"
    )
    (fixture / "workdir" / "app.py").write_text("pass\n")
    (fixture / "eval" / "run.sh").write_text("#!/bin/sh\n")
    (fixture / "eval" / "Dockerfile").write_text("ARG BASE_IMAGE\nFROM ${BASE_IMAGE}\n")
    return fixture


def test_discover_fixtures_validates_layout_and_prompt(tmp_path: Path) -> None:
    """Fixtures need the complete layout and a meaningful YAML prompt."""
    root = tmp_path / "fixtures"
    fixture = make_fixture(root)

    discovered = discover_fixtures(root, "add-greeting")

    assert discovered == (
        Fixture(
            "add-greeting",
            "Add a greeting.",
            "python:3.12-alpine",
            ("python", "/eval/check.py", "/submission"),
            fixture,
            fixture / "docker" / "Dockerfile",
            outcome_group="coding",
            evaluator_dockerfile=fixture / "eval" / "Dockerfile",
        ),
    )
    (fixture / "manifest.yaml").write_text(
        "prompt: '   '\neval_image: busybox\neval_command: [true]\n"
    )
    with pytest.raises(ValueError, match="prompt"):
        discover_fixtures(root, "add-greeting")
    (fixture / "manifest.yaml").write_text("[not-a-mapping]\n")
    with pytest.raises(ValueError, match="mapping"):
        discover_fixtures(root, "add-greeting")
    (fixture / "manifest.yaml").write_text(
        "prompt:\neval_image: busybox\neval_command: [true]\n"
    )
    with pytest.raises(ValueError, match="prompt"):
        discover_fixtures(root, "add-greeting")
    (fixture / "manifest.yaml").write_text("prompt: [\n")
    with pytest.raises(ValueError, match="invalid manifest"):
        discover_fixtures(root, "add-greeting")
    (fixture / "manifest.yaml").write_text("prompt: valid\neval_image: busybox\n")
    with pytest.raises(ValueError, match="eval_command"):
        discover_fixtures(root, "add-greeting")
    (fixture / "manifest.yaml").write_text(
        "prompt: valid\neval_image: '  '\neval_command: [true]\n"
    )
    with pytest.raises(ValueError, match="eval_image"):
        discover_fixtures(root, "add-greeting")
    (fixture / "eval" / "run.sh").unlink()
    (fixture / "eval" / "Dockerfile").unlink()
    (fixture / "eval").rmdir()
    with pytest.raises(ValueError, match="eval"):
        discover_fixtures(root, "add-greeting")


def test_default_fixture_root_contains_smoke_and_migrated_experiments() -> None:
    """The runner exposes the smoke test plus the five controlled prompts."""
    fixtures = discover_fixtures(FIXTURE_ROOT)

    assert tuple(fixture.name for fixture in fixtures) == (
        *(f"experiment-{number}" for number in range(1, 6)),
        "smoke-test",
    )


def test_submission_dependency_scan_ignores_generated_virtualenv(
    tmp_path: Path,
) -> None:
    """Container-specific virtualenv links are not host submission manifests."""
    submission = tmp_path / "submission"
    (submission / ".venv" / "bin").mkdir(parents=True)
    (submission / ".venv" / "bin" / "python").symlink_to(
        "/root/.local/share/uv/python/cpython/bin/python"
    )
    (submission / ".venv" / "pyproject.toml").write_text("[project]\n")

    assert runner._existing_submission_dependency_files(submission, ()) == ()


def test_workspace_and_state_volumes_isolate_pairs() -> None:
    """Every fixture and harness pair gets separate workspace and state volumes."""
    assert workspace_volume_name("add-greeting", "opencode") != workspace_volume_name(
        "add-greeting", "tinycua"
    )
    assert workspace_volume_name("task_a", "opencode") != workspace_volume_name(
        "task-a", "opencode"
    )
    assert workspace_volume_name("task_a", "opencode") == workspace_volume_name(
        "task_a", "opencode"
    )
    assert state_volume_name("add-greeting", "opencode") != state_volume_name(
        "add-greeting", "tinycua"
    )
    assert state_volume_name("task_a", "opencode") != state_volume_name(
        "task-a", "opencode"
    )
    assert state_volume_name("task_a", "opencode") == state_volume_name(
        "task_a", "opencode"
    )


def test_evaluator_base_agents_adds_tinycua_for_local_python_evaluators() -> None:
    """Local Python evaluators work even when TinyCUA is not selected as an agent."""
    fixture = Fixture(
        "report",
        "Write a report.",
        "tinycua-template-tinycua-base",
        ("sh", "/eval/run.sh", "/submission"),
        Path("fixture"),
        Path("fixture/docker/Dockerfile"),
    )

    assert evaluator_base_agents((fixture,), ("opencode",)) == ("opencode", "tinycua")


def test_docker_commands_isolate_agent_and_evaluator(tmp_path: Path) -> None:
    """Only evaluators receive evaluator files and every mount is explicit."""
    fixture = make_fixture(tmp_path / "fixtures")
    dockerfile = fixture / "docker" / "Dockerfile"
    dockerfile.parent.mkdir()
    dockerfile.write_text("ARG BASE_IMAGE\nFROM ${BASE_IMAGE}\n")
    submission = tmp_path / "results" / "workdir"
    workspace = workspace_volume_name("add-greeting", "opencode")
    volume = state_volume_name("add-greeting", "opencode")

    decorator = build_decorator_command(dockerfile, "base:latest", "derived:latest")
    agent = build_agent_command(
        Path("docker-compose.yml"),
        tmp_path / "override.yaml",
        "opencode",
        "Add a greeting.",
        workspace,
        volume,
        container_name("add-greeting", "opencode", "agent"),
    )
    evaluator = build_evaluator_command(
        "python:3.12-alpine",
        ("python", "/eval/check.py", "/submission"),
        submission,
        fixture / "eval",
        container_name("add-greeting", "opencode", "evaluator"),
        agent_stdout=tmp_path / "agent.stdout.log",
        result_directory=tmp_path / "evaluator-result",
    )

    assert decorator == [
        "docker",
        "build",
        "--tag",
        "derived:latest",
        "--build-arg",
        "BASE_IMAGE=base:latest",
        "--file",
        str(dockerfile),
        str(fixture / "docker"),
    ]
    assert "eval" not in " ".join(agent)
    assert agent.count("-v") == 1
    assert "--name" in agent
    assert agent[agent.index("--name") + 1] == container_name(
        "add-greeting", "opencode", "agent"
    )
    assert f"{workspace}:/workspace" in agent
    assert f"{submission.resolve()}:/workspace" not in agent
    assert f"{volume}:/state" not in agent
    assert agent[-3:] == ["--workdir", "/workspace", "opencode"]
    assert f"{submission.resolve()}:/submission:ro" in evaluator
    assert f"{(fixture / 'eval').resolve()}:/eval:ro" in evaluator
    assert (
        f"{(tmp_path / 'agent.stdout.log').resolve()}:/agent-output/agent.stdout.log:ro"
        in evaluator
    )
    assert f"{(tmp_path / 'evaluator-result').resolve()}:/result" in evaluator
    assert "--name" in evaluator
    assert evaluator[evaluator.index("--name") + 1] == container_name(
        "add-greeting", "opencode", "evaluator"
    )
    assert evaluator[-4:] == [
        "python:3.12-alpine",
        "python",
        "/eval/check.py",
        "/submission",
    ]
    assert container_name("add-greeting", "opencode", "agent") != container_name(
        "add-greeting", "opencode", "evaluator"
    )


def test_evaluator_installs_submission_and_evaluator_dependencies(
    tmp_path: Path,
) -> None:
    """Dependency manifests are installed inside the evaluator before its command."""
    submission = tmp_path / "submission"
    evaluator = tmp_path / "eval"
    submission.mkdir()
    evaluator.mkdir()
    (submission / "requirements.txt").write_text("requests==2.32.3\n")
    (submission / "pyproject.toml").write_text("[project]\nname = 'submission'\n")
    (evaluator / "requirements.txt").write_text("sacrebleu==2.5.1\n")
    (evaluator / "pyproject.toml").write_text("[project]\nname = 'evaluator'\n")

    command = build_evaluator_command(
        "python:3.12-alpine",
        ("python", "/eval/check.py", "/submission"),
        submission,
        evaluator,
        "evaluator",
    )

    assert command[-7:-4] == ["sh", "-c", command[-5]]
    assert "python or python3 is available" in command[-5]
    assert "python -m pip is unavailable" in command[-5]
    assert "/submission/requirements.txt" in command[-5]
    assert "pip install -r /submission/requirements.txt" in command[-5]
    assert "/submission/pyproject.toml" not in command[-5]
    assert "/eval/requirements.txt" in command[-5]
    assert "pip install -r /eval/requirements.txt" in command[-5]
    assert "pip install /eval" in command[-5]
    assert command[-3:] == ["python", "/eval/check.py", "/submission"]


def test_fixture_declares_safe_nested_submission_dependencies(tmp_path: Path) -> None:
    """Fixtures explicitly allow only sorted nested dependency manifests."""
    fixture = make_fixture(tmp_path / "fixtures")
    (fixture / "manifest.yaml").write_text(
        "prompt: Add a greeting.\n"
        "eval_image: python:3.12-alpine\n"
        "eval_command: [python, /eval/check.py, /submission]\n"
        "submission_dependency_files:\n"
        "  - packages/z/pyproject.toml\n"
        "  - packages/a/requirements.txt\n"
        "submission_dockerfile: Dockerfile\n"
    )
    (fixture / "workdir" / "packages" / "a").mkdir(parents=True)
    (fixture / "workdir" / "packages" / "z").mkdir()
    (fixture / "workdir" / "packages" / "a" / "requirements.txt").write_text("a\n")
    (fixture / "workdir" / "packages" / "z" / "pyproject.toml").write_text(
        "[project]\nname = 'z'\n"
    )

    discovered = discover_fixtures(tmp_path / "fixtures", "add-greeting")[0]
    command = build_evaluator_command(
        discovered.eval_image,
        discovered.eval_command,
        fixture / "workdir",
        fixture / "eval",
        "evaluator",
        discovered.submission_dependency_files,
    )

    assert discovered.submission_dependency_files == (
        Path("packages/a/requirements.txt"),
        Path("packages/z/pyproject.toml"),
    )
    assert discovered.submission_dockerfile == Path("Dockerfile")
    assert "/submission/packages/a/requirements.txt" in command[-5]
    assert "/submission/packages/z/pyproject.toml" not in command[-5]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("submission_dependency_files", "[../requirements.txt]"),
        ("submission_dependency_files", "[requirements.txt]"),
        ("submission_dependency_files", "[a/requirements.txt, a/requirements.txt]"),
        ("submission_dockerfile", "../Dockerfile"),
    ],
)
def test_discover_fixtures_rejects_unsafe_submission_paths(
    tmp_path: Path, field: str, value: str
) -> None:
    """Submission manifest paths cannot escape or duplicate the copied workspace."""
    fixture = make_fixture(tmp_path / "fixtures")
    (fixture / "manifest.yaml").write_text(
        "prompt: Add a greeting.\n"
        "eval_image: python:3.12-alpine\n"
        "eval_command: [python, /eval/check.py, /submission]\n"
        f"{field}: {value}\n"
    )

    with pytest.raises(ValueError, match=field):
        discover_fixtures(tmp_path / "fixtures", "add-greeting")


def test_evaluator_without_dependency_manifests_keeps_busybox_command(
    tmp_path: Path,
) -> None:
    """Manifest-free BusyBox evaluators do not require Python or a shell wrapper."""
    submission = tmp_path / "submission"
    evaluator = tmp_path / "eval"
    submission.mkdir()
    evaluator.mkdir()

    command = build_evaluator_command(
        "busybox:1.36",
        ("sh", "/eval/check.sh", "/submission"),
        submission,
        evaluator,
        "evaluator",
    )

    assert command[-4:] == ["busybox:1.36", "sh", "/eval/check.sh", "/submission"]


def test_parse_args_requires_a_positive_timeout() -> None:
    """The controlled runner always has a finite execution deadline."""
    assert parse_args([]).timeout_seconds == 14_400
    with pytest.raises(SystemExit):
        parse_args(["--timeout-seconds", "0"])


def test_run_disconnects_child_stdin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Compose runs cannot wait for or receive the runner's terminal input."""
    captured: dict[str, object] = {}

    def fake_run(*_args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured.update(kwargs)
        return subprocess.CompletedProcess([], 0, "", "")

    monkeypatch.setattr(runner.subprocess, "run", fake_run)

    assert runner._run(["docker"], tmp_path / "stdout", tmp_path / "stderr", 1) == (
        0,
        None,
    )
    assert captured["stdin"] is subprocess.DEVNULL


def test_reset_state_volumes_skips_opencode(monkeypatch: pytest.MonkeyPatch) -> None:
    """OpenCode uses an ephemeral home while other harnesses keep pair state."""
    calls: list[list[str]] = []

    def fake_run(
        command: list[str], **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, "", "")

    fixture = Fixture(
        "greeting",
        "Reply.",
        "busybox",
        ("true",),
        Path("fixture"),
        Path("fixture/docker/Dockerfile"),
    )
    monkeypatch.setattr(runner.subprocess, "run", fake_run)

    runner._reset_state_volumes((fixture,), ("opencode", "openclaw", "tinycua"), 1)

    assert calls == [
        [
            "docker",
            "volume",
            "rm",
            "--force",
            state_volume_name("greeting", "openclaw"),
        ],
        ["docker", "volume", "rm", "--force", state_volume_name("greeting", "tinycua")],
    ]


def test_write_result_is_portable_and_sanitizes_environment(tmp_path: Path) -> None:
    """The per-pair result contains safe, portable execution evidence."""
    result_path = tmp_path / "result.json"
    stdout = tmp_path / "agent.stdout.log"
    stderr = tmp_path / "agent.stderr.log"
    stdout.write_text("agent output\n")
    stderr.write_text("")
    started_at = datetime(2026, 7, 22, tzinfo=timezone.utc)
    ended_at = datetime(2026, 7, 22, 0, 0, 1, tzinfo=timezone.utc)

    write_result(
        result_path,
        "add-greeting",
        "opencode",
        "state",
        started_at,
        ended_at,
        1.25,
        7,
        0,
        stdout,
        stderr,
        {"DB_PASSWORD": "raw-password", "VISIBLE": "value"},
    )
    result = json.loads(result_path.read_text())
    assert result["started_at"] == "2026-07-22T00:00:00+00:00"
    assert result["ended_at"] == "2026-07-22T00:00:01+00:00"
    assert result["elapsed_prompt_to_finish_seconds"] == 1.25
    assert result["stdout_path"] == "agent.stdout.log"
    assert result["stderr_path"] == "agent.stderr.log"
    assert result["sanitized_environment"] == "container_environment.json"
    assert result["agent_exit_code"] == 7
    assert result["evaluator_exit_code"] == 0
    assert result["passed"] is True
    assert result["evaluator_outcome"] == "passed"
    snapshot = json.loads((tmp_path / result["sanitized_environment"]).read_text())
    assert snapshot["VISIBLE"] == "value"
    assert snapshot["DB_PASSWORD"] == "[REDACTED]"
    assert (
        "raw-password" not in (tmp_path / result["sanitized_environment"]).read_text()
    )


def test_redaction_preserves_token_counts_but_removes_credentials() -> None:
    """Usage telemetry is visible while actual credentials remain protected."""
    text = "output_tokens=123 total_tokens:456 api_key=raw-secret"

    assert runner._redact_output(text, ("raw-secret",)) == (
        "output_tokens=123 total_tokens:456 api_key=[REDACTED]"
    )


def test_parse_score_accepts_evidenced_threshold_score() -> None:
    """Scores contain bounded category points and evidence for critical work."""
    score = parse_score(
        {
            "categories": {
                "backend_api": {
                    "points": 20,
                    "max_points": 20,
                    "evidence": ["POST /blocks returned 201"],
                },
                "frontend": {
                    "points": 15,
                    "max_points": 20,
                    "evidence": [],
                },
            },
            "total": 35,
            "pass_threshold": 30,
            "critical_categories": ["backend_api"],
        }
    )

    assert score.passed is True
    assert score.as_dict() == {
        "categories": {
            "backend_api": {
                "points": 20,
                "max_points": 20,
                "evidence": ["POST /blocks returned 201"],
            },
            "frontend": {"points": 15, "max_points": 20, "evidence": []},
        },
        "total": 35,
        "pass_threshold": 30,
        "critical_categories": ["backend_api"],
    }


def test_parse_score_preserves_non_gating_secondary_metrics() -> None:
    """Secondary metrics are reported without changing pass/fail semantics."""
    score = parse_score(
        {
            "categories": {
                "report_exists": {
                    "points": 1,
                    "max_points": 1,
                    "evidence": ["report exists"],
                }
            },
            "total": 1,
            "pass_threshold": 1,
            "critical_categories": ["report_exists"],
            "metrics": {"rouge_l_f1": 42.75},
        }
    )

    assert score.passed is True
    assert score.as_dict()["metrics"] == {"rouge_l_f1": 42.75}


@pytest.mark.parametrize(
    "data",
    [
        {},
        {
            "categories": {
                "backend_api": {
                    "points": 21,
                    "max_points": 20,
                    "evidence": ["too many points"],
                }
            },
            "total": 21,
            "pass_threshold": 20,
            "critical_categories": ["backend_api"],
        },
    ],
)
def test_parse_score_rejects_malformed_scores(data: object) -> None:
    """Malformed scores cannot enter pair results."""
    with pytest.raises(ValueError):
        parse_score(data)


def test_parse_score_fails_without_critical_evidence() -> None:
    """A complete score cannot pass when a critical category lacks evidence."""
    score = parse_score(
        {
            "categories": {
                "backend_api": {"points": 20, "max_points": 20, "evidence": []}
            },
            "total": 20,
            "pass_threshold": 20,
            "critical_categories": ["backend_api"],
        }
    )

    assert score.passed is False


def test_parse_score_fails_when_critical_category_is_partial() -> None:
    """Critical categories must earn all available points, not just evidence."""
    score = parse_score(
        {
            "categories": {
                "correctness": {
                    "points": 0,
                    "max_points": 1,
                    "evidence": ["check ran but failed"],
                },
                "formatting": {
                    "points": 1,
                    "max_points": 1,
                    "evidence": ["format passed"],
                },
            },
            "total": 1,
            "pass_threshold": 1,
            "critical_categories": ["correctness"],
        }
    )

    assert score.passed is False


def test_write_result_embeds_optional_score(tmp_path: Path) -> None:
    """A valid evaluator score becomes portable pair-result evidence."""
    result_path = tmp_path / "result.json"
    stdout = tmp_path / "agent.stdout.log"
    stderr = tmp_path / "agent.stderr.log"
    stdout.write_text("")
    stderr.write_text("")
    score = parse_score(
        {
            "categories": {
                "frontend": {
                    "points": 20,
                    "max_points": 20,
                    "evidence": ["browser rendered block"],
                }
            },
            "total": 20,
            "pass_threshold": 20,
            "critical_categories": ["frontend"],
        }
    )

    write_result(
        result_path,
        "add-greeting",
        "opencode",
        "state",
        datetime(2026, 7, 22, tzinfo=timezone.utc),
        datetime(2026, 7, 22, 0, 0, 1, tzinfo=timezone.utc),
        1.0,
        0,
        0,
        stdout,
        stderr,
        {},
        score,
    )

    result = json.loads(result_path.read_text())
    assert result["score"] == score.as_dict()
    assert result["passed"] is True
