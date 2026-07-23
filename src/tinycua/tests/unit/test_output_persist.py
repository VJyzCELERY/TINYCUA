"""Unit tests for output_persist — oversized persistence + staleness eviction + safety net."""

from __future__ import annotations

import json



# ---------------------------------------------------------------------------
# persist_if_oversized
# ---------------------------------------------------------------------------

def test_under_threshold_passthrough() -> None:
    from tinycua.agent.tools.native.output_persist import persist_if_oversized

    assert persist_if_oversized("small", "tc1") == "small"


def test_over_threshold_persisted_with_preview(tmp_path, monkeypatch) -> None:
    from tinycua.agent.tools.native import output_persist

    monkeypatch.setattr(output_persist, "_RESULTS_DIR", tmp_path / "tool-results")
    big = "A" * 150_000
    out = output_persist.persist_if_oversized(big, "tc-2", tool_name="run_shell")

    assert "<persisted-output>" in out
    assert "150000 chars" in out
    assert "read_file" in out
    assert "tool=run_shell" in out
    assert ("A" * 4_000) in out  # preview head
    written = (tmp_path / "tool-results" / "tc-2.txt").read_text()
    assert written == big


def test_write_failure_returns_original_untruncated(tmp_path, monkeypatch) -> None:
    """On disk write failure, never lose data — return the full content."""
    from tinycua.agent.tools.native import output_persist

    monkeypatch.setattr(
        output_persist,
        "_RESULTS_DIR",
        tmp_path / "im_a_file" / "cant_make_parent",
    )
    (tmp_path / "im_a_file").write_text("blocker")

    big = "B" * 150_000
    out = output_persist.persist_if_oversized(big, "tc-3")
    assert out == big


# ---------------------------------------------------------------------------
# evict_superseded_file_reads — the PRIMARY context bound (staleness, not size)
# ---------------------------------------------------------------------------

def _assistant_with_tool_calls(*calls: tuple[str, str, dict]) -> dict:
    """Build an assistant message with tool_calls. Each call: (id, name, args_dict)."""
    return {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {"id": cid, "function": {"name": name, "arguments": json.dumps(args)}}
            for cid, name, args in calls
        ],
    }


def _tool_result(tc_id: str, name: str, content: str) -> dict:
    return {"role": "tool", "tool_call_id": tc_id, "name": name, "content": content}


def test_superseded_read_file_stubs_older_same_path() -> None:
    """Re-reading the same file stubs the older reads; latest stays verbatim."""
    from tinycua.agent.tools.native.output_persist import evict_superseded_file_reads

    msgs = [
        _assistant_with_tool_calls(
            ("r1", "read_file", {"path": "api.py"}),
            ("r2", "read_file", {"path": "api.py"}),
            ("r3", "read_file", {"path": "api.py"}),
        ),
        _tool_result("r1", "read_file", "X" * 5_000),
        _tool_result("r2", "read_file", "Y" * 5_000),
        _tool_result("r3", "read_file", "Z" * 5_000),
    ]
    evict_superseded_file_reads(msgs)
    # r1, r2 stubbed (superseded by r3)
    assert str(msgs[1]["content"]).startswith("[elided prior read_file")
    assert str(msgs[2]["content"]).startswith("[elided prior read_file")
    assert "superseded" in str(msgs[1]["content"])
    # r3 (latest) stays verbatim
    assert msgs[3]["content"] == "Z" * 5_000


def test_distinct_file_reads_stay_verbatim() -> None:
    """Reading 3 different files — none stubbed (no supersession)."""
    from tinycua.agent.tools.native.output_persist import evict_superseded_file_reads

    msgs = [
        _assistant_with_tool_calls(
            ("a", "read_file", {"path": "a.py"}),
            ("b", "read_file", {"path": "b.py"}),
            ("c", "read_file", {"path": "c.py"}),
        ),
        _tool_result("a", "read_file", "A" * 5_000),
        _tool_result("b", "read_file", "B" * 5_000),
        _tool_result("c", "read_file", "C" * 5_000),
    ]
    evict_superseded_file_reads(msgs)
    assert msgs[1]["content"] == "A" * 5_000
    assert msgs[2]["content"] == "B" * 5_000
    assert msgs[3]["content"] == "C" * 5_000


def test_write_then_read_same_path_stubs_the_write() -> None:
    """write_file then read_file of same path — the write result is superseded."""
    from tinycua.agent.tools.native.output_persist import evict_superseded_file_reads

    msgs = [
        _assistant_with_tool_calls(
            ("w1", "write_file", {"path": "api.py"}),
            ("r1", "read_file", {"path": "api.py"}),
        ),
        _tool_result("w1", "write_file", "wrote 5000 chars"),
        _tool_result("r1", "read_file", "X" * 5_000),
    ]
    evict_superseded_file_reads(msgs)
    assert str(msgs[1]["content"]).startswith("[elided prior write_file")
    assert msgs[2]["content"] == "X" * 5_000


