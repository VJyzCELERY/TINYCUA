"""Behavior tests for ignored local-first issue bundles."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import local_issue


def documents() -> dict[str, str]:
    """Return the complete local bundle document set."""
    return {name: f"# {name}\n" for name in local_issue.DOCUMENTS}


def promotion() -> dict:
    """Return one complete verified remote mapping."""
    base = "https://github.com/acme/widgets/issues"
    return {
        "repository": "acme/widgets",
        "issue": {"number": 7, "url": f"{base}/7"},
        "specs": {
            "number": 8,
            "url": f"{base}/8",
            "documents": {
                name: f"{base}/8#issuecomment-{index}"
                for index, name in enumerate(local_issue.SPECS_DOCUMENTS, 1)
            },
        },
    }


def git(repository: Path, *args: str) -> None:
    """Run one successful Git command in a disposable repository."""
    subprocess.run(["git", *args], cwd=repository, check=True, capture_output=True)


def repository(tmp_path: Path, branch: str = "feat/7-local") -> Path:
    """Create a worktree whose current branch is *branch*."""
    git(tmp_path, "init", "-b", "main")
    git(tmp_path, "config", "user.email", "tests@example.com")
    git(tmp_path, "config", "user.name", "Tests")
    (tmp_path / "README.md").write_text("# Test\n", encoding="utf-8")
    git(tmp_path, "add", "README.md")
    git(tmp_path, "commit", "-m", "initial")
    git(tmp_path, "checkout", "-b", branch)
    return tmp_path


def run(root: Path, *args: str) -> tuple[int, str, str]:
    """Run the local-bundle CLI against an isolated worktree."""
    output: list[str] = []
    errors: list[str] = []
    code = local_issue.main(
        list(args), root=root, output=output.append, error=errors.append
    )
    return code, "\n".join(output), "\n".join(errors)


def test_local_bundle_cli_resumes_each_phase_and_gates_promotion(tmp_path):
    root = repository(tmp_path)
    inputs = root / "inputs"
    inputs.mkdir()
    for name, content in documents().items():
        (inputs / name).write_text(content, encoding="utf-8")
    paths = {
        "--draft": inputs / "draft.md",
        "--spec": inputs / "spec.md",
        "--design": inputs / "design.md",
        "--implementation-plan": inputs / "implementation-plan.md",
        "--task": inputs / "task.md",
    }
    create_args = [
        "create",
        "resume-local",
        "feat/7-local",
        "--worktree",
        str(root),
    ]
    for option, path in paths.items():
        create_args.extend((option, str(path)))

    assert run(root, *create_args)[0] == 0
    for phase in ("planned", "implemented", "reviewed"):
        assert run(root, "validate", "resume-local")[0] == 0
        assert run(root, "transition", "resume-local", phase)[0] == 0

    mapping = root / "promotion.json"
    mapping.write_text(json.dumps(promotion()), encoding="utf-8")
    assert run(root, "promote", "resume-local", "--mapping", str(mapping))[0] == 0
    assert json.loads(run(root, "validate", "resume-local")[1])["phase"] == "promoted"

    assert run(root, *create_args)[0] == 0
    assert run(root, "transition", "resume-local", "planned")[0] == 1


def test_create_bundle_retains_required_documents_and_branch(tmp_path):
    root = repository(tmp_path)
    bundle = local_issue.create_bundle(
        root, "ship-local-first", "feat/7-local", root, documents()
    )

    assert bundle == root / ".agents/local/issues/ship-local-first"
    assert {path.name for path in bundle.iterdir()} == {
        *local_issue.DOCUMENTS,
        "state.json",
    }
    assert local_issue.validate_bundle(root, "ship-local-first") == {
        "identifier": "ship-local-first",
        "branch": "feat/7-local",
        "worktree": str(root),
        "phase": "issue",
        "promotion": None,
    }


def test_bundle_validation_rejects_unsafe_incomplete_or_unresolved_content(tmp_path):
    root = repository(tmp_path)
    with pytest.raises(ValueError, match="lower-kebab"):
        local_issue.create_bundle(root, "../escape", "feat/7-local", root, documents())

    bundle = local_issue.create_bundle(
        root, "safe-bundle", "feat/7-local", root, documents()
    )
    (bundle / "task.md").unlink()
    with pytest.raises(ValueError, match="missing"):
        local_issue.validate_bundle(root, "safe-bundle")

    (bundle / "task.md").write_text("[NEEDS CLARIFICATION]", encoding="utf-8")
    with pytest.raises(ValueError, match="clarification"):
        local_issue.validate_bundle(root, "safe-bundle")


def test_bundle_validation_rejects_state_symlink_outside_bundle(tmp_path):
    root = repository(tmp_path)
    bundle = local_issue.create_bundle(
        root, "safe-bundle", "feat/7-local", root, documents()
    )
    escaped = root / "outside-state.json"
    escaped.write_text("{}", encoding="utf-8")
    (bundle / "state.json").unlink()
    (bundle / "state.json").symlink_to(escaped)

    with pytest.raises(ValueError, match="state escapes"):
        local_issue.validate_bundle(root, "safe-bundle")


def test_record_promotion_is_idempotent_and_rejects_conflicting_mapping(tmp_path):
    root = repository(tmp_path)
    local_issue.create_bundle(root, "promote-once", "feat/7-local", root, documents())

    with pytest.raises(ValueError, match="reviewed"):
        local_issue.record_promotion(root, "promote-once", promotion())
    local_issue.record_phase(root, "promote-once", "planned")
    local_issue.record_phase(root, "promote-once", "implemented")
    local_issue.record_phase(root, "promote-once", "reviewed")
    first = local_issue.record_promotion(root, "promote-once", promotion())
    assert first["promotion"] == promotion()
    assert local_issue.record_promotion(root, "promote-once", promotion()) == first

    conflict = promotion() | {
        "issue": {"number": 9, "url": "https://github.com/acme/widgets/issues/9"}
    }
    with pytest.raises(ValueError, match="conflicts"):
        local_issue.record_promotion(root, "promote-once", conflict)

    with pytest.raises(ValueError, match="promotion issue"):
        local_issue.record_promotion(root, "promote-once", promotion() | {"issue": []})
