"""Session model for tracking agent execution state."""

from __future__ import annotations

import logging
import os
import platform
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

from tinycua.models.task import Task, TaskStateStore

if TYPE_CHECKING:
    from tinycua.config.session_config import SessionConfig
    from tinycua.models.chat_record import ChatRecord
    from tinycua.models.session_context_entry import SessionContextEntry

logger = logging.getLogger(__name__)


def _detect_virtualization() -> list[str]:
    """Detect virtualization signals (Docker, WSL2, etc.). Pure stdlib.

    Returns a list of detected signals (e.g. ["Docker container", "WSL2 host"]).
    Empty list means bare metal / no virtualization detected.
    """
    signals: list[str] = []
    if os.path.exists("/.dockerenv"):
        signals.append("Docker container")
    try:
        with open("/proc/1/cgroup", encoding="utf-8") as f:
            cg = f.read()
        if "docker" in cg or "kubepods" in cg:
            if "Docker container" not in signals:
                signals.append("container (cgroup)")
    except (OSError, PermissionError):
        pass
    release = platform.release().lower()
    if "microsoft" in release and "wsl" in release:
        signals.append("WSL2 host")
    return signals


def _detect_distro() -> str:
    """Best-effort distro name from /etc/os-release. Empty string if unknown."""
    try:
        with open("/etc/os-release", encoding="utf-8") as f:
            for line in f:
                if line.startswith("PRETTY_NAME="):
                    return line.split("=", 1)[1].strip().strip('"')
    except (OSError, PermissionError):
        pass
    return ""


def _build_env_snapshot() -> str:
    """Build a session-scoped environment snapshot for the system prompt.

    Captures OS + virtualization + shell + python at call time. Pure stdlib
    (platform + file checks) — no subprocess calls. Failures degrade
    gracefully (skip that signal). Stable for the session lifetime so
    FR-015 prompt-cache stability holds.

    Returns the multi-line ``Environment:`` block (no leading ``##`` — the
    caller places it in the runtime context).
    """
    os_name = platform.system()
    machine = platform.machine()
    distro = _detect_distro()
    os_label = f"{os_name} ({distro})" if distro else os_name
    virt_signals = _detect_virtualization()
    virt_label = ", ".join(virt_signals) if virt_signals else "bare metal"
    py_version = platform.python_version()
    return (
        "Environment:\n"
        f"- OS: {os_label} on {machine}\n"
        f"- Virtualization: {virt_label}\n"
        "- Shell: /bin/sh (POSIX sh — bash syntax like [[ ]], brace expansion {a,b}, "
        "source, or the `function` keyword is not supported)\n"
        f"- Python: {py_version} (run_python executes in this version)"
    )