def test_failed_mutation_keeps_prior_successful_observation() -> None:
    """A failed write cannot supersede an observation because the file is unchanged."""
    from tinycua.agent.tools.native.output_persist import evict_superseded_file_reads

    msgs = [
        _assistant_with_tool_calls(
            ("r1", "read_file", {"path": "api.py"}),
            ("w1", "write_file", {"path": "api.py"}),
        ),
        _tool_result("r1", "read_file", "observed contents"),
        _tool_result("w1", "write_file", json.dumps({"success": False, "error": "denied"})),
    ]

    evict_superseded_file_reads(msgs)

    assert msgs[1]["content"] == "observed contents"


def test_non_file_tools_never_stubbed_by_staleness() -> None:
    """run_shell/task_inspect results are not file reads — left alone by staleness pass."""
    from tinycua.agent.tools.native.output_persist import evict_superseded_file_reads

    msgs = [
        _assistant_with_tool_calls(
            ("s1", "run_shell", {"command": "ls"}),
            ("s2", "run_shell", {"command": "ls"}),
        ),
        _tool_result("s1", "run_shell", "file1\nfile2"),
        _tool_result("s2", "run_shell", "file1\nfile2"),
    ]
    evict_superseded_file_reads(msgs)
    # Neither stubbed — run_shell isn't a file-path tool.
    assert msgs[1]["content"] == "file1\nfile2"
    assert msgs[2]["content"] == "file1\nfile2"


def test_staleness_no_op_without_assistant_tool_calls() -> None:
    """If only tool-result messages are passed (no assistant tool_calls), bail safely."""
    from tinycua.agent.tools.native.output_persist import evict_superseded_file_reads

    msgs = [
        _tool_result("r1", "read_file", "X" * 5_000),
        _tool_result("r2", "read_file", "Y" * 5_000),
    ]
    evict_superseded_file_reads(msgs)
    assert msgs[0]["content"] == "X" * 5_000
    assert msgs[1]["content"] == "Y" * 5_000


def test_already_stubbed_not_re_stubbed() -> None:
    """A message already stubbed isn't processed again."""
    from tinycua.agent.tools.native.output_persist import evict_superseded_file_reads

    stub = "[elided prior read_file result (1000 chars, superseded); re-call read_file if needed]"
    msgs = [
        _assistant_with_tool_calls(
            ("r1", "read_file", {"path": "api.py"}),
            ("r2", "read_file", {"path": "api.py"}),
        ),
        _tool_result("r1", "read_file", stub),
        _tool_result("r2", "read_file", "X" * 5_000),
    ]
    evict_superseded_file_reads(msgs)
    assert msgs[1]["content"] == stub  # unchanged


# ---------------------------------------------------------------------------
# enforce_turn_budget — high safety net only (NOT a tight budget)
# ---------------------------------------------------------------------------

def test_safety_net_no_op_under_threshold() -> None:
    """10 tool results of 1K each (10K total) — well under 200K net → untouched."""
    from tinycua.agent.tools.native.output_persist import enforce_turn_budget

    msgs = [{"role": "tool", "tool_call_id": f"t{i}", "name": "run_shell", "content": "X" * 1_000} for i in range(10)]
    enforce_turn_budget(msgs, budget=200_000)
    assert all(m["content"] == "X" * 1_000 for m in msgs)


def test_safety_net_stubs_oldest_when_overrun() -> None:
    """At 250K total with 200K net, oldest non-file results stubbed until under."""
    from tinycua.agent.tools.native.output_persist import enforce_turn_budget

    msgs = [{"role": "tool", "tool_call_id": f"t{i}", "name": "run_shell", "content": "X" * 50_000} for i in range(5)]
    enforce_turn_budget(msgs, budget=200_000)
    total = sum(len(str(m.get("content", ""))) for m in msgs)
    assert total <= 200_000 + 200
    stubbed = [m for m in msgs if str(m.get("content", "")).startswith("[elided prior")]
    assert len(stubbed) >= 1


def test_safety_net_persists_oversized_first() -> None:
    """A single 150K result gets persisted before the net fires."""
    from tinycua.agent.tools.native import output_persist
    import os

    # Use a temp dir for the persist target.
    results_dir = os.path.join(os.path.dirname(__file__), "_test_results")
    output_persist._RESULTS_DIR = type(output_persist._RESULTS_DIR)(results_dir)
    try:
        msgs = [
            {"role": "tool", "tool_call_id": "big", "name": "run_shell", "content": "A" * 150_000},
        ]
        output_persist.enforce_turn_budget(msgs, budget=200_000)
        assert "<persisted-output>" in str(msgs[0]["content"])
    finally:
        import shutil
        shutil.rmtree(results_dir, ignore_errors=True)


if __name__ == "__main__":
    import sys

    passed = failed = 0
    for name, obj in sorted(globals().items()):
        if name.startswith("test_") and callable(obj):
            try:
                obj()
                passed += 1
            except Exception as exc:
                failed += 1
                print(f"FAIL {name}: {exc}", file=sys.stderr)
    print(f"output_persist tests: {passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
