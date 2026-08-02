"""Behavior tests for /goal role configuration."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
import goal_roles


def run(root: Path, *args: str) -> tuple[int, dict | None, str]:
    """Run role configuration resolution against an isolated repository root."""
    output: list[str] = []
    errors: list[str] = []
    code = goal_roles.main(list(args), root=root, output=output.append, error=errors.append)
    return code, json.loads(output[0]) if output else None, "\n".join(errors)


def repository(root: Path) -> Path:
    """Create the minimum safe repository layout."""
    templates = root / ".agents/templates"
    templates.mkdir(parents=True)
    source = Path(goal_roles.__file__).parent.parent / "templates/goal-roles.default.json"
    (templates / source.name).write_bytes(source.read_bytes())
    return root


def test_goal_configuration_is_initialized_per_goal(tmp_path):
    root = repository(tmp_path)

    code, result, error = run(root, "preflight", "Owner/Repo#42")

    assert (code, error) == (0, "")
    assert result == {
        "configuration": "missing",
        "goal": "owner/repo#42",
    }

    code, _, error = run(root, "resolve", "Owner/Repo#42", "planner")
    assert code == 1
    assert "missing" in error

    code, _, error = run(
        root,
        "init",
        "Owner/Repo#42",
        "--planner",
        "current",
        "--worker",
        "codex",
        "--worker-model",
        "opaque-model",
        "--reviewer",
        "current",
    )

    assert (code, error) == (0, "")
    code, result, error = run(root, "resolve", "Owner/Repo#42", "worker")
    assert (code, error) == (0, "")
    assert result == {
        "goal": "owner/repo#42",
        "harness": "codex",
        "model": "opaque-model",
        "role": "worker",
        "source": "local",
        "variant": None,
    }

    code, result, error = run(root, "preflight", "Owner/Repo#43")
    assert (code, error) == (0, "")
    assert result == {"configuration": "missing", "goal": "owner/repo#43"}


def test_init_rejects_external_harness_without_model(tmp_path):
    root = repository(tmp_path)

    code, _, error = run(
        root,
        "init",
        "Owner/Repo#42",
        "--planner",
        "opencode",
        "--worker",
        "current",
        "--reviewer",
        "current",
    )

    assert code == 1
    assert "model" in error


@pytest.mark.parametrize(
    "alias", ("-m", "-mother-model", "-m=other-model", "--model=other-model")
)
def test_verify_rejects_any_unconfigured_model_selector(tmp_path, alias):
    root = repository(tmp_path)
    assert run(root, "preflight", "Owner/Repo#42")[0] == 0
    assert (
        run(
            root,
            "init",
            "Owner/Repo#42",
            "--worker",
            "codex",
            "--worker-model",
            "configured-model",
        )[0]
        == 0
    )
    command = [
        "verify",
        "Owner/Repo#42",
        "worker",
        "--",
        "codex",
        "exec",
        "--model",
        "configured-model",
        alias,
    ]
    if alias == "-m":
        command.append("other-model")

    code, _, error = run(root, *command)

    assert code == 1
    assert "model" in error


def test_resolve_cli_reads_process_arguments():
    result = subprocess.run(
        [
            sys.executable,
            str(Path(goal_roles.__file__)),
            "resolve",
            "owner/repo#42",
            "worker",
        ],
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 1
    assert "missing" in result.stdout


def test_resolve_rejects_unsafe_per_goal_configuration(tmp_path):
    root = repository(tmp_path)
    override = root / ".agents/local/state/goals/owner_repo_42/roles.json"
    override.parent.mkdir(parents=True)
    override.write_text(
        '{"schema_version": 1, "roles": {'
        '"planner": {"harness": "current", "model": null}, '
        '"worker": {"harness": "codex", "model": "TOKEN=unsafe"}, '
        '"reviewer": {"harness": "current", "model": null}}}',
        encoding="utf-8",
    )
    (override.parent / "roles.confirmed").write_text("confirmed\n", encoding="utf-8")

    code, _, error = run(root, "resolve", "Owner/Repo#42", "worker")

    assert code == 1
    assert "model" in error
