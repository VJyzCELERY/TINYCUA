"""Unit tests for the TinyCUA stdout trace parser.

Covers event extraction, retry/defect-signal detection, and per-task story
assembly directly from the documented stdout grammar. Tests stay free of any
existing evaluation-results fixtures so they remain hermetic and fast.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import trace_parser
from trace_parser import (
    TraceParseError,
    classify_defect_signals,
    parse_stdout,
    parse_tool_result_fields,
    summarize,
)


def _write_run(run_logs: Path, stdout: str, duration: float = 100.0) -> Path:
    """Materialize a fake run_logs dir matching on-disk layout."""
    run_logs.mkdir(parents=True, exist_ok=True)
    (run_logs / "stdout.txt").write_text(stdout)
    (run_logs / "metadata.json").write_text(
        '{"experiment_num": 4, "agent": "tinycua", '
        '"duration_seconds": ' + str(duration) + ', "status": "passed"}'
    )
    return run_logs


def test_parse_stdout_extracts_every_event_kind(tmp_path: Path) -> None:
    """One complete loop (digest -> work -> exec -> review -> rework) parses cleanly."""
    stdout = (
        "=== LIVE STREAM ===\n"
        "[query_analyst] start\n"
        "Classifying the user query.\n"
        "[query_analyst] tool_call: select_query_route\n"
        "[query_analyst] usage: input_tokens=855 output_tokens=287 total_tokens=1142\n"
        "[query_analyst] completed: empty\n"
        "\n"
        "[tool-result] node=QueryAnalyst tool=select_query_route completed\n"
        "\n"
        "[digester] start\n"
        "[digester] tool_call: enhanced_context_retrieval\n"
        "[digester] usage: input_tokens=2092 output_tokens=137 total_tokens=2229\n"
        "[digester] completed: empty\n"
        "\n"
        "[tool-result] node=InformationDigester tool=enhanced_context_retrieval completed\n"
        "\n"
        "[task_executor] start\n"
        "Writing the file now.\n"
        "[task_executor] tool_call: write_file\n"
        "[task_executor] usage: input_tokens=100 output_tokens=20 total_tokens=120\n"
        "\n"
        "[tool-result] node=TaskExecutor tool=write_file success=True "
        "path=/workspace/experiment-4/src/main.py\n"
        "[task_executor] tool_call: task_result_update\n"
        "[task_executor] usage: input_tokens=110 output_tokens=10 total_tokens=120\n"
        "\n"
        "[tool-result] node=TaskExecutor tool=task_result_update success=True "
        "task_id=abc status=in_progress\n"
        "[task_executor] tool_call: terminate\n"
        "[task_executor] usage: input_tokens=120 output_tokens=5 total_tokens=125\n"
        "[task_executor] completed: empty\n"
        "\n"
        "[tool-result] node=TaskExecutor tool=terminate completed\n"
    )
    events = parse_stdout(stdout)

    # Sanity: structural events present in expected order and counts.
    kinds = [e["kind"] for e in events]
    assert kinds.count("session_start") == 3
    assert kinds.count("session_end") == 3
    assert kinds.count("tool_call") == 5
    assert kinds.count("usage") == 5
    assert kinds.count("tool_result") == 5
    assert kinds.count("text") >= 2  # query analyst + executor reasoning blobs

    # Token accounting per LLM call is preserved.
    assert (
        sum(e["total_tokens"] for e in events if e["kind"] == "usage")
        == 1142 + 2229 + 120 + 120 + 125
    )

    # Tool-result fields are parsed, even when optional fields appear together.
    tr_write = next(
        e for e in events if e["kind"] == "tool_result" and e["tool"] == "write_file"
    )
    assert tr_write["success"] is True
    assert tr_write["path"] == "/workspace/experiment-4/src/main.py"

    tr_task = next(
        e
        for e in events
        if e["kind"] == "tool_result" and e["tool"] == "task_result_update"
    )
    assert tr_task["task_id"] == "abc"
    assert tr_task["status"] == "in_progress"


def test_parse_stdout_captures_reviewer_verdict_and_cited_cause(tmp_path: Path) -> None:
    """Reviewer decision and the assistant reasoning that preceded it are linked."""
    stdout = (
        "[result_reviewer] start\n"
        "The init_db.py script has a syntax error - Field is imported from "
        "Field import but not imported. I need to report needs_revision.\n"
        "[result_reviewer] tool_call: task_review_decision\n"
        "[result_reviewer] usage: input_tokens=8484 output_tokens=143 total_tokens=8627\n"
        "\n"
        "[tool-result] node=ResultReviewer tool=task_review_decision success=True "
        "task_id=64c7 status=in_progress decision=needs_revision\n"
        "[result_reviewer] tool_call: terminate\n"
        "[result_reviewer] usage: input_tokens=11121 output_tokens=69 total_tokens=11190\n"
        "[result_reviewer] completed: empty\n"
        "\n"
        "[tool-result] node=ResultReviewer tool=terminate completed\n"
    )
    events = parse_stdout(stdout)
    decision = next(
        e
        for e in events
        if e["kind"] == "tool_result" and e["tool"] == "task_review_decision"
    )
    assert decision["decision"] == "needs_revision"
    assert decision["task_id"] == "64c7"

    # The text blob immediately preceding the decision tool_call is captured.
    text_events = [e for e in events if e["kind"] == "text"]
    assert text_events, "reviewer reasoning text should be captured"
    assert "Field" in text_events[-1]["text"]
    assert "needs_revision" in text_events[-1]["text"]


def test_summarize_counts_verdicts_and_rework_per_task() -> None:
    """Verdict split and per-task rework counts come straight from tool-result events."""
    events = parse_stdout(
        "[task_executor] start\n"
        "[task_executor] tool_call: task_result_update\n"
        "[task_executor] usage: input_tokens=1 output_tokens=1 total_tokens=2\n"
        "\n"
        "[tool-result] node=TaskExecutor tool=task_result_update success=True task_id=t1 status=in_progress\n"
        "[task_executor] tool_call: terminate\n"
        "[task_executor] completed: empty\n"
        "\n"
        "[tool-result] node=TaskExecutor tool=terminate completed\n"
        "[result_reviewer] start\n"
        "[result_reviewer] tool_call: task_review_decision\n"
        "[result_reviewer] usage: input_tokens=1 output_tokens=1 total_tokens=2\n"
        "\n"
        "[tool-result] node=ResultReviewer tool=task_review_decision success=True task_id=t1 decision=approved\n"
        "[result_reviewer] tool_call: terminate\n"
        "[result_reviewer] completed: empty\n"
        "\n"
        "[tool-result] node=ResultReviewer tool=terminate completed\n"
        # rework 1
        "[task_executor] start\n"
        "[task_executor] tool_call: task_result_update\n"
        "[task_executor] usage: input_tokens=1 output_tokens=1 total_tokens=2\n"
        "\n"
        "[tool-result] node=TaskExecutor tool=task_result_update success=True task_id=t2 status=in_progress\n"
        "[task_executor] tool_call: terminate\n"
        "[task_executor] completed: empty\n"
        "\n"
        "[tool-result] node=TaskExecutor tool=terminate completed\n"
        "[result_reviewer] start\n"
        "[result_reviewer] tool_call: task_review_decision\n"
        "[result_reviewer] usage: input_tokens=1 output_tokens=1 total_tokens=2\n"
        "\n"
        "[tool-result] node=ResultReviewer tool=task_review_decision success=True task_id=t2 decision=needs_revision\n"
        "[result_reviewer] tool_call: terminate\n"
        "[result_reviewer] completed: empty\n"
        "\n"
        "[tool-result] node=ResultReviewer tool=terminate completed\n"
        # rework 2 on same task t2
        "[task_executor] start\n"
        "[task_executor] tool_call: task_result_update\n"
        "[task_executor] usage: input_tokens=1 output_tokens=1 total_tokens=2\n"
        "\n"
        "[tool-result] node=TaskExecutor tool=task_result_update success=True task_id=t2 status=in_progress\n"
        "[task_executor] tool_call: terminate\n"
        "[task_executor] completed: empty\n"
        "\n"
        "[tool-result] node=TaskExecutor tool=terminate completed\n"
        "[result_reviewer] start\n"
        "[result_reviewer] tool_call: task_review_decision\n"
        "[result_reviewer] usage: input_tokens=1 output_tokens=1 total_tokens=2\n"
        "\n"
        "[tool-result] node=ResultReviewer tool=task_review_decision success=True task_id=t2 decision=needs_revision\n"
        "[result_reviewer] tool_call: terminate\n"
        "[result_reviewer] completed: empty\n"
        "\n"
        "[tool-result] node=ResultReviewer tool=terminate completed\n"
    )
    summary = summarize(events)
    assert summary["review_verdicts"]["approved"] == 1
    assert summary["review_verdicts"]["needs_revision"] == 2
    # rework = number of needs_revision verdicts received by that task
    assert summary["task_rework_counts"]["t2"] == 2
    assert summary["task_rework_counts"].get("t1", 0) == 0


def test_classify_defect_signals_flags_multi_decision_reviewer_session() -> None:
    """Signal #1: a reviewer session emitting two decisions is a defect."""
    events = parse_stdout(
        "[result_reviewer] start\n"
        "Reviewer second-guesses itself.\n"
        "[result_reviewer] tool_call: task_review_decision\n"
        "[result_reviewer] usage: input_tokens=1 output_tokens=1 total_tokens=2\n"
        "\n"
        "[tool-result] node=ResultReviewer tool=task_review_decision success=True task_id=t1 decision=needs_revision\n"
        "[result_reviewer] tool_call: task_review_decision\n"
        "[result_reviewer] usage: input_tokens=1 output_tokens=1 total_tokens=2\n"
        "\n"
        "[tool-result] node=ResultReviewer tool=task_review_decision success=True task_id=t1 decision=approved\n"
        "[result_reviewer] tool_call: terminate\n"
        "[result_reviewer] completed: empty\n"
        "\n"
        "[tool-result] node=ResultReviewer tool=terminate completed\n"
    )
    summary = summarize(events)
    defects = classify_defect_signals(events, summary)
    # Both usage events in the flagged session should be defect.
    defect_seqs = {d["seq"] for d in defects["defect_usage_events"]}
    # Two review-decision usage events land on the lines containing their `usage:` tags.
    assert len(defect_seqs) == 2


