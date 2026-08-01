"""Unit tests for output_persist — oversized persistence + staleness eviction + safety net."""

from __future__ import annotations

import json


# ---------------------------------------------------------------------------
# persist_if_oversized
# ---------------------------------------------------------------------------


def test_under_threshold_passthrough() -> None:
    from tinycua.agent.tools.native.output_persist import persist_if_oversized

    assert persist_if_oversized("small", "tc1") == "small"


def test_over_threshold_persisted_with_authorized_opaque_handle() -> None:
    from tinycua.agent.tools.native.output_persist import (
        SessionToolResultStore,
        bind_tool_result_access,
        persist_if_oversized,
        read_tool_result,
    )

    big = "A" * 150_000
    store = SessionToolResultStore("session-1")
    try:
        out = persist_if_oversized(
            big,
            "tc-2",
            tool_name="run_shell",
            store=store,
            owner_node_id="task_executor",
        )
        handle = out.split("handle=", 1)[1].splitlines()[0]
        bind_tool_result_access(store, "session-1", "task_executor")

        first_page = read_tool_result(handle, char_limit=4_000)
        second_page = read_tool_result(handle, char_offset=4_000, char_limit=4_000)

        assert "<persisted-output>" in out
        assert "150000 chars" in out
        assert "read_tool_result" in out
        assert "tool=run_shell" in out
        assert "/tmp/" not in out
        assert ("A" * 4_000) in out  # preview head
        assert first_page["content"] == "A" * 4_000
        assert second_page["content"] == "A" * 4_000
        assert first_page["next_offset"] == 4_000
        assert second_page["next_offset"] == 8_000
    finally:
        store.cleanup()


def test_persisted_result_rejects_foreign_node() -> None:
    from tinycua.agent.tools.native.output_persist import (
        SessionToolResultStore,
        bind_tool_result_access,
        persist_if_oversized,
        read_tool_result,
    )

    store = SessionToolResultStore("session-1")
    try:
        persisted = persist_if_oversized(
            "A" * 150_000,
            "tc-2",
            store=store,
            owner_node_id="task_executor",
        )
        handle = persisted.split("handle=", 1)[1].splitlines()[0]
        bind_tool_result_access(store, "session-1", "result_reviewer")

        assert read_tool_result(handle) == {"error": "Tool result is unavailable."}
        bind_tool_result_access(store, "foreign-session", "task_executor")
        assert read_tool_result(handle) == {"error": "Tool result is unavailable."}
    finally:
        store.cleanup()


def test_write_failure_returns_original_untruncated(monkeypatch) -> None:
    """On disk write failure, never lose data — return the full content."""
    from tinycua.agent.tools.native.output_persist import (
        SessionToolResultStore,
        persist_if_oversized,
    )

    store = SessionToolResultStore("session-1")
    try:
        monkeypatch.setattr(
            store, "persist", lambda *_args: (_ for _ in ()).throw(OSError())
        )
        big = "B" * 150_000
        out = persist_if_oversized(
            big, "tc-3", store=store, owner_node_id="task_executor"
        )
        assert out == big
    finally:
        store.cleanup()


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
        _tool_result(
            "w1",
            "write_file",
            json.dumps(
                {
                    "name": "write_file",
                    "allowed": True,
                    "output": {"success": False, "error": "denied"},
                }
            ),
        ),
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

    msgs = [
        {
            "role": "tool",
            "tool_call_id": f"t{i}",
            "name": "run_shell",
            "content": "X" * 1_000,
        }
        for i in range(10)
    ]
    enforce_turn_budget(msgs, budget=200_000)
    assert all(m["content"] == "X" * 1_000 for m in msgs)


def test_safety_net_stubs_oldest_when_overrun() -> None:
    """At 250K total with 200K net, oldest non-file results stubbed until under."""
    from tinycua.agent.tools.native.output_persist import enforce_turn_budget

    msgs = [
        {
            "role": "tool",
            "tool_call_id": f"t{i}",
            "name": "run_shell",
            "content": "X" * 50_000,
        }
        for i in range(5)
    ]
    enforce_turn_budget(msgs, budget=200_000)
    total = sum(len(str(m.get("content", ""))) for m in msgs)
    assert total <= 200_000 + 200
    stubbed = [m for m in msgs if str(m.get("content", "")).startswith("[elided prior")]
    assert len(stubbed) >= 1


def test_safety_net_persists_oversized_first() -> None:
    """A single 150K result gets persisted before the net fires."""
    from tinycua.agent.tools.native import output_persist

    store = output_persist.SessionToolResultStore("session-1")
    try:
        msgs = [
            {
                "role": "tool",
                "tool_call_id": "big",
                "name": "run_shell",
                "content": "A" * 150_000,
            },
        ]
        output_persist.enforce_turn_budget(
            msgs,
            budget=200_000,
            store=store,
            owner_node_id="task_executor",
        )
        assert "<persisted-output>" in str(msgs[0]["content"])
    finally:
        store.cleanup()


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