@dataclass
class Session:
    """Represents an agent execution session.

    A session tracks the conversation history, context entries,
    and associated task/todo state for a single agent execution.

    Attributes:
        session_id: Unique identifier for this session.
        parent_id: Optional parent session ID for child sessions.
        session_config: Configuration applied to this session.
        input_context: Merged SDK messages from the agent loop.
        chat_history: Append-only durable audit transcript.
        session_context: Mutable LLM-reusable context with segment metadata.
        diagnostics: Internal runtime diagnostics that must not be sent as
            reusable LLM context.
        task: Optional root task object.
        task_store: Session-owned task tree state.
        todo: Optional todo list.
    """

    session_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    parent_id: str | None = None
    session_config: SessionConfig | None = None
    input_context: list[dict[str, Any]] = field(default_factory=list)
    chat_history: list[ChatRecord] = field(default_factory=list)
    session_context: list[SessionContextEntry] = field(default_factory=list)
    diagnostics: list[dict[str, Any]] = field(default_factory=list)
    task: Task | None = None
    task_store: TaskStateStore = field(default_factory=TaskStateStore)
    todo: list[dict[str, Any]] = field(default_factory=list)
    # Session-owned artifact history store (workspace revisions, result
    # revisions, review checkpoint). Root sessions own it; scoped node
    # sessions share the reference so one run keeps one revision chain.
    artifact_store: Any = None
    # Milestone 8 Stream B: per-session token tracking from provider usage.
    # Updated after each LLM call from response.usage.input_tokens.
    # Used to trigger compaction before the next call when over threshold.
    _last_input_tokens: int = 0
    # Session-scoped date snapshot for the system prompt (FR-015). Slow-moving
    # time info (date + weekday) injected into the stable system prefix so the
    # model sees the authoritative current date without a per-call timestamp
    # breaking prompt-cache stability. Set once at construction; child sessions
    # inherit the root's snapshot via ensure_session() so all nodes in one run
    # share one date. Never mutated during the session.
    date_snapshot: str = field(
        default_factory=lambda: datetime.now().strftime("%Y-%m-%d (%A)")
    )
    # Session-scoped environment snapshot for the system prompt (FR-015).
    # OS + virtualization + shell + python, captured once at construction.
    # Stable for the session lifetime so the prompt-cache prefix stays
    # byte-stable. Child sessions inherit the root's snapshot via
    # ensure_session(). Never mutated during the session.
    env_snapshot: str = field(default_factory=_build_env_snapshot)
    # Lazy AGENTS.md snapshot. None = not yet read from disk; "" = read but
    # missing/empty (no Project Instructions section); non-empty = read with
    # content. Resolved on first build_system_message call (by then
    # session_config.workspace_dir is set), then cached so we read the file
    # at most once per session. Child sessions inherit the resolved value.
    agents_md_snapshot: str | None = None
    # FR-062: per-node progress trackers, keyed by node_id. Survives node
    # reconstruction (fresh node instances read from here). Cleaned up when
    # a node completes (don't store done nodes).
    node_progress: dict[str, Any] = field(default_factory=dict)
    # Editable structured tool payloads. Kept in memory because sessions do
    # not currently support cross-process resume.
    json_drafts: dict[str, dict[str, Any]] = field(default_factory=dict)

    @staticmethod
    def _summary_to_entry(summary: Any) -> SessionContextEntry:
        """Convert a compaction summary (dict or entry) to a SessionContextEntry."""
        from tinycua.models.session_context_entry import SessionContextEntry

        if isinstance(summary, dict):
            if "record_id" in summary or "segment" in summary:
                return SessionContextEntry.from_dict(summary)
            return SessionContextEntry(
                content=summary.get("content", ""),
                segment="prior",
                created_seq=0,
            )
        return summary

    async def compact_context(
        self, window: list[SessionContextEntry] | list[dict[str, Any]] | None = None
    ) -> dict[str, Any] | None:
        """Compact context entries using the configured strategy.

        If no ``compaction_strategy`` is set on ``session_config``, returns
        ``None`` immediately. Otherwise delegates to the strategy's
        ``compact()`` method and replaces the compacted window in
        ``session_context`` with the resulting summary.

        Args:
            window: Optional explicit subset of messages to compact. When
                ``None``, uses the full ``session_context``.

        Returns:
            The assistant-role summary dict produced by the strategy, or
            ``None`` if no strategy is configured.
        """
        if (
            self.session_config is None
            or self.session_config.compaction_strategy is None
        ):
            return None

        # Early return for empty window — nothing to compact.
        if window is not None and len(window) == 0:
            return None

        strategy = self.session_config.compaction_strategy

        # Convert SessionContextEntry objects to dicts for compaction strategy
        def _to_dict(entry: SessionContextEntry | dict[str, Any]) -> dict[str, Any]:
            if isinstance(entry, dict):
                return entry
            return entry.to_dict()

        if window is not None:
            messages = [_to_dict(entry) for entry in window]
        else:
            messages = [_to_dict(entry) for entry in self.session_context]

        summary = await strategy.compact(messages)

        if window is None:
            self.session_context = [self._summary_to_entry(summary)]
        elif len(window) > 0:
            # Remove the compacted window entries and append the summary.
            # Find the window by comparing expected sequence within session_context.
            # Assumes window is a contiguous subset of session_context.
            window_len = len(window)
            for i in range(len(self.session_context) - window_len + 1):
                current_slice = self.session_context[i : i + window_len]
                current_dicts = [_to_dict(entry) for entry in current_slice]
                window_dicts = [_to_dict(entry) for entry in window]
                if current_dicts == window_dicts:
                    summary_entry = self._summary_to_entry(summary)
                    self.session_context = (
                        self.session_context[:i]
                        + [summary_entry]
                        + self.session_context[i + window_len :]
                    )
                    break
            else:
                msg = "Supplied window is not a contiguous subset of session_context"
                raise ValueError(msg)

        return summary
