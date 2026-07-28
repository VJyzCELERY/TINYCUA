import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest


SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location(
    "review_workflow", SCRIPTS / "review_workflow.py"
)
review_workflow = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(review_workflow)


def test_native_gh_timeout_fails_closed(monkeypatch):
    monkeypatch.setattr(
        review_workflow.subprocess,
        "run",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            subprocess.TimeoutExpired(["gh"], 30)
        ),
    )

    with pytest.raises(RuntimeError, match="timed out"):
        review_workflow._gh_json(["gh", "api", "user"])


def test_inspect_remote_consumes_every_paginated_ndjson_page(monkeypatch):
    calls = []
    thread = {
        "id": "THREAD",
        "isResolved": False,
        "comments": {
            "nodes": [
                {
                    "url": "https://github.com/acme/widgets/pull/7#discussion_r9",
                    "body": "feedback",
                    "isMinimized": False,
                    "author": {"login": "bot", "__typename": "Bot"},
                }
            ],
            "pageInfo": {"hasNextPage": False},
        },
    }

    def run(command, **_kwargs):
        calls.append(command)
        if command[:3] == ["gh", "api", "user"]:
            output = "agent\n"
        elif command[:3] == ["gh", "pr", "view"]:
            output = json.dumps(
                {
                    "url": "https://github.com/acme/widgets/pull/7",
                    "headRefOid": "b" * 40,
                }
            )
        elif "reviewThreads" in command[command.index("-f") + 1]:
            output = "\n".join(
                json.dumps({"nodes": nodes}) for nodes in ([thread], [thread])
            )
        else:
            output = json.dumps({"nodes": []})
        return subprocess.CompletedProcess(command, 0, stdout=output, stderr="")

    monkeypatch.setattr(review_workflow.subprocess, "run", run)

    state = review_workflow._inspect_remote("https://github.com/acme/widgets/pull/7")

    api_calls = [call for call in calls if call[:3] == ["gh", "api", "graphql"]]
    assert len(state["items"]) == 2
    assert all("--paginate" in call and "--slurp" not in call for call in api_calls)
    assert all("--jq" in call for call in api_calls)


def test_inspect_remote_rejects_malformed_paginated_ndjson(monkeypatch):
    result = subprocess.CompletedProcess(
        ["gh", "api", "graphql"],
        0,
        stdout='{"nodes": []}\nnot-json\n',
        stderr="",
    )
    monkeypatch.setattr(
        review_workflow.subprocess, "run", lambda *_args, **_kwargs: result
    )

    with pytest.raises(RuntimeError, match="malformed paginated GraphQL JSON"):
        review_workflow._graphql_pages("query", "acme", "widgets", "7", "reviews")


def report(head="b" * 40, items=None):
    remote = ""
    if items is not None:
        import json

        payload = {
            "repository": "https://github.com/acme/widgets",
            "pull_request": "https://github.com/acme/widgets/pull/7",
            "head": head,
            "items": items,
        }
        remote = f"\n## Remote Feedback\n\n```json\n{json.dumps(payload)}\n```\n"
    return f"""# Review Report: Test

**Branch**: feature
**Commit Range**: {"a" * 40}...{head}

## Findings

No findings.
{remote}"""


def test_finalize_preserves_source_when_logging_fails(tmp_path):
    source = tmp_path / "REVIEW_test.md"
    source.write_text(report())

    with pytest.raises(RuntimeError, match="log failed"):
        review_workflow.finalize_report(
            source,
            tmp_path / "archive",
            current_head="b" * 40,
            log_report=lambda _: (_ for _ in ()).throw(RuntimeError("log failed")),
        )

    assert source.exists()
    assert not (tmp_path / "archive" / source.name).exists()