def test_classify_defect_signals_flags_non_zero_shell_exit() -> None:
    """Signal #3: a shell command returning non-zero exit is a defect on its caller's session."""
    events = parse_stdout(
        "[task_executor] start\n"
        "[task_executor] tool_call: run_shell\n"
        "[task_executor] usage: input_tokens=1 output_tokens=1 total_tokens=2\n"
        "\n"
        "[tool-result] node=TaskExecutor tool=run_shell exit_code=1 timed_out=False\n"
        "[task_executor] tool_call: terminate\n"
        "[task_executor] usage: input_tokens=1 output_tokens=1 total_tokens=2\n"
        "[task_executor] completed: empty\n"
        "\n"
        "[tool-result] node=TaskExecutor tool=terminate completed\n"
    )
    summary = summarize(events)
    defects = classify_defect_signals(events, summary)
    assert defects["defect_usage_events"], (
        "non-zero shell exit should flag the executor session"
    )
    assert defects["signal_counts"]["non_zero_shell"] == 1


def test_classify_defect_signals_flags_unbounded_list_files() -> None:
    """Signal #4: list_files returning many items is a defect."""
    events = parse_stdout(
        "[task_executor] start\n"
        "[task_executor] tool_call: list_files\n"
        "[task_executor] usage: input_tokens=1 output_tokens=1 total_tokens=2\n"
        "\n"
        "[tool-result] node=TaskExecutor tool=list_files items=2356\n"
        "[task_executor] tool_call: terminate\n"
        "[task_executor] completed: empty\n"
        "\n"
        "[tool-result] node=TaskExecutor tool=terminate completed\n"
    )
    summary = summarize(events)
    defects = classify_defect_signals(events, summary)
    assert defects["signal_counts"]["oversize_listing"] == 1
    assert defects["defect_usage_events"], (
        "oversize listing should flag its session tokens"
    )


