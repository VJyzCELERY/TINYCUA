"""Repository contracts for the native GitHub CLI migration."""

from pathlib import Path


ROOT = Path(__file__).parents[3]


def test_repository_has_no_github_wrapper_or_references():
    wrapper_name = "gh" + ".py"
    assert not (ROOT / ".agents/scripts" / wrapper_name).exists()
    for path in [ROOT / "AGENTS.md", *(ROOT / ".agents").rglob("*")]:
        if ".agents/local" in path.as_posix():
            continue
        if path.is_file() and path.suffix in {".md", ".py", ".json", ".yaml", ".yml"}:
            assert wrapper_name not in path.read_text(encoding="utf-8"), path


def test_github_skill_requires_explicit_repository_and_file_inputs():
    skill = (ROOT / ".agents/skills/gh/SKILL.md").read_text(encoding="utf-8")
    for contract in ("--repo OWNER/REPO", "--body-file", "gh api --input", "--paginate"):
        assert contract in skill
    assert (
        "repos/OWNER/REPO/pulls/<number> --input ./tmp/pr-metadata.json" in skill
    )
    assert (
        "repos/OWNER/REPO/issues/<number>/assignees --input ./tmp/assignees.json"
        in skill
    )
    assert "gh pr edit" not in skill
    assert "--slurp" not in skill
    assert "--jq '.[]'" in skill

    plan = (ROOT / ".agents/commands/plan.md").read_text(encoding="utf-8")
    assert "--slurp" not in plan
    assert "--jq '.[]'" in plan