def test_finalize_logs_then_archives_before_fresh_report(tmp_path):
    source = tmp_path / "REVIEW_test.md"
    source.write_text(report())
    events = []

    result = review_workflow.finalize_report(
        source,
        tmp_path / "archive",
        current_head="b" * 40,
        log_report=lambda _: events.append("log"),
        create_fresh=lambda: events.append("fresh"),
    )

    assert events == ["log", "fresh"]
    assert result["state"] == "ARCHIVED"
    assert not source.exists()
    assert Path(result["archive"]).exists()
    assert result["archive"].endswith(f"__feature__{'b' * 12}.md")


def test_finalize_allows_repeated_branch_cycles_but_rejects_exact_cycle(tmp_path):
    archive = tmp_path / "archives"
    first = tmp_path / "REVIEW_test.md"
    first.write_text(report(head="b" * 40))
    first_result = review_workflow.finalize_report(
        first, archive, "b" * 40, log_report=lambda _: None
    )
    second = tmp_path / "REVIEW_test.md"
    second.write_text(report(head="c" * 40))
    second_result = review_workflow.finalize_report(
        second, archive, "c" * 40, log_report=lambda _: None
    )
    duplicate = tmp_path / "REVIEW_test.md"
    duplicate.write_text(report(head="b" * 40))

    with pytest.raises(ValueError, match="archive already exists"):
        review_workflow.finalize_report(
            duplicate, archive, "b" * 40, log_report=lambda _: None
        )

    assert first_result["archive"] != second_result["archive"]
    assert duplicate.exists()