def test_classify_defect_signals_flags_session_without_terminate() -> None:
    """Signal #5: a session that completed without calling terminate is a protocol defect."""
    events = parse_stdout(
        "[task_executor] start\n"
        "[task_executor] tool_call: task_result_update\n"
        "[task_executor] usage: input_tokens=1 output_tokens=1 total_tokens=2\n"
        "\n"
        "[tool-result] node=TaskExecutor tool=task_result_update success=True task_id=t1 status=in_progress\n"
        "[task_executor] completed: empty\n"
    )
    summary = summarize(events)
    defects = classify_defect_signals(events, summary)
    assert defects["signal_counts"]["session_without_terminate"] == 1


def test_classify_defect_signals_flags_triple_needs_revision_on_same_task() -> None:
    """Signal #2: a task receiving three needs_revision verdicts flags all its sessions."""
    sessions = []
    for _ in range(3):
        sessions.append(
            "[task_executor] start\n"
            "[task_executor] tool_call: task_result_update\n"
            "[task_executor] usage: input_tokens=1 output_tokens=1 total_tokens=2\n"
            "\n"
            "[tool-result] node=TaskExecutor tool=task_result_update success=True task_id=t1 status=in_progress\n"
            "[task_executor] tool_call: terminate\n"
            "[task_executor] completed: empty\n"
            "\n"
            "[tool-result] node=TaskExecutor tool=terminate completed\n"
            "[result_reviewer] start\n"
            "[result_reviewer] tool_call: task_review_decision\n"
            "[result_reviewer] usage: input_tokens=1 output_tokens=1 total_tokens=2\n"
            "\n"
            "[tool-result] node=ResultReviewer tool=task_review_decision success=True task_id=t1 decision=needs_revision\n"
            "[result_reviewer] tool_call: terminate\n"
            "[result_reviewer] completed: empty\n"
            "\n"
            "[tool-result] node=ResultReviewer tool=terminate completed\n"
        )
    events = parse_stdout("".join(sessions))
    summary = summarize(events)
    defects = classify_defect_signals(events, summary)
    assert defects["signal_counts"]["triple_needs_revision_task"] == 1
    assert len(defects["defect_usage_events"]) == 6  # 3 executor + 3 reviewer usages


