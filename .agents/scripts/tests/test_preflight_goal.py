"""Behavior tests for goal preflight."""

import importlib.util
import json
import sys
from pathlib import Path


def module():
    """Load the hyphenated goal-preflight script."""
    path = Path(__file__).parent.parent / "preflight-goal.py"
    sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location("preflight_goal", path)
    assert spec and spec.loader
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def test_preflight_reports_missing_remote_state_and_configuration(tmp_path):
    preflight = module()
    templates = tmp_path / ".agents/templates"
    templates.mkdir(parents=True)
    (templates / "goal-roles.default.json").write_text(
        '{"schema_version": 1, "roles": {'
        '"planner": {"harness": "current", "model": null}, '
        '"worker": {"harness": "current", "model": null}, '
        '"reviewer": {"harness": "current", "model": null}}}',
        encoding="utf-8",
    )
    state_template = Path(preflight.workflow_state.__file__).parent.parent / "templates/goal-state.default.json"
    (templates / state_template.name).write_bytes(state_template.read_bytes())
    output: list[str] = []
    errors: list[str] = []

    code = preflight.main(
        ["Owner/Repo#42", "--format", "json"],
        root=tmp_path,
        output=output.append,
        error=errors.append,
    )

    assert (code, errors) == (0, [])
    assert json.loads(output[0]) == {
        "configuration": "missing",
        "goal": "owner/repo#42",
        "state": "missing",
    }
    assert json.loads(
        (
            tmp_path
            / ".agents/local/state/goals/owner_repo_42/roles.json"
        ).read_text(encoding="utf-8")
    ) == json.loads(
        (templates / "goal-roles.default.json").read_text(encoding="utf-8")
    )


def test_preflight_initializes_goal_state_from_template(tmp_path):
    preflight = module()
    templates = tmp_path / ".agents/templates"
    templates.mkdir(parents=True)
    for name in ("goal-roles.default.json", "goal-state.default.json"):
        source = Path(preflight.workflow_state.__file__).parent.parent / "templates" / name
        (templates / name).write_bytes(source.read_bytes())
    output: list[str] = []
    errors: list[str] = []

    code = preflight.main(
        [
            "Owner/Repo#42",
            "--title",
            "Ship goal preflight",
            "--url",
            "https://github.com/Owner/Repo/issues/42",
            "--objective",
            "Initialize goal state",
            "--format",
            "json",
        ],
        root=tmp_path,
        output=output.append,
        error=errors.append,
    )

    assert (code, errors) == (0, [])
    assert json.loads(output[0])["state"] == "valid"


def test_preflight_rejects_an_invalid_remote_target_before_copying_templates(tmp_path):
    preflight = module()
    templates = tmp_path / ".agents/templates"
    templates.mkdir(parents=True)
    for name in ("goal-roles.default.json", "goal-state.default.json"):
        source = Path(preflight.workflow_state.__file__).parent.parent / "templates" / name
        (templates / name).write_bytes(source.read_bytes())
    output: list[str] = []
    errors: list[str] = []

    code = preflight.main(
        ["owner-/repo#42", "--format", "json"],
        root=tmp_path,
        output=output.append,
        error=errors.append,
    )

    assert code == 1
    assert not output
    assert errors
    assert not (tmp_path / ".agents/local").exists()
