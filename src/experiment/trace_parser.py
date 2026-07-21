"""TinyCUA stdout trace parser.

Parses a TinyCUA ``run_logs/stdout.txt`` into a normalized event stream,
summarizes node costs and reviewer verdicts, and classifies each LLM-call's
tokens as architectural-inherent vs prototype-defect overhead using a strict,
documented signal catalog.

The parser is intentionally single-backend: only TinyCUA's grammar is
recognized. Other harnesses (OpenCode, Hermes, OpenClaw) are read by hand and
cited by stdout line number in the reports; their grammars differ too much to
share a parser.

Stdout grammar (confirmed against experiment-4):

    [<node_snake>] start
    [<node_snake>] tool_call: <tool>
    [<node_snake>] usage: input_tokens=N output_tokens=N total_tokens=N
    [<node_snake>] completed: <reason>
    [tool-result] node=<NodePascal> tool=<tool> [optional key=value]* [completed]

Free-form assistant reasoning text appears between structural events and is
captured as ``text`` events so the reviewer's cited cause can be linked to its
verdict. TinyCUA stdout carries no per-event wall-clock timestamp, so event
``seq`` (the source line number) acts as the timeline index.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

# snake_case start/tool_call/usage/completed tag -> PascalCase node name used
# in [tool-result] lines. Every observed start tag maps here.
NODE_TAG_TO_CANONICAL: dict[str, str] = {
    "query_analyst": "QueryAnalyst",
    "digester": "InformationDigester",
    "worker": "Worker",
    "task_create": "TaskCreate",
    "task_analyzer": "TaskAnalyzer",
    "analysis_effort": "AnalysisEffort",
    "task_assessor": "TaskAssessor",
    "task_executor": "TaskExecutor",
    "result_reviewer": "ResultReviewer",
    "result_aggregation": "ResultAggregation",
    "response": "Response",
}

# Strict defect-signal thresholds; codified exactly, not heuristic.
LIST_FILES_OVERSIZE_THRESHOLD = 500
NEEDS_REVISION_TRIPLE_THRESHOLD = 3

_RE_START = re.compile(r"^\[(?P<tag>[a-z_]+)\] start$")
_RE_TOOL_CALL = re.compile(r"^\[(?P<tag>[a-z_]+)\] tool_call: (?P<tool>[A-Za-z_]+)$")
_RE_USAGE = re.compile(
    r"^\[(?P<tag>[a-z_]+)\] usage: "
    r"input_tokens=(?P<in>\d+) output_tokens=(?P<out>\d+) total_tokens=(?P<total>\d+)$"
)
_RE_COMPLETED = re.compile(r"^\[(?P<tag>[a-z_]+)\] completed: (?P<reason>\w+)$")
_RE_TOOL_RESULT = re.compile(r"^\[tool-result\] (?P<rest>.+)$")
_RE_LIVE_HEADER = re.compile(r"^=== LIVE STREAM ===$")

# Anchored regex set for reviewer-cited causes. Matches only when the cause
# appears verbatim in the assistant text immediately preceding the verdict.
# A non-match is recorded as "unclassified" and the raw text is preserved
# verbatim so an auditor can reclassify by hand.
CAUSE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "missing_import",
        re.compile(r"missing\s+(?:[A-Za-z_][\w.]*)?\s*import", re.IGNORECASE),
    ),
    ("type_error", re.compile(r"\bTypeError\b", re.IGNORECASE)),
    ("syntax_error", re.compile(r"syntax\s+error", re.IGNORECASE)),
    (
        "module_not_found",
        re.compile(
            r"ModuleNotFoundError|ImportError|module\s+(?:\w+\s+)?not\s+found",
            re.IGNORECASE,
        ),
    ),
    (
        "database_failed",
        re.compile(
            r"database.*(?:failed|error|unable)|unable\s+to\s+open\s+database",
            re.IGNORECASE,
        ),
    ),
    ("exit_code", re.compile(r"exit\s+code\s+\d+", re.IGNORECASE)),
    ("expected_got", re.compile(r"expected.*got", re.IGNORECASE)),
    ("cannot_empty", re.compile(r"cannot\s+.*empty", re.IGNORECASE)),
)


class TraceParseError(ValueError):
    """Raised on a structural line that cannot be parsed; never silently dropped."""


def parse_tool_result_fields(rest: str) -> dict:
    """Parse the ``key=value`` tail of a ``[tool-result]`` line."""
    tokens = rest.split()
    out: dict = {"node": None, "tool": None}
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if "=" in tok:
            key, _, value = tok.partition("=")
            out[key] = _coerce_field(key, value)
            i += 1
            continue
        if tok == "completed":
            out["completed"] = True
            i += 1
            continue
        # Bare token with no '=': attach to the most recent key lacking one.
        # In practice this only happens inside multi-part tool names; we ignore
        # stray unstructured tail here since none of the report signals need it.
        i += 1
    # Required fields.
    if out["node"] is None or out["tool"] is None:
        raise TraceParseError(f"tool-result line missing node/tool: {rest!r}")
    return out


def _coerce_field(key: str, value: str) -> object:
    """Coerce known tool-result field values to their Python type."""
    if key in {"success"}:
        return value.lower() == "true"
    if key == "timed_out":
        return value.lower() == "true"
    if key in {"exit_code", "items"}:
        try:
            return int(value)
        except ValueError as exc:
            raise TraceParseError(f"non-integer {key}={value!r}") from exc
    return value  # task_id, status, decision, path, etc. stay strings.


@dataclass
class _EventBuf:
    """Accumulator for the assistant reasoning blob between structural events."""

    text: list[str] = field(default_factory=list)
    start_seq: int | None = None

    def reset(self, seq: int) -> None:
        self.text = []
        self.start_seq = seq

    def append(self, line: str) -> None:
        if self.start_seq is None:
            self.start_seq = 0
        self.text.append(line)

    def flush(self) -> tuple[int, str] | None:
        if not self.text:
            self.start_seq = None
            return None
        text = "\n".join(self.text)
        seq = self.start_seq if self.start_seq is not None else 0
        self.reset(0)
        return seq, text


def parse_stdout(text: str) -> list[dict]:
    """Stream a TinyCUA stdout string into normalized event dicts in source order."""
    events: list[dict] = []
    buf = _EventBuf()
    for seq, raw in enumerate(text.splitlines(), start=1):
        line = raw.rstrip("\r")
        if _RE_LIVE_HEADER.match(line):
            continue
        if not line.strip():
            continue  # blank lines between turns are not events

        m = _RE_START.match(line)
        if m:
            _flush_text(events, buf)
            tag = m.group("tag")
            if tag not in NODE_TAG_TO_CANONICAL:
                raise TraceParseError(f"unknown node tag at line {seq}: {tag!r}")
            events.append(
                {
                    "seq": seq,
                    "kind": "session_start",
                    "actor": NODE_TAG_TO_CANONICAL[tag],
                }
            )
            continue
        m = _RE_TOOL_CALL.match(line)
        if m:
            _flush_text(events, buf)
            tag = m.group("tag")
            _require_known_tag(tag, seq)
            events.append(
                {
                    "seq": seq,
                    "kind": "tool_call",
                    "actor": NODE_TAG_TO_CANONICAL[tag],
                    "tool": m.group("tool"),
                }
            )
            continue
        m = _RE_USAGE.match(line)
        if m:
            _flush_text(events, buf)
            tag = m.group("tag")
            _require_known_tag(tag, seq)
            events.append(
                {
                    "seq": seq,
                    "kind": "usage",
                    "actor": NODE_TAG_TO_CANONICAL[tag],
                    "in_tokens": int(m.group("in")),
                    "out_tokens": int(m.group("out")),
                    "total_tokens": int(m.group("total")),
                }
            )
            continue
        m = _RE_COMPLETED.match(line)
        if m:
            _flush_text(events, buf)
            tag = m.group("tag")
            _require_known_tag(tag, seq)
            events.append(
                {
                    "seq": seq,
                    "kind": "session_end",
                    "actor": NODE_TAG_TO_CANONICAL[tag],
                    "reason": m.group("reason"),
                }
            )
            continue
        m = _RE_TOOL_RESULT.match(line)
        if m:
            _flush_text(events, buf)
            fields = parse_tool_result_fields(m.group("rest"))
            event = {
                "seq": seq,
                "kind": "tool_result",
                "actor": fields["node"],
                "tool": fields["tool"],
            }
            for k, v in fields.items():
                if k in {"node", "tool"}:
                    continue
                event[k] = v
            events.append(event)
            continue

        # No structural match: part of the assistant reasoning blob.
        buf.append(line)

    _flush_text(events, buf)
    return events


def _flush_text(events: list[dict], buf: _EventBuf) -> None:
    flushed = buf.flush()
    if flushed is None:
        return
    seq, text = flushed
    events.append({"seq": seq, "kind": "text", "text": text})


def _require_known_tag(tag: str, seq: int) -> None:
    if tag not in NODE_TAG_TO_CANONICAL:
        raise TraceParseError(f"unknown node tag at line {seq}: {tag!r}")


def _sessions(events: Iterable[dict]) -> list[dict]:
    """Group events into per-session spans keyed by start_seq.

    Each span records its actor, the seq range, and the tool_calls/usage/tool_results
    that happened inside it. Tools emitted after a session_end (e.g. the trailing
    terminate tool-result) are attached to the most recently closed session of
    the same actor, since they semantically belong to it.
    """
    spans: list[dict] = []
    pending: dict[str, int] = {}  # actor -> current span index
    last_closed: dict[str, int] = {}  # actor -> last closed span index
    for ev in events:
        if ev["kind"] == "session_start":
            span = {
                "actor": ev["actor"],
                "start_seq": ev["seq"],
                "end_seq": None,
                "usage_events": [],
                "tool_calls": [],
                "tool_results": [],
                "decisions": [],
                "task_ids": set(),
                "file_paths": [],
                "no_terminate": True,
            }
            spans.append(span)
            pending[ev["actor"]] = len(spans) - 1
            continue
        if ev["kind"] == "session_end":
            actor = ev["actor"]
            idx = pending.get(actor)
            if idx is None:
                # Orphan session_end (e.g. interleaved emit); still record at span level.
                continue
            spans[idx]["end_seq"] = ev["seq"]
            last_closed[actor] = idx
            del pending[actor]
            continue
        # Attribute tool_call / usage / tool_result to whichever span owns them.
        actor = ev.get("actor")
        if actor is None:
            continue  # text event or anything else without an owning node
        idx = pending.get(actor)
        if idx is None:
            idx = last_closed.get(actor)
        if idx is None:
            continue  # stray event without a start; skip silently (not a defect signal target)
        span = spans[idx]
        if ev["kind"] == "tool_call":
            span["tool_calls"].append(ev)
            if ev["tool"] == "terminate":
                span["no_terminate"] = False
        elif ev["kind"] == "usage":
            span["usage_events"].append(ev)
        elif ev["kind"] == "tool_result":
            span["tool_results"].append(ev)
            if "decision" in ev:
                span["decisions"].append(ev)
            if "task_id" in ev:
                span["task_ids"].add(ev["task_id"])
            if "path" in ev:
                span["file_paths"].append(ev["path"])
    return spans


def summarize(events: list[dict]) -> dict:
    """Produce aggregate counts from a parsed event stream."""
    if not events:
        return _empty_summary()

    verdicts: Counter = Counter()
    task_rework: Counter = Counter()
    by_node: dict[str, dict] = {}
    for ev in events:
        actor = ev.get("actor", "")
        if ev["kind"] == "usage":
            node = by_node.setdefault(
                actor, {"calls": 0, "in_tokens": 0, "out_tokens": 0, "total_tokens": 0}
            )
            node["calls"] += 1
            node["in_tokens"] += ev["in_tokens"]
            node["out_tokens"] += ev["out_tokens"]
            node["total_tokens"] += ev["total_tokens"]
        elif ev["kind"] == "tool_result":
            decision = ev.get("decision")
            if decision:
                verdicts[decision] += 1
                if decision in {"needs_revision", "rejected", "replan"}:
                    task_id = ev.get("task_id")
                    if task_id:
                        task_rework[task_id] += 1

    llm_calls = sum(n["calls"] for n in by_node.values())
    in_tokens = sum(n["in_tokens"] for n in by_node.values())
    out_tokens = sum(n["out_tokens"] for n in by_node.values())
    total_tokens = sum(n["total_tokens"] for n in by_node.values())
    return {
        "llm_calls": llm_calls,
        "in_tokens": in_tokens,
        "out_tokens": out_tokens,
        "total_tokens": total_tokens,
        "by_node": by_node,
        "review_verdicts": dict(verdicts),
        "task_rework_counts": dict(task_rework),
    }


def classify_defect_signals(events: list[dict], summary: dict) -> dict:
    """Flag LLM-call tokens as architectural vs prototype-defect by strict signals.

    Signals (codified exactly; see the module docstring for the prose version):

    1. ``multi_decision_reviewer_session``: a reviewer session emits >=2
       ``task_review_decision`` calls.
    2. ``triple_needs_revision_task``: one task_id received >=3 needs_revision
       verdicts; flags every session that touched that task_id.
    3. ``non_zero_shell``: ``run_shell`` / ``run_python`` returned ``exit_code!=0``
       or any tool returned ``timed_out=True``.
    4. ``oversize_listing``: ``list_files`` / ``search_files`` returned >=500 items.
    5. ``session_without_terminate``: a session ended without a prior
       ``terminate`` tool_call.

    Signal #6 from the experiment plan (same-path consecutive rework) is folded
    into #2 in practice: a task hitting the triple threshold is already flagged,
    and the same-path detail is rendered as a citation in the report rather than
    a separate token-attribution signal.
    """
    spans = _sessions(events)
    signal_counts = Counter()
    defect_session_idxs: set[int] = set()

    for idx, span in enumerate(spans):
        # Signal #1: multi-decision reviewer session.
        if span["actor"] == "ResultReviewer" and len(span["decisions"]) >= 2:
            signal_counts["multi_decision_reviewer_session"] += 1
            defect_session_idxs.add(idx)
        # Signal #5: session ended without terminate.
        if span["end_seq"] is not None and span["no_terminate"]:
            signal_counts["session_without_terminate"] += 1
            defect_session_idxs.add(idx)
        # Signals #3 and #4 fire on tool_results inside the session.
        for tr in span["tool_results"]:
            tool = tr["tool"]
            exit_code = tr.get("exit_code")
            if exit_code is not None and exit_code != 0:
                signal_counts["non_zero_shell"] += 1
                defect_session_idxs.add(idx)
            if tr.get("timed_out"):
                signal_counts["non_zero_shell"] += 1
                defect_session_idxs.add(idx)
            items = tr.get("items")
            if (
                items is not None
                and items >= LIST_FILES_OVERSIZE_THRESHOLD
                and tool in {"list_files", "search_files"}
            ):
                signal_counts["oversize_listing"] += 1
                defect_session_idxs.add(idx)

    # Signal #2: triple needs_revision per task. Propagate to every session that
    # touched the offending task_id. The signal count records the number of
    # offending tasks (one per task crossing the threshold), not the number of
    # sessions.
    triple_tasks = {
        tid
        for tid, count in summary["task_rework_counts"].items()
        if count >= NEEDS_REVISION_TRIPLE_THRESHOLD
    }
    signal_counts["triple_needs_revision_task"] = len(triple_tasks)
    if triple_tasks:
        for idx, span in enumerate(spans):
            if triple_tasks & span["task_ids"]:
                defect_session_idxs.add(idx)

    defect_usage_seqs: set[int] = set()
    for idx in defect_session_idxs:
        for ev in spans[idx]["usage_events"]:
            defect_usage_seqs.add(ev["seq"])

    defect_usage_events = [
        ev for ev in events if ev["kind"] == "usage" and ev["seq"] in defect_usage_seqs
    ]
    arch_tokens = sum(
        ev["total_tokens"]
        for ev in events
        if ev["kind"] == "usage" and ev["seq"] not in defect_usage_seqs
    )
    defect_tokens = sum(ev["total_tokens"] for ev in defect_usage_events)

    return {
        "signal_counts": dict(signal_counts),
        "defect_session_count": len(defect_session_idxs),
        "total_sessions": len(spans),
        "defect_usage_events": defect_usage_events,
        "architectural_tokens": arch_tokens,
        "prototype_defect_tokens": defect_tokens,
    }


def extract_reviewer_causes(events: list[dict]) -> list[dict]:
    """Link each reviewer verdict to the assistant text that preceded it.

    Returns one row per ``task_review_decision`` tool_result with the cited
    cause (matched against the anchored catalog) and the raw preceding text.
    Non-matching texts are recorded as ``cause="unclassified"`` with the raw
    text preserved verbatim so the report can flag them for manual review.
    """
    rows: list[dict] = []
    pending_text: str | None = None
    for ev in events:
        if ev["kind"] == "text":
            pending_text = ev["text"]
            continue
        if (
            ev["kind"] == "tool_result"
            and ev["tool"] == "task_review_decision"
            and "decision" in ev
        ):
            cause = "unclassified"
            if pending_text:
                for name, pattern in CAUSE_PATTERNS:
                    if pattern.search(pending_text):
                        cause = name
                        break
            rows.append(
                {
                    "seq": ev["seq"],
                    "task_id": ev.get("task_id"),
                    "decision": ev["decision"],
                    "status": ev.get("status"),
                    "cited_cause": cause,
                    "preceding_text": pending_text or "",
                }
            )
            pending_text = None
    return rows


def _empty_summary() -> dict:
    return {
        "llm_calls": 0,
        "in_tokens": 0,
        "out_tokens": 0,
        "total_tokens": 0,
        "by_node": {},
        "review_verdicts": {},
        "task_rework_counts": {},
    }


def parse_run(run_logs: Path) -> dict:
    """Read one run_logs dir, write events.jsonl + run_summary.json, return summary."""
    stdout_path = run_logs / "stdout.txt"
    if not stdout_path.exists():
        raise FileNotFoundError(f"no stdout at {stdout_path}")
    text = stdout_path.read_text()
    events = parse_stdout(text)
    summary = summarize(events)
    defects = classify_defect_signals(events, summary)
    causes = extract_reviewer_causes(events)

    # Attach metadata if available so the report can cite duration.
    metadata_path = run_logs / "metadata.json"
    metadata = {}
    if metadata_path.exists():
        try:
            metadata = json.loads(metadata_path.read_text())
        except json.JSONDecodeError:
            logger.warning("metadata.json unreadable at %s", metadata_path)

    # Per-task story card, only for tasks that triggered signal #2 (>=3 reworks).
    # Embedded into run_summary.json so a single file write carries all output
    # (failed multi-file write on the 9p drvfs worktree mount was the motivation).
    triple_sorted = sorted(
        [
            tid
            for tid, c in summary["task_rework_counts"].items()
            if c >= NEEDS_REVISION_TRIPLE_THRESHOLD
        ],
        key=lambda t: -summary["task_rework_counts"][t],
    )
    task_stories = {tid: _task_story(events, tid) for tid in triple_sorted}

    full_summary = {
        **summary,
        "defect_signals": defects["signal_counts"],
        "defect_session_count": defects["defect_session_count"],
        "total_sessions": defects["total_sessions"],
        "architectural_tokens": defects["architectural_tokens"],
        "prototype_defect_tokens": defects["prototype_defect_tokens"],
        "reviewer_causes": causes,
        "task_stories": task_stories,
        "metadata": metadata,
    }
    full_summary.pop(
        "defect_usage_events", None
    )  # not serializable-friendly; events file covers it

    (run_logs / "events.jsonl").write_text(
        "\n".join(json.dumps(ev, default=str) for ev in events)
        + ("\n" if events else "")
    )
    (run_logs / "run_summary.json").write_text(
        json.dumps(full_summary, indent=2, default=str) + "\n"
    )
    return full_summary


def _task_story(events: list[dict], task_id: str) -> dict:
    """Assemble a per-task timeline from event stream for the given task_id."""
    timeline: list[dict] = []
    pending_text: str | None = None
    for ev in events:
        if ev["kind"] == "text":
            pending_text = ev["text"]
            continue
        if ev.get("task_id") != task_id:
            continue
        row = {
            "seq": ev["seq"],
            "kind": ev["kind"],
            "actor": ev.get("actor"),
            "tool": ev.get("tool"),
        }
        for key in (
            "decision",
            "status",
            "path",
            "exit_code",
            "items",
            "success",
            "timed_out",
        ):
            if key in ev:
                row[key] = ev[key]
        if (
            pending_text
            and ev["kind"] == "tool_result"
            and ev.get("tool") == "task_review_decision"
        ):
            row["preceding_text"] = pending_text
        timeline.append(row)
        if ev["kind"] == "tool_result":
            pending_text = None
    rework_count = sum(
        1
        for r in timeline
        if r.get("decision") in {"needs_revision", "rejected", "replan"}
    )
    return {"task_id": task_id, "rework_count": rework_count, "timeline": timeline}


def main(argv: list[str] | None = None) -> int:
    """CLI entry point.

    Two modes:
      --run-logs PATH   parse a single run_logs dir
      --all-glob PATH   parse every experiment-*/run_logs under PATH (tinycua root)

    Writes events.jsonl and run_summary.json into each parsed run_logs dir.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-logs", type=Path, help="single run_logs dir to parse")
    parser.add_argument(
        "--all-glob",
        type=Path,
        help="parent dir (e.g. evaluation-results/tinycua); parses experiment-*/run_logs",
    )
    args = parser.parse_args(argv)
    if not args.run_logs and not args.all_glob:
        parser.error("provide --run-logs or --all-glob")

    parsed = 0
    if args.run_logs:
        summary = parse_run(args.run_logs)
        print(f"parsed {args.run_logs}: llm_calls={summary['llm_calls']}")
        parsed += 1
    if args.all_glob:
        for run_logs in sorted(args.all_glob.glob("experiment-*/run_logs")):
            if not run_logs.is_dir():
                continue
            try:
                summary = parse_run(run_logs)
            except TraceParseError as exc:
                logger.error("parse failed for %s: %s", run_logs, exc)
                continue
            print(f"parsed {run_logs}: llm_calls={summary['llm_calls']}")
            parsed += 1
    print(f"done: {parsed} run(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