def test_classify_signals_on_real_sqlite_cycle_fixture() -> None:
    """A faithful extract of exp-4 stdout lines around the SQLite init_db cycle.

    Lines 2144-2167 reproduced exactly: reviewer flips from needs_revision to
    approved on the same broken code, then admits the approval was wrong.
    """
    sqlite_fixture = (
        "[result_reviewer] start\n"
        "The active task is Fix SQLite database initialization. The reviewer must "
        "verify the create_engine call works.\n"
        "[result_reviewer] tool_call: task_review_decision\n"
        "[result_reviewer] usage: input_tokens=1 output_tokens=1 total_tokens=2\n"
        "\n"
        "[tool-result] node=ResultReviewer tool=task_review_decision success=True "
        "task_id=2a5c1f0acd194af38807b352010068d0 status=in_progress decision=needs_revision\n"
        "Reviewer reads the still-broken file.\n"
        "[result_reviewer] tool_call: read_file\n"
        "[result_reviewer] usage: input_tokens=1 output_tokens=1 total_tokens=2\n"
        "\n"
        "[tool-result] node=ResultReviewer tool=read_file completed\n"
        "Reviewer approves without a fix.\n"
        "[result_reviewer] tool_call: task_review_decision\n"
        "[result_reviewer] usage: input_tokens=1 output_tokens=1 total_tokens=2\n"
        "\n"
        "[tool-result] node=ResultReviewer tool=task_review_decision success=True "
        "task_id=2a5c1f0acd194af38807b352010068d0 status=completed decision=approved\n"
        "I should NOT have approved this. The validation evidence shows the code is "
        "broken (TypeError when running).\n"
        "[result_reviewer] tool_call: terminate\n"
        "[result_reviewer] usage: input_tokens=1 output_tokens=1 total_tokens=2\n"
        "[result_reviewer] completed: empty\n"
        "\n"
        "[tool-result] node=ResultReviewer tool=terminate completed\n"
    )
    events = parse_stdout(sqlite_fixture)
    summary = summarize(events)
    defects = classify_defect_signals(events, summary)

    # Two decisions, one of them a false approval: signal #1 fires.
    assert defects["signal_counts"]["multi_decision_reviewer_session"] == 1
    # And the verdict split captures both needs_revision and approved.
    assert summary["review_verdicts"]["needs_revision"] == 1
    assert summary["review_verdicts"]["approved"] == 1


def test_parse_stdout_raises_on_malformed_tool_result_line() -> None:
    """A tool-result line missing required fields fails loudly, never silently drops."""
    # node= is mandatory on tool-result lines; removing it is unrecoverable.
    bad = "[tool-result] tool=run_shell exit_code=0 timed_out=False\n"
    with pytest.raises(TraceParseError):
        parse_stdout(bad)


def test_parse_tool_result_fields_handles_every_field_kind() -> None:
    """All observed tool-result field shapes parse to the right typed values."""
    fields = parse_tool_result_fields(
        "node=TaskExecutor tool=task_review_decision success=True "
        "task_id=abc status=completed decision=approved path=/x/y.py "
        "exit_code=0 timed_out=False items=42 completed"
    )
    assert fields["node"] == "TaskExecutor"
    assert fields["tool"] == "task_review_decision"
    assert fields["success"] is True
    assert fields["task_id"] == "abc"
    assert fields["status"] == "completed"
    assert fields["decision"] == "approved"
    assert fields["path"] == "/x/y.py"
    assert fields["exit_code"] == 0
    assert fields["timed_out"] is False
    assert fields["items"] == 42


def test_main_writes_per_run_outputs_from_real_run_logs(tmp_path: Path) -> None:
    """End-to-end: parse_run reads run_logs/stdout.txt and writes the three artifacts."""
    stdout = (
        "[query_analyst] start\n"
        "[query_analyst] tool_call: select_query_route\n"
        "[query_analyst] usage: input_tokens=855 output_tokens=287 total_tokens=1142\n"
        "[query_analyst] completed: empty\n"
        "\n"
        "[tool-result] node=QueryAnalyst tool=select_query_route completed\n"
    )
    run_logs = _write_run(tmp_path / "tinycua" / "experiment-4" / "run_logs", stdout)
    code = trace_parser.main(["--run-logs", str(run_logs)])
    assert code == 0
    events_path = run_logs / "events.jsonl"
    summary_path = run_logs / "run_summary.json"
    assert events_path.exists()
    assert summary_path.exists()
    summary = __import__("json").loads(summary_path.read_text())
    assert summary["llm_calls"] == 1
    assert summary["in_tokens"] == 855
    assert summary["out_tokens"] == 287
