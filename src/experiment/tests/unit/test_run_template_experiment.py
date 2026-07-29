"""Unit tests for the controlled template experiment runner."""

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest
import run_template_experiment as runner

from run_template_experiment import (
    AGENTS,
    FIXTURE_ROOT,
    Fixture,
    build_agent_command,
    build_decorator_command,
    build_evaluator_command,
    container_name,
    discover_fixtures,
    parse_agents,
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


def test_tinycua_ablation_aliases_are_selectable_without_changing_defaults() -> None:
    """Ablations are explicit controlled-runner selections, not new defaults."""
    aliases = ("tinycua-nr", "tinycua-nd", "tinycua-nd-nr")

    assert AGENTS == ("tinycua", "opencode", "hermes", "openclaw")
    assert parse_agents(",".join(("tinycua", *aliases))) == ("tinycua", *aliases)


def test_pending_pairs_follow_selected_major_order(tmp_path: Path) -> None:
    """Agent and fixture selectors retain their explicit relative order."""
    fixtures = tuple(
        Fixture(
            name,
            "Make a change.",
            "busybox",
            ("true",),
            tmp_path / name,
            tmp_path / name / "Dockerfile",
        )
        for name in ("experiment-2", "experiment-1")
    )
    agents = ("tinycua", "opencode")

    fixture_major = runner._select_pending_pairs(
        tmp_path, fixtures, agents, False, "fixture"
    )
    agent_major = runner._select_pending_pairs(
        tmp_path, fixtures, agents, False, "agent"
    )

    assert [(fixture.name, agent) for fixture, agent in fixture_major] == [
        ("experiment-2", "tinycua"),
        ("experiment-2", "opencode"),
        ("experiment-1", "tinycua"),
        ("experiment-1", "opencode"),
    ]
    assert [(fixture.name, agent) for fixture, agent in agent_major] == [
        ("experiment-2", "tinycua"),
        ("experiment-1", "tinycua"),
        ("experiment-2", "opencode"),
        ("experiment-1", "opencode"),
    ]


@pytest.mark.parametrize(
    ("agent", "digest", "review"),
    [
        ("tinycua", "0", "0"),
        ("tinycua-nr", "0", "1"),
        ("tinycua-nd", "1", "0"),
        ("tinycua-nd-nr", "1", "1"),
    ],
)
def test_tinycua_ablation_aliases_share_service_and_set_flags(
    agent: str, digest: str, review: str
) -> None:
    """Logical ablations reuse TinyCUA while retaining isolated run identities."""
    command = build_agent_command(
        Path("docker-compose.yml"),
        Path("override.yaml"),
        agent,
        "Do work.",
        workspace_volume_name("fixture", agent),
        state_volume_name("fixture", agent),
        container_name("fixture", agent, "agent"),
    )

    assert command[-1] == "tinycua"
    assert f"EXPERIMENT_TINYCUA_NO_DIGEST={digest}" in command
    assert f"EXPERIMENT_TINYCUA_NO_REVIEW={review}" in command
    assert f"{state_volume_name('fixture', agent)}:/state" in command
    assert f"{workspace_volume_name('fixture', agent)}:/workspace" in command


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


def test_fixture_can_delegate_dependency_setup_to_its_entrypoint(
    tmp_path: Path,
) -> None:
    """A free-form fixture can let its start script install its dependencies."""
    fixture = make_fixture(tmp_path / "fixtures")
    (fixture / "manifest.yaml").write_text(
        "prompt: Add a greeting.\n"
        "eval_image: python:3.12-alpine\n"
        "eval_command: [python, /eval/check.py, /submission]\n"
        "entrypoint_manages_dependencies: true\n"
    )
    submission = fixture / "workdir"
    evaluator = fixture / "eval"
    (submission / "requirements.txt").write_text("requests==2.32.3\n")
    (evaluator / "requirements.txt").write_text("sacrebleu==2.5.1\n")

    discovered = discover_fixtures(tmp_path / "fixtures", "add-greeting")[0]
    command = build_evaluator_command(
        discovered.eval_image,
        discovered.eval_command,
        submission,
        evaluator,
        "evaluator",
        install_submission_dependencies=not discovered.entrypoint_manages_dependencies,
    )

    assert discovered.entrypoint_manages_dependencies
    assert "/submission/requirements.txt" not in command[-5]
    assert "/eval/requirements.txt" in command[-5]


@pytest.mark.parametrize("value", ('"yes"', '"false"', "1", "[]"))
def test_fixture_rejects_non_boolean_entrypoint_dependency_mode(
    tmp_path: Path, value: str
) -> None:
    """Entrypoint dependency ownership is an explicit boolean contract."""
    fixture = make_fixture(tmp_path / "fixtures")
    (fixture / "manifest.yaml").write_text(
        "prompt: Add a greeting.\n"
        "eval_image: python:3.12-alpine\n"
        "eval_command: [python, /eval/check.py, /submission]\n"
        f"entrypoint_manages_dependencies: {value}\n"
    )

    with pytest.raises(ValueError, match="entrypoint_manages_dependencies"):
        discover_fixtures(tmp_path / "fixtures", "add-greeting")


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
    assert parse_args([]).order_by == "fixture"
    assert parse_args(["--order-by", "agent"]).order_by == "agent"
    with pytest.raises(SystemExit):
        parse_args(["--timeout-seconds", "0"])
    with pytest.raises(SystemExit):
        parse_args(["--order-by", "unknown"])


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


def test_ensure_searxng_ready_waits_and_propagates_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A campaign cannot start while its search service is unavailable."""
    commands: list[list[str]] = []

    def fake_run(
        command: list[str], *_args: object, **_kwargs: object
    ) -> tuple[int, None]:
        commands.append(command)
        return 7, None

    monkeypatch.setattr(runner, "_run", fake_run)

    code = runner._ensure_searxng_ready(
        tmp_path / "stdout.log", tmp_path / "stderr.log", ()
    )

    assert code == 7
    assert commands == [
        [
            "docker",
            "compose",
            "up",
            "-d",
            "--wait",
            "searxng",
        ]
    ]


def test_campaign_stops_before_build_when_searxng_is_unhealthy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Search readiness failure prevents every candidate and evaluator build."""
    fixture = Fixture(
        "fixture",
        "Make a change.",
        "busybox",
        ("true",),
        tmp_path / "fixture",
        tmp_path / "fixture" / "Dockerfile",
    )
    metadata = {
        "fixtures": {"fixture": {"outcome_group": "coding"}},
        "pairs": [{"fixture": "fixture", "agent": "tinycua"}],
    }
    monkeypatch.setattr(runner, "_ensure_searxng_ready", lambda *_args: 7)

    def unexpected_build(*_args: object) -> None:
        raise AssertionError("build must not start")

    monkeypatch.setattr(runner, "_build_campaign_images", unexpected_build)

    assert (
        runner._continue_campaign(
            (fixture,), ("tinycua",), tmp_path, False, 1, metadata, (), "fixture"
        )
        == 7
    )


def test_write_result_is_portable_and_sanitizes_environment(tmp_path: Path) -> None:
    """The per-pair result contains safe, portable execution evidence."""
    result_path = tmp_path / "result.json"
    stdout = tmp_path / "stdout.log"
    stderr = tmp_path / "stderr.log"
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
    assert result["schema_version"] == 2
    assert result["stdout_path"] == "stdout.log"
    assert result["stderr_path"] == "stderr.log"
    assert result["sanitized_environment"] == "environment.json"
    assert result["status"] == "passed"
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


def test_write_result_replaces_json_atomically(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed replacement cannot truncate an existing durable result."""
    result_path = tmp_path / "result.json"
    result_path.write_text('{"old": true}\n')
    stdout = tmp_path / "stdout.log"
    stderr = tmp_path / "stderr.log"
    stdout.write_text("")
    stderr.write_text("")

    def fail_replace(_source: Path, _destination: Path) -> None:
        raise OSError("replace failed")

    monkeypatch.setattr(runner.os, "replace", fail_replace)

    with pytest.raises(OSError, match="replace failed"):
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
        )

    assert result_path.read_text() == '{"old": true}\n'
    assert not list(tmp_path.glob(".*.tmp"))


def test_prune_workdir_removes_only_generated_heavy_directories(tmp_path: Path) -> None:
    """Submission cleanup preserves deliverables while dropping generated caches."""
    workdir = tmp_path / "workdir"
    keep = (
        "src/app.py",
        "docs/guide.md",
        "uv.lock",
        "data.sqlite3",
    )
    remove = (
        ".venv/bin/python",
        "venv/bin/python",
        "node_modules/pkg/index.js",
        "src/__pycache__/app.pyc",
        ".pytest_cache/state",
        ".agent_scripts/tool.py",
        ".tinycua_context_cache/context.json",
        ".tinycua-artifacts/log.json",
    )
    for relative in (*keep, *remove):
        path = workdir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("data")

    runner.prune_workdir(workdir)

    assert all((workdir / relative).is_file() for relative in keep)
    assert all(not (workdir / relative).exists() for relative in remove)


def test_outcomes_summary_replacement_is_atomic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed outcomes replacement leaves the previous summary readable."""
    outcomes_path = tmp_path / "outcomes.json"
    outcomes_path.write_text('{"previous": true}\n')
    metadata = {
        "fixtures": {
            "greeting": {
                "outcome_group": "coding",
                "fixture_revision": "fixture",
                "evaluator_revision": "evaluator",
            }
        },
        "pairs": [],
    }

    def fail_replace(_source: Path, _destination: Path) -> None:
        raise OSError("replace failed")

    monkeypatch.setattr(runner.os, "replace", fail_replace)

    with pytest.raises(OSError, match="replace failed"):
        runner.write_outcomes(outcomes_path, tmp_path, metadata)

    assert outcomes_path.read_text() == '{"previous": true}\n'
    assert not list(tmp_path.glob(".*.tmp"))


def test_model_settings_use_explicit_agent_allowlist() -> None:
    """Compatibility records effective agent controls but excludes judge config."""
    environment = {
        "EXPERIMENT_LLM_BASE_URL": "http://model/v1",
        "EXPERIMENT_LLM_MODEL": "model",
        "EXPERIMENT_LLM_PROVIDER": "provider",
        "EXPERIMENT_OPENCODE_MODEL": "open/model",
        "EXPERIMENT_HERMES_PROVIDER": "hermes-provider",
        "EXPERIMENT_HERMES_MAX_TURNS": "90",
        "EXPERIMENT_HERMES_PROCESS_POLL_TIMEOUT_SECONDS": "600",
        "EXPERIMENT_OPENCLAW_MODEL": "claw/model",
        "EXPERIMENT_OPENCLAW_THINKING": "off",
        "EXPERIMENT_TINYCUA_PROVIDER_TYPE": "openai-chat-completions",
        "EXPERIMENT_TINYCUA_MAX_CONTEXT": "262144",
        "EXPERIMENT_TINYCUA_RECOVERY_STRATEGY": "markdown_synthesis",
        "EXPERIMENT_TIMEOUT_SECONDS": "14400",
        "EXPERIMENT_SEARXNG_BASE_URL": "http://searxng:8080",
        "SEARXNG_URL": "http://searxng:8080",
        "SEARXNG_BASE_URL": "http://searxng:8080",
        "TINYCUA_SEARXNG_URL": "http://searxng:8080/search",
        "JUDGE_MODEL": "judge/model",
        "JUDGE_VARIANT": "high",
        "UNRELATED_MODEL_CACHE": "ignore",
    }

    settings = runner._model_settings(environment)

    assert settings == {
        name: value
        for name, value in environment.items()
        if name
        not in {"JUDGE_MODEL", "JUDGE_VARIANT", "UNRELATED_MODEL_CACHE"}
    }


def test_campaign_resource_names_include_optional_campaign_namespace() -> None:
    """Production campaign IDs isolate Docker resources across output roots."""
    first = "00000000-0000-4000-8000-000000000001"
    second = "00000000-0000-4000-8000-000000000002"

    assert state_volume_name("fixture", "tinycua", first) != state_volume_name(
        "fixture", "tinycua", second
    )
    assert workspace_volume_name(
        "fixture", "tinycua", first
    ) != workspace_volume_name("fixture", "tinycua", second)
    assert container_name("fixture", "tinycua", "agent", first) != container_name(
        "fixture", "tinycua", "agent", second
    )
    assert state_volume_name("fixture", "tinycua") == state_volume_name(
        "fixture", "tinycua"
    )


def test_atomic_json_fsyncs_file_and_parent_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Atomic JSON publication persists both file contents and directory entry."""
    calls: list[int] = []
    real_fsync = runner.os.fsync

    def record_fsync(descriptor: int) -> None:
        calls.append(descriptor)
        real_fsync(descriptor)

    monkeypatch.setattr(runner.os, "fsync", record_fsync)

    runner._atomic_write_json(tmp_path / "summary.json", {"ok": True})

    assert len(calls) == 2


@pytest.mark.parametrize(
    "change",
    (
        {"passed": False},
        {"status": "failed"},
        {"evaluator_outcome": "failed"},
        {
            "score": {
                "categories": {
                    "check": {"points": 2, "max_points": 1, "evidence": ["bad"]}
                },
                "total": 2,
                "pass_threshold": 1,
                "critical_categories": ["check"],
            }
        },
    ),
)
def test_schema_v2_result_rejects_inconsistent_outcomes(
    tmp_path: Path, change: dict[str, object]
) -> None:
    """A schema-v2 terminal marker is complete only when outcome fields agree."""
    run_root = tmp_path / "fixture" / "opencode"
    run_root.mkdir(parents=True)
    stdout = run_root / "stdout.log"
    stderr = run_root / "stderr.log"
    stdout.write_text("=== agent ===\nanswer\n")
    stderr.write_text("")
    write_result(
        run_root / "result.json",
        "fixture",
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
    )
    result_path = run_root / "result.json"
    result = json.loads(result_path.read_text())
    result.update(change)
    result_path.write_text(json.dumps(result))

    assert runner._valid_pair_result(result_path) is None


def test_schema_v2_result_requires_retained_workdir(tmp_path: Path) -> None:
    """A terminal pair is incomplete until its submission directory exists."""
    run_root = tmp_path / "fixture" / "opencode"
    run_root.mkdir(parents=True)
    stdout = run_root / "stdout.log"
    stderr = run_root / "stderr.log"
    stdout.write_text("")
    stderr.write_text("")
    write_result(
        run_root / "result.json",
        "fixture",
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
    )

    assert runner._valid_pair_result(run_root / "result.json") is None
    (run_root / "workdir").mkdir()
    assert runner._valid_pair_result(run_root / "result.json") is not None


def test_campaign_finalizes_invocation_after_unexpected_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Unexpected runner errors still leave terminal invocation provenance."""
    metadata = {"invocations": [{"started_at": "2026-07-29T00:00:00+00:00"}]}
    monkeypatch.setattr(runner, "_agent_compose_environments", lambda *_args: ({}, {}))
    monkeypatch.setattr(
        runner, "_prepare_campaign_metadata", lambda *_args: metadata
    )

    def fail(*_args: object) -> int:
        raise RuntimeError("unexpected")

    monkeypatch.setattr(runner, "_continue_campaign", fail)

    with pytest.raises(RuntimeError, match="unexpected"):
        runner._run_campaign((), (), tmp_path, False, 1)

    invocation = json.loads((tmp_path / "run_metadata.json").read_text())[
        "invocations"
    ][-1]
    assert invocation["status"] == "failed"
    assert invocation["exit_code"] == 1


def test_campaign_rejects_changed_execution_sources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One campaign cannot aggregate results from different runner code."""
    metadata = runner._new_metadata(1, {})
    monkeypatch.setattr(runner, "_execution_revision", lambda: "changed")

    with pytest.raises(ValueError, match="result_generation_revision"):
        runner._validate_campaign_compatibility(metadata, (), 1, {})


def test_external_image_is_restored_from_recorded_digest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A pruned external tag can be restored without accepting new bytes."""
    recorded_id = "sha256:recorded"
    digest = "busybox@sha256:digest"
    records = {
        "busybox": {
            "reference": "busybox",
            "id": recorded_id,
            "repo_digests": [digest],
        }
    }
    tagged = False
    commands = []

    def identity(image: str) -> dict[str, object]:
        identity_id = recorded_id if image == "busybox" and tagged else None
        return {"reference": image, "id": identity_id, "repo_digests": []}

    def run(command: list[str], *_args: object, **_kwargs: object) -> tuple[int, None]:
        nonlocal tagged
        commands.append(command)
        if command[:3] == ["docker", "image", "tag"]:
            tagged = True
        return 0, None

    monkeypatch.setattr(runner, "_image_identity", identity)
    monkeypatch.setattr(runner, "_run", run)

    code = runner._ensure_external_image(
        tmp_path / "run_metadata.json",
        {},
        records,
        "busybox",
        "busybox",
        {"reference": "busybox", "id": None, "repo_digests": []},
        recorded_id,
        tmp_path / "stdout.log",
        tmp_path / "stderr.log",
        1,
        (),
    )

    assert code == 0
    assert commands == [
        ["docker", "pull", digest],
        ["docker", "image", "tag", digest, "busybox"],
    ]


def test_digest_image_restoration_does_not_tag_a_digest_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An immutable digest reference is usable immediately after its pull."""
    recorded_id = "sha256:recorded"
    image = "busybox@sha256:digest"
    pulled = False
    commands = []

    def identity(reference: str) -> dict[str, object]:
        identity_id = recorded_id if reference == recorded_id or (reference == image and pulled) else None
        return {"reference": reference, "id": identity_id, "repo_digests": [image]}

    def run(command: list[str], *_args: object, **_kwargs: object) -> tuple[int, None]:
        nonlocal pulled
        commands.append(command)
        if command[:2] == ["docker", "pull"]:
            pulled = True
        return 0, None

    monkeypatch.setattr(runner, "_image_identity", identity)
    monkeypatch.setattr(runner, "_run", run)

    code = runner._ensure_external_image(
        tmp_path / "run_metadata.json",
        {},
        {image: {"reference": image, "id": recorded_id, "repo_digests": [image]}},
        image,
        image,
        {"reference": image, "id": None, "repo_digests": []},
        recorded_id,
        tmp_path / "stdout.log",
        tmp_path / "stderr.log",
        1,
        (),
    )

    assert code == 0
    assert commands == [["docker", "pull", image]]


def test_evaluator_images_are_recorded_per_fixture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fixtures sharing a mutable tag cannot reuse each other's evaluator build."""
    fixtures = tuple(
        Fixture(
            name,
            "Make a change.",
            "shared-evaluator",
            ("true",),
            tmp_path / name,
            tmp_path / name / "docker" / "Dockerfile",
            evaluator_dockerfile=tmp_path / name / "eval" / "Dockerfile",
        )
        for name in ("first", "second")
    )
    metadata = {
        "images": {
            "harnesses": {},
            "evaluators": {},
            "decorators": {},
            "candidates": {},
        }
    }
    evaluator_keys = []

    def ensure(
        _metadata_path: Path,
        _metadata: dict[str, object],
        records: dict[str, object],
        key: str,
        image: str,
        *_args: object,
    ) -> int:
        records[key] = {"reference": image, "id": f"sha256:{key}"}
        if records is metadata["images"]["evaluators"]:
            evaluator_keys.append(key)
        return 0

    monkeypatch.setattr(runner, "_ensure_image", ensure)

    for fixture in fixtures:
        runner._ensure_evaluator_image(
            fixture,
            {"tinycua": "tinycua-base"},
            tmp_path / "run_metadata.json",
            metadata,
            tmp_path / "stdout.log",
            tmp_path / "stderr.log",
            1,
            (),
        )

    assert evaluator_keys == ["first", "second"]


def test_schema_v1_failed_setup_can_migrate_without_workdir(tmp_path: Path) -> None:
    """Legacy pre-execution failures gain the schema-v2 empty workdir artifact."""
    run_root = tmp_path / "fixture" / "opencode"
    run_root.mkdir(parents=True)
    (run_root / "agent.stdout.log").write_text("")
    (run_root / "agent.stderr.log").write_text("build failed\n")
    (run_root / "container_environment.json").write_text("{}\n")
    (run_root / "result.json").write_text(
        json.dumps(
            {
                "fixture": "fixture",
                "agent": "opencode",
                "passed": False,
                "agent_exit_code": 125,
                "evaluator_exit_code": 125,
            }
        )
    )

    assert runner._valid_pair_result(run_root / "result.json") is not None
    runner._upgrade_campaign_artifacts(tmp_path, {"schema_version": 1})
    assert (run_root / "workdir").is_dir()
    assert runner._valid_pair_result(run_root / "result.json") is not None


def test_migrated_campaign_cannot_register_new_pairs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Unknown legacy runner inputs seal migrated evidence against aggregation."""
    fixture_root = tmp_path / "fixture-source"
    (fixture_root / "workdir").mkdir(parents=True)
    fixture = Fixture(
        "fixture",
        "Make a change.",
        "busybox",
        ("true",),
        fixture_root,
        fixture_root / "docker" / "Dockerfile",
    )
    metadata = {
        "campaign_id": "00000000-0000-0000-0000-000000000000",
        "legacy_results": True,
        "fixtures": {"fixture": {"outcome_group": "coding"}},
        "pairs": [{"fixture": "fixture", "agent": "opencode"}],
    }
    monkeypatch.setattr(runner, "_load_campaign", lambda _root: (metadata, False))
    monkeypatch.setattr(runner, "_validate_campaign_compatibility", lambda *_args: None)

    with pytest.raises(ValueError, match="sealed"):
        runner._prepare_campaign_metadata(
            tmp_path, (fixture,), ("opencode",), False, 1, {}
        )
    assert not (tmp_path / "run_metadata.json").exists()


def test_schema_v1_migration_keeps_sources_until_result_is_durable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed migration cannot delete logs still named by the old result."""
    run_root = tmp_path / "fixture" / "opencode"
    (run_root / "workdir").mkdir(parents=True)
    (run_root / "agent.stdout.log").write_text("answer\n")
    (run_root / "agent.stderr.log").write_text("")
    (run_root / "container_environment.json").write_text("{}\n")
    (run_root / "result.json").write_text(
        json.dumps(
            {
                "fixture": "fixture",
                "agent": "opencode",
                "passed": True,
                "agent_exit_code": 0,
                "evaluator_exit_code": 0,
                "stdout_path": "agent.stdout.log",
                "stderr_path": "agent.stderr.log",
                "sanitized_environment": "container_environment.json",
            }
        )
    )
    real_write = runner._atomic_write_json

    def fail_result(path: Path, value: object) -> None:
        if path.name == "result.json":
            raise OSError("result write failed")
        real_write(path, value)

    monkeypatch.setattr(runner, "_atomic_write_json", fail_result)

    with pytest.raises(OSError, match="result write failed"):
        runner._upgrade_campaign_artifacts(tmp_path, {"schema_version": 1})

    assert (run_root / "agent.stdout.log").is_file()
    assert (run_root / "agent.stderr.log").is_file()


def test_pair_cleans_workspace_volume_after_artifact_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Artifact failures cannot bypass final Docker volume cleanup."""
    fixture_root = tmp_path / "fixture"
    (fixture_root / "workdir").mkdir(parents=True)
    fixture = Fixture(
        "fixture",
        "Make a change.",
        "busybox",
        ("true",),
        fixture_root,
        fixture_root / "docker" / "Dockerfile",
    )
    removals = []

    monkeypatch.setattr(runner, "_agent_compose_environments", lambda *_args: ({}, {}))
    monkeypatch.setattr(runner, "_write_override", lambda *_args: None)
    monkeypatch.setattr(
        runner,
        "_remove_workspace_volume",
        lambda name, _timeout: removals.append(name),
    )
    monkeypatch.setattr(runner, "_seed_workspace_volume", lambda *_args: None)

    def run(
        _command: list[str], stdout: Path, stderr: Path, *_args: object, **_kwargs: object
    ) -> tuple[int, None]:
        stdout.write_text("")
        stderr.write_text("")
        return 0, None

    monkeypatch.setattr(runner, "_run", run)

    def export(*args: object) -> None:
        Path(args[3]).mkdir()

    monkeypatch.setattr(runner, "_export_workspace_volume", export)
    monkeypatch.setattr(
        runner, "_evaluate_submission", lambda *_args: (0, None, None, None, None)
    )
    monkeypatch.setattr(
        runner,
        "prune_workdir",
        lambda _path: (_ for _ in ()).throw(OSError("prune failed")),
    )

    with pytest.raises(OSError, match="prune failed"):
        runner._execute_pair(
            fixture, "opencode", "image", tmp_path / "run", 1, "campaign"
        )

    assert len(removals) == 2


def test_replacement_publication_restores_previous_pair_on_swap_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed staging rename leaves the prior complete pair public."""
    public = tmp_path / "fixture" / "opencode"
    staging = public.with_name(".opencode.staging")
    for run_root, marker in ((public, "old"), (staging, "new")):
        (run_root / "workdir").mkdir(parents=True)
        (run_root / "workdir" / "marker.txt").write_text(marker)
        stdout = run_root / "stdout.log"
        stderr = run_root / "stderr.log"
        stdout.write_text("=== agent ===\nanswer\n")
        stderr.write_text("")
        write_result(
            run_root / "result.json",
            "fixture",
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
        )
    real_replace = Path.replace

    def fail_staging_replace(source: Path, target: Path) -> Path:
        if source == staging:
            raise OSError("publication failed")
        return real_replace(source, target)

    monkeypatch.setattr(Path, "replace", fail_staging_replace)

    with pytest.raises(OSError, match="publication failed"):
        runner._publish_replacement(public, "fixture", "opencode")

    assert (public / "workdir" / "marker.txt").read_text() == "old"
    assert runner._valid_pair_result(public / "result.json") is not None
