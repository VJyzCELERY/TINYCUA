"""Session artifact store: workspace revisions, blobs, checkpoints, and redaction.

Covers the external session artifact history contracts
(local:cumulative-review-artifact-history):
- before/after revision chains for direct file tools, shell, Python, deletion,
  partial failure, and no-op calls,
- eligible changed content stored once by SHA-256; sensitive/binary/oversized
  and external symlink targets stay hash-only,
- opaque bounded inspection without filesystem path disclosure,
- fail-closed persistence failure behavior.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import tinycua.models.artifact_history as artifact_history
from tinycua.models.artifact_history import SessionArtifactStore


def _store(workspace: Path, **kwargs) -> SessionArtifactStore:
    return SessionArtifactStore(workspace_dir=workspace, **kwargs)


def test_noop_tool_call_creates_no_revision(tmp_path: Path) -> None:
    art = _store(tmp_path)
    (tmp_path / "a.txt").write_text("x")

    art.begin_capture()
    revision = art.finish_capture(
        {"tool_name": "read_file", "call_id": "c1", "success": True}
    )

    assert revision is None
    assert art.revision_count() == 0


def test_direct_write_creates_revision_with_parent_chain(tmp_path: Path) -> None:
    art = _store(tmp_path)
    art.begin_capture()
    (tmp_path / "a.txt").write_text("one")
    art.finish_capture({"tool_name": "write_file", "call_id": "c1", "success": True})
    art.begin_capture()
    (tmp_path / "a.txt").write_text("two")
    art.finish_capture({"tool_name": "str_replace", "call_id": "c2", "success": True})

    revisions = art.revisions()
    assert len(revisions) == 2
    assert revisions[1]["parent"] == revisions[0]["revision_id"]
    assert revisions[0]["provenance"]["tool_name"] == "write_file"
    change = revisions[1]["changes"][0]
    assert change["path"] == "a.txt"
    assert change["status"] == "modified"
    assert change["before"]["hash"] != change["after"]["hash"]
    assert change["after"]["blob_id"] is not None
    assert change["after"]["size"] == 3


def test_shell_and_python_changes_are_captured(tmp_path: Path) -> None:
    art = _store(tmp_path)
    (tmp_path / "out.txt").write_text("old")
    art.begin_capture()
    (tmp_path / "out.txt").write_text("new via python")

    revision = art.finish_capture(
        {"tool_name": "run_python", "call_id": "p1", "success": True}
    )

    assert revision is not None
    assert revision["provenance"]["tool_name"] == "run_python"
    assert revision["changes"][0]["path"] == "out.txt"
    assert revision["changes"][0]["status"] == "modified"


def test_partial_failure_after_mutation_records_failed_call_revision(
    tmp_path: Path,
) -> None:
    art = _store(tmp_path)
    (tmp_path / "f.txt").write_text("before")
    art.begin_capture()
    (tmp_path / "f.txt").write_text("after")

    revision = art.finish_capture(
        {
            "tool_name": "write_file",
            "call_id": "c1",
            "success": False,
            "error": "boom",
        }
    )

    assert revision is not None
    assert revision["provenance"]["success"] is False
    change = revision["changes"][0]
    assert change["after"]["hash"] != change["before"]["hash"]


def test_deleted_file_retains_before_identity(tmp_path: Path) -> None:
    art = _store(tmp_path)
    (tmp_path / "gone.txt").write_text("doomed")
    art.begin_capture()
    (tmp_path / "gone.txt").unlink()

    revision = art.finish_capture(
        {"tool_name": "run_shell", "call_id": "s1", "success": True}
    )

    assert revision is not None
    change = revision["changes"][0]
    assert change["status"] == "deleted"
    assert change["before"]["hash"]
    assert change["before"]["size"] == 6
    assert change["after"] is None


def test_renamed_file_retains_before_and_after_identity(tmp_path: Path) -> None:
    art = _store(tmp_path)
    (tmp_path / "old.txt").write_text("content")
    art.begin_capture()
    (tmp_path / "old.txt").rename(tmp_path / "new.txt")

    revision = art.finish_capture(
        {"tool_name": "run_shell", "call_id": "s1", "success": True}
    )

    changes = {change["status"]: change for change in revision["changes"]}
    assert "deleted" in changes and "added" in changes
    assert changes["deleted"]["path"] == "old.txt"
    assert changes["deleted"]["before"]["hash"]
    assert changes["added"]["path"] == "new.txt"
    assert changes["added"]["after"]["hash"] == changes["deleted"]["before"]["hash"]


def test_eligible_content_stored_once_by_hash(tmp_path: Path) -> None:
    art = _store(tmp_path)
    art.begin_capture()
    (tmp_path / "a.txt").write_text("same content")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.txt").write_text("same content")
    art.finish_capture({"tool_name": "write_file", "call_id": "c1", "success": True})
    art.begin_capture()
    (tmp_path / "a.txt").write_text("changed content")
    art.finish_capture({"tool_name": "write_file", "call_id": "c2", "success": True})

    # Identical content across two paths in one revision is stored once.
    assert len(art.blob_hashes()) == 2
    assert len(art.blob_hashes()) == len(set(art.blob_hashes()))
    assert any(b"same content" == art.blob_content(h) for h in art.blob_hashes())


def test_sensitive_binary_and_oversized_files_are_hash_only(tmp_path: Path) -> None:
    art = _store(tmp_path)
    art.begin_capture()
    (tmp_path / ".env").write_text("SECRET=value")
    (tmp_path / "blob.bin").write_bytes(b"\x00\x01\x02\xff")
    (tmp_path / "big.txt").write_text("x" * (art.content_limit + 10))
    art.finish_capture({"tool_name": "write_file", "call_id": "c1", "success": True})

    revision = art.revisions()[-1]
    by_path = {change["path"]: change for change in revision["changes"]}
    for path in (".env", "blob.bin", "big.txt"):
        assert by_path[path]["after"]["hash"]
        assert by_path[path]["after"]["size"] > 0
        assert by_path[path]["after"]["blob_id"] is None


def test_sensitive_credential_paths_are_hash_only(tmp_path: Path) -> None:
    """Credential-like filenames never retain plaintext blobs."""
    art = _store(tmp_path)
    art.begin_capture()
    for path in ("credentials.json", "id_rsa", "api-token.txt"):
        (tmp_path / path).write_text("SECRET=value")

    art.finish_capture({"tool_name": "write_file", "call_id": "c1", "success": True})

    by_path = {change["path"]: change for change in art.revisions()[-1]["changes"]}
    for path in ("credentials.json", "id_rsa", "api-token.txt"):
        assert by_path[path]["after"]["hash"]
        assert by_path[path]["after"]["blob_id"] is None


def test_blob_capture_rejects_post_scan_symlink(tmp_path: Path, monkeypatch) -> None:
    """A path swapped for an external symlink is never stored as a blob."""
    outside = tmp_path.parent / f"{tmp_path.name}-outside.txt"
    outside.write_text("outside secret")
    art = _store(tmp_path)
    original = art._store_eligible_blobs

    def swap_then_store(changes: list[dict]) -> None:
        path = tmp_path / "report.txt"
        path.unlink()
        path.symlink_to(outside)
        original(changes)

    monkeypatch.setattr(art, "_store_eligible_blobs", swap_then_store)
    art.begin_capture()
    (tmp_path / "report.txt").write_text("workspace report")

    revision = art.finish_capture(
        {"tool_name": "write_file", "call_id": "c1", "success": True}
    )

    assert revision is not None
    assert revision["changes"][0]["after"]["blob_id"] is None
    assert all(
        art.blob_content(blob_id) != b"outside secret" for blob_id in art.blob_hashes()
    )


def test_external_symlink_is_not_followed(tmp_path: Path) -> None:
    outside = tmp_path.parent / f"{tmp_path.name}-outside"
    outside.mkdir(exist_ok=True)
    (outside / "secret.txt").write_text("outside secret")

    art = _store(tmp_path)
    art.begin_capture()
    link = tmp_path / "link.txt"
    link.symlink_to(outside / "secret.txt")
    art.finish_capture({"tool_name": "run_shell", "call_id": "s1", "success": True})
    revision = art.revisions()[-1]
    change = next(c for c in revision["changes"] if c["path"] == "link.txt")
    assert change["status"] == "added"
    assert change["after"]["blob_id"] is None
    # The outside file's content is never read into a blob.
    assert all(b"outside secret" != art.blob_content(h) for h in art.blob_hashes())


def test_session_dir_never_leaks_into_revision_projection(tmp_path: Path) -> None:
    session_store = tmp_path / "session-store"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    art = _store(workspace, session_dir=session_store)
    art.begin_capture()
    (workspace / "a.txt").write_text("v1")
    art.finish_capture({"tool_name": "write_file", "call_id": "c1", "success": True})

    projection = art.render_checkpoint_diff()

    assert str(session_store.resolve()) not in projection
    assert str(workspace.resolve()) not in projection
    assert "a.txt" in projection


def test_inspect_revision_pages_bounded_detail_by_opaque_id(tmp_path: Path) -> None:
    art = _store(tmp_path)
    art.begin_capture()
    (tmp_path / "a.txt").write_text("A" * 500)
    art.finish_capture({"tool_name": "write_file", "call_id": "c1", "success": True})
    revision_id = art.latest_revision_id()

    summary = art.inspect_revision(revision_id, offset=0, limit=10)
    page = art.inspect_revision(revision_id, path="a.txt", offset=100, limit=50)

    assert summary["revision_id"] == revision_id
    assert summary["changes"][0]["path"] == "a.txt"
    assert page["content"] == "A" * 50
    assert page["has_more"] is True
    assert page["next_offset"] == 150


def test_inspect_rejects_unknown_id_and_invalid_bounds(tmp_path: Path) -> None:
    art = _store(tmp_path)
    art.begin_capture()
    (tmp_path / "a.txt").write_text("x")
    art.finish_capture({"tool_name": "write_file", "call_id": "c1", "success": True})

    with pytest.raises(ValueError, match="revision"):
        art.inspect_revision("rev-unknown", offset=0, limit=10)
    with pytest.raises(ValueError, match="offset"):
        art.inspect_revision(art.latest_revision_id(), offset=-1, limit=10)
    with pytest.raises(ValueError, match="limit"):
        art.inspect_revision(art.latest_revision_id(), offset=0, limit=0)


def test_unavailable_workspace_blocks_capture_before_mutation(tmp_path: Path) -> None:
    not_a_dir = tmp_path / "file"
    not_a_dir.write_text("x")
    art = _store(not_a_dir)

    error = art.begin_capture()

    assert error is not None
    assert art.is_incomplete()


def test_unreadable_path_fails_closed(tmp_path: Path, monkeypatch) -> None:
    """A manifest entry that cannot be read blocks the mutation boundary."""
    blocked = tmp_path / "blocked.txt"
    blocked.write_text("cannot read")
    art = _store(tmp_path)
    original_hash = artifact_history._hash_file

    def fail_hash(path: Path) -> tuple[str, int]:
        if path == blocked:
            raise OSError("denied")
        return original_hash(path)

    monkeypatch.setattr(artifact_history, "_hash_file", fail_hash)

    assert art.begin_capture() is not None
    assert art.is_incomplete()


def test_failed_capture_does_not_expose_internal_path_on_retry(
    tmp_path: Path, monkeypatch
) -> None:
    art = _store(tmp_path)
    internal_path = tmp_path / "session" / "revisions.jsonl"

    def fail_scan() -> dict[str, dict[str, object]]:
        raise OSError(f"cannot access {internal_path}")

    monkeypatch.setattr(art, "_scan_workspace", fail_scan)

    assert art.begin_capture() == "artifact capture unavailable"
    error = art.begin_capture()

    assert error == "artifact capture unavailable"
    assert str(internal_path) not in error


def test_directory_symlink_is_recorded_without_traversal(tmp_path: Path) -> None:
    """Directory symlinks are manifest entries and never traverse their targets."""
    outside = tmp_path.parent / f"{tmp_path.name}-outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("outside secret")
    art = _store(tmp_path)
    art.begin_capture()
    (tmp_path / "linked-dir").symlink_to(outside, target_is_directory=True)

    revision = art.finish_capture(
        {"tool_name": "run_shell", "call_id": "c1", "success": True}
    )

    assert revision is not None
    change = revision["changes"][0]
    assert change["path"] == "linked-dir"
    assert change["after"]["kind"] == "symlink"
    assert change["after"]["blob_id"] is None


def test_checkpoint_without_revision_then_write(tmp_path: Path) -> None:
    """The empty checkpoint is the baseline before every revision."""
    art = _store(tmp_path)
    art.advance_checkpoint("task-1", "review-1")
    art.begin_capture()
    (tmp_path / "later.txt").write_text("later")
    art.finish_capture({"tool_name": "write_file", "call_id": "c1", "success": True})

    diff = art.changes_since_checkpoint()

    assert diff["revision_ids"] == [art.latest_revision_id()]
    assert diff["changes"][0]["path"] == "later.txt"


def test_reviewed_result_revision_persists_after_replacement(tmp_path: Path) -> None:
    """A persisted report stays inspectable after its active result changes."""
    session_dir = tmp_path.parent / f"{tmp_path.name}-session"
    art = _store(tmp_path, session_dir=session_dir)

    revision = art.record_result_revision("task-1", "reviewed report")
    replacement = SessionArtifactStore(workspace_dir=tmp_path, session_dir=session_dir)

    page = replacement.inspect_result_revision(revision["revision_id"], limit=8)

    assert page["content"] == "reviewed"
    assert page["has_more"] is True
    assert page["next_offset"] == 8


def test_result_revision_rejects_path_traversal(tmp_path: Path) -> None:
    session_dir = tmp_path.parent / f"{tmp_path.name}-session"
    session_dir.mkdir()
    (session_dir / "results").mkdir()
    (session_dir / "checkpoint.json").write_text("internal checkpoint")
    art = _store(tmp_path, session_dir=session_dir)

    with pytest.raises(ValueError, match="Unknown result revision"):
        art.inspect_result_revision("result-../checkpoint.json")


def test_tmp_workspace_changes_are_captured(tmp_path: Path) -> None:
    art = _store(tmp_path)
    art.begin_capture()
    (tmp_path / "tmp").mkdir()
    (tmp_path / "tmp" / "report.md").write_text("audited")

    revision = art.finish_capture(
        {"tool_name": "write_file", "call_id": "c1", "success": True}
    )

    assert revision is not None
    assert revision["changes"][0]["path"] == "tmp/report.md"


def test_cumulative_projection_is_inspectable(tmp_path: Path) -> None:
    """Each projected path retains the opaque revision that owns its content."""
    art = _store(tmp_path)
    art.begin_capture()
    (tmp_path / "first.txt").write_text("first")
    first = art.finish_capture(
        {"tool_name": "write_file", "call_id": "c1", "success": True}
    )
    art.begin_capture()
    (tmp_path / "second.txt").write_text("second")
    second = art.finish_capture(
        {"tool_name": "write_file", "call_id": "c2", "success": True}
    )

    changes = {
        change["path"]: change for change in art.changes_since_checkpoint()["changes"]
    }

    assert changes["first.txt"]["revision_id"] == first["revision_id"]
    assert changes["second.txt"]["revision_id"] == second["revision_id"]
    assert first["revision_id"] in art.render_checkpoint_diff()


def test_revision_summary_is_paginated(tmp_path: Path) -> None:
    """Revision summaries honor stable page bounds before exposing changes."""
    art = _store(tmp_path)
    art.begin_capture()
    (tmp_path / "a.txt").write_text("a")
    (tmp_path / "b.txt").write_text("b")
    art.finish_capture({"tool_name": "write_file", "call_id": "c1", "success": True})

    page = art.inspect_revision(art.latest_revision_id(), offset=0, limit=1)

    assert len(page["changes"]) == 1
    assert page["has_more"] is True
    assert page["next_offset"] == 1


def test_post_write_persistence_failure_marks_incomplete(
    tmp_path: Path, monkeypatch
) -> None:
    art = _store(tmp_path)

    def failing_persist(self, revision: dict) -> None:  # noqa: ANN001
        self._mark_incomplete(f"simulated write failure for {revision['revision_id']}")

    monkeypatch.setattr(SessionArtifactStore, "_persist_revision", failing_persist)
    art.begin_capture()
    (tmp_path / "a.txt").write_text("one")

    revision = art.finish_capture(
        {"tool_name": "write_file", "call_id": "c1", "success": True}
    )

    assert revision is not None
    assert art.is_incomplete()
    assert art.incomplete_reason() is not None


def test_session_dir_inside_workspace_is_rejected(tmp_path: Path) -> None:
    """Session storage must resolve outside the judged workspace."""
    with pytest.raises(ValueError, match="outside the workspace"):
        SessionArtifactStore(
            session_dir=tmp_path / "inside",
            workspace_dir=tmp_path,
        )