def test_finalize_rejects_archive_symlink_escape_and_preserves_report(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(review_workflow.repo_guard, "repo_root", lambda: tmp_path)
    source = tmp_path / "REVIEW_test.md"
    source.write_text(report())
    outside = tmp_path.parent / f"outside-{tmp_path.name}"
    outside.mkdir()
    archive = tmp_path / "archives"
    archive.symlink_to(outside, target_is_directory=True)
    try:
        with pytest.raises(ValueError, match="escapes"):
            review_workflow.finalize_report(
                source, archive, "b" * 40, log_report=lambda _: None
            )
        assert source.exists()
    finally:
        outside.rmdir()


def authoritative(items):
    for item in items:
        item.setdefault("node_id", "NODE_ID")
    return {
        "repository": "https://github.com/acme/widgets",
        "pull_request": "https://github.com/acme/widgets/pull/7",
        "head": "b" * 40,
        "actor": "agent",
        "items": items,
    }


def test_remote_plan_is_dry_run_without_sync_gate_and_validates_identity_head(tmp_path):
    path = tmp_path / "REVIEW_test.md"
    path.write_text(
        report(
            items=[
                {
                    "url": "https://github.com/acme/widgets/pull/7#discussion_r9",
                    "reply": "fixed",
                }
            ]
        )
    )

    plan = review_workflow.build_remote_plan(
        path,
        repository="https://github.com/acme/widgets",
        pull_request="https://github.com/acme/widgets/pull/7",
        remote_head="b" * 40,
        inspect=lambda *_: authoritative(
            [
                {
                    "url": "https://github.com/acme/widgets/pull/7#discussion_r9",
                    "author": "bot",
                    "author_type": "Bot",
                    "active_human": False,
                }
            ]
        ),
    )
    assert plan["writes_performed"] is False
    assert plan["actions"][0]["command"] == "resolve"

    with pytest.raises(ValueError, match="head"):
        review_workflow.build_remote_plan(
            path,
            "https://github.com/acme/widgets",
            "https://github.com/acme/widgets/pull/7",
            "c" * 40,
        )
    with pytest.raises(ValueError, match="repository"):
        review_workflow.build_remote_plan(
            path,
            "https://github.com/other/widgets",
            "https://github.com/other/widgets/pull/7",
            "b" * 40,
        )


def test_finalize_refuses_report_not_at_current_head(tmp_path):
    source = tmp_path / "REVIEW_test.md"
    source.write_text(report())

    with pytest.raises(ValueError, match="STALE"):
        review_workflow.finalize_report(source, tmp_path / "archive", "c" * 40)

    assert source.exists()


def test_finalize_derives_current_head_when_not_supplied(tmp_path, monkeypatch):
    source = tmp_path / "REVIEW_test.md"
    source.write_text(report())
    completed = review_workflow.subprocess.CompletedProcess(
        ["git", "rev-parse", "HEAD"], 0, stdout=f"{'b' * 40}\n", stderr=""
    )
    monkeypatch.setattr(
        review_workflow.subprocess, "run", lambda *_args, **_kwargs: completed
    )

    result = review_workflow.finalize_report(
        source, tmp_path / "archive", log_report=lambda _: None
    )

    assert result["state"] == "ARCHIVED"


def test_cli_gates_only_remote_apply_with_sync_remote(monkeypatch):
    monkeypatch.setattr(
        review_workflow,
        "build_remote_plan",
        lambda *_args: {"state": "REMOTE_PLAN"},
    )

    common = [
        "report.md",
        "--repository",
        "https://github.com/acme/widgets",
        "--pull-request",
        "https://github.com/acme/widgets/pull/7",
        "--remote-head",
        "b" * 40,
    ]
    assert review_workflow.main(["remote-plan", *common]) == 0
    with pytest.raises(SystemExit):
        review_workflow.main(["remote-apply", *common])


def test_remote_plan_blocks_authoritative_human_discussion(tmp_path):
    path = tmp_path / "REVIEW_test.md"
    path.write_text(
        report(
            items=[
                {
                    "url": "https://github.com/acme/widgets/pull/7#discussion_r9",
                    "reply": "fixed",
                }
            ]
        )
    )

    with pytest.raises(ValueError, match="human discussion"):
        review_workflow.build_remote_plan(
            path,
            "https://github.com/acme/widgets",
            "https://github.com/acme/widgets/pull/7",
            "b" * 40,
            inspect=lambda *_: authoritative(
                [
                    {
                        "url": "https://github.com/acme/widgets/pull/7#discussion_r9",
                        "author": "alice",
                        "author_type": "User",
                        "active_human": True,
                    }
                ]
            ),
        )


def test_remote_plan_ignores_report_authorization_fields(tmp_path):
    url = "https://github.com/acme/widgets/pull/7#pullrequestreview-10"
    path = tmp_path / "REVIEW_test.md"
    path.write_text(report(items=[{"url": url, "reply": ""}]))

    with pytest.raises(ValueError, match="actor-owned"):
        review_workflow.build_remote_plan(
            path,
            "https://github.com/acme/widgets",
            "https://github.com/acme/widgets/pull/7",
            "b" * 40,
            inspect=lambda *_: authoritative(
                [
                    {
                        "url": url,
                        "author": "other",
                        "author_type": "Bot",
                        "active_human": False,
                    }
                ]
            ),
        )


def test_remote_apply_replies_before_resolve_and_is_idempotent(tmp_path):
    path = tmp_path / "REVIEW_test.md"
    path.write_text(
        report(
            items=[
                {
                    "url": "https://github.com/acme/widgets/pull/7#discussion_r9",
                    "reply": "Addressed in the linked review cycle.",
                }
            ]
        )
    )
    calls = []
    verification = iter([[], ["https://github.com/acme/widgets/pull/7#discussion_r9"]])

    result = review_workflow.apply_remote_feedback(
        path,
        "https://github.com/acme/widgets",
        "https://github.com/acme/widgets/pull/7",
        "b" * 40,
        True,
        run_gh=lambda args: calls.append(args) or 0,
        verify=lambda _plan: next(verification),
        inspect=lambda *_: authoritative(
            [
                {
                    "url": "https://github.com/acme/widgets/pull/7#discussion_r9",
                    "author": "bot",
                    "author_type": "Bot",
                    "active_human": False,
                    "bodies": [],
                }
            ]
        ),
    )

    assert [call[:3] for call in calls] == [
        ["gh", "api", "--method"],
        ["gh", "api", "graphql"],
    ]
    assert result["state"] == "REMOTE_APPLIED"
    assert result["writes_performed"] is True

    calls.clear()
    result = review_workflow.apply_remote_feedback(
        path,
        "https://github.com/acme/widgets",
        "https://github.com/acme/widgets/pull/7",
        "b" * 40,
        True,
        run_gh=lambda args: calls.append(args) or 0,
        verify=lambda plan: [item["url"] for item in plan["actions"]],
        inspect=lambda *_: authoritative(
            [
                {
                    "url": "https://github.com/acme/widgets/pull/7#discussion_r9",
                    "author": "bot",
                    "author_type": "Bot",
                    "active_human": False,
                    "bodies": [],
                }
            ]
        ),
    )
    assert calls == []
    assert result["state"] == "REMOTE_APPLIED"


def test_remote_apply_only_minimizes_actor_owned_reviews(tmp_path):
    path = tmp_path / "REVIEW_test.md"
    path.write_text(
        report(
            items=[
                {
                    "url": "https://github.com/acme/widgets/pull/7#pullrequestreview-10",
                    "reply": "",
                }
            ]
        )
    )

    with pytest.raises(ValueError, match="actor-owned"):
        review_workflow.apply_remote_feedback(
            path,
            "https://github.com/acme/widgets",
            "https://github.com/acme/widgets/pull/7",
            "b" * 40,
            True,
            inspect=lambda *_: authoritative(
                [
                    {
                        "url": "https://github.com/acme/widgets/pull/7#pullrequestreview-10",
                        "author": "other",
                        "author_type": "Bot",
                        "active_human": False,
                    }
                ]
            ),
        )


def test_remote_apply_partial_failure_preserves_report(tmp_path):
    path = tmp_path / "REVIEW_test.md"
    content = report(
        items=[
            {
                "url": "https://github.com/acme/widgets/pull/7#discussion_r9",
                "reply": "Addressed.",
            }
        ]
    )
    path.write_text(content)
    outcomes = iter([0, 7])

    with pytest.raises(RuntimeError, match="partial"):
        review_workflow.apply_remote_feedback(
            path,
            "https://github.com/acme/widgets",
            "https://github.com/acme/widgets/pull/7",
            "b" * 40,
            True,
            run_gh=lambda _args: next(outcomes),
            verify=lambda _plan: [],
            inspect=lambda *_: authoritative(
                [
                    {
                        "url": "https://github.com/acme/widgets/pull/7#discussion_r9",
                        "author": "bot",
                        "author_type": "Bot",
                        "active_human": False,
                        "bodies": [],
                    }
                ]
            ),
        )
    assert path.read_text() == content


def test_remote_apply_marker_skips_duplicate_reply_after_partial_failure(tmp_path):
    url = "https://github.com/acme/widgets/pull/7#discussion_r9"
    path = tmp_path / "REVIEW_test.md"
    path.write_text(report(items=[{"url": url, "reply": "Addressed."}]))
    marker_key = review_workflow.hashlib.sha256(
        f"{'b' * 40}:{url}".encode()
    ).hexdigest()[:20]
    calls = []
    verification = iter([[], [url]])

    review_workflow.apply_remote_feedback(
        path,
        "https://github.com/acme/widgets",
        "https://github.com/acme/widgets/pull/7",
        "b" * 40,
        True,
        run_gh=lambda args: calls.append(args) or 0,
        verify=lambda _plan: next(verification),
        inspect=lambda *_: authoritative(
            [
                {
                    "url": url,
                    "author": "bot",
                    "author_type": "Bot",
                    "active_human": False,
                    "bodies": [f"Addressed.\n<!-- review-cleanup:{marker_key} -->"],
                }
            ]
        ),
    )

    assert [call[:3] for call in calls] == [["gh", "api", "graphql"]]
