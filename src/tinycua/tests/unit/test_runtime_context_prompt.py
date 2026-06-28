"""Tests for runtime context in TinyCUA node prompts.

Phase 3 (FR-015/FR-016): the system prompt is byte-stable across calls (no
per-call timestamp) so prompt-cache prefixes hold on llama.cpp / OpenAI. The
slow-moving date (session-scoped snapshot) lives in the stable system prefix;
the fast-moving time-of-day lives in a volatile USER message in the suffix.
"""

from datetime import UTC, datetime

from tinycua.config.node_config import NodeConfigBase
from tinycua.config.system_prompt import build_runtime_context
from tinycua.loops.node import ProcessNode
from tinycua.models.session import Session


def test_build_runtime_context_is_stable_without_timestamp() -> None:
    """Runtime context without a snapshot is constant — no per-call timestamp (FR-015).

    The ``now`` arg is accepted for backward-compat but ignored; the context
    is byte-stable so the system prefix can be prompt-cached.
    """
    a = build_runtime_context(datetime(2026, 6, 19, 5, 0, tzinfo=UTC))
    b = build_runtime_context(datetime(2027, 1, 1, 0, 0, tzinfo=UTC))
    c = build_runtime_context()

    assert a == b == c, "runtime context must be byte-stable across calls"
    assert "## Runtime Context" in a
    # No timestamp fragments leak into the stable system context.
    assert "Current date/time:" not in a
    assert "Timezone:" not in a
    assert "Today:" not in a  # no snapshot → no date line


def test_build_runtime_context_includes_date_snapshot() -> None:
    """When date_snapshot is provided, it appears as `Today: <snapshot>`."""
    ctx = build_runtime_context(date_snapshot="2026-06-21 (Sunday)")
    assert "## Runtime Context" in ctx
    assert "Today: 2026-06-21 (Sunday)" in ctx


def test_system_prompt_is_byte_stable_across_calls() -> None:
    """Two consecutive build_system_message calls return identical bytes (FR-016)."""
    node = ProcessNode("x", NodeConfigBase(), instruction="Do the task.")

    first = node.build_system_message()
    second = node.build_system_message()

    assert first == second, "system message must be byte-stable across calls"


def test_time_lives_in_user_message_date_in_system() -> None:
    """Date snapshot is in the SYSTEM message; time-of-day is in a USER message."""
    session = Session()
    node = ProcessNode("x", NodeConfigBase(), instruction="Do the task.")
    node.ensure_session(session)

    messages = node.build_messages(session, {})

    system = messages[0]
    assert system["role"] == "system"
    assert "Do the task." in system["content"]
    assert "## Runtime Context" in system["content"]
    # The date snapshot must be in the system message.
    assert "Today:" in system["content"]
    # The time-of-day must NOT be in the system message.
    assert "Current time:" not in system["content"]
    # The old phrasing must not appear anywhere.
    assert "Current date/time:" not in system["content"]

    # The time-of-day must be in a user message in the suffix.
    user_msgs = [m for m in messages if m["role"] == "user"]
    assert any("Current time:" in m["content"] for m in user_msgs), (
        "time-of-day must appear in a user message"
    )


def test_system_prefix_stable_while_timestamp_varies() -> None:
    """The system message stays identical even as time advances between calls."""
    node = ProcessNode("x", NodeConfigBase(), instruction="Do the task.")
    sys1 = node.build_system_message()
    # Simulate a later call — system message cached, should be identical.
    sys2 = node.build_system_message()
    assert sys1 == sys2


def test_system_message_includes_date_snapshot_from_session() -> None:
    """The system message includes the session's date snapshot as `Today: ...`."""
    session = Session()
    session.date_snapshot = "2026-06-21 (Sunday)"
    node = ProcessNode("x", NodeConfigBase(), instruction="Do the task.")
    node.ensure_session(session)

    system = node.build_system_message()
    assert "Today: 2026-06-21 (Sunday)" in system["content"]


def test_child_session_inherits_root_date_snapshot() -> None:
    """ensure_session copies the root's date snapshot to the child session."""
    root = Session()
    root.date_snapshot = "2026-06-21 (Sunday)"
    node = ProcessNode("x", NodeConfigBase(), instruction="Do the task.")

    child = node.ensure_session(root)

    assert child.date_snapshot == "2026-06-21 (Sunday)"
    # And the node's system message picks it up.
    system = node.build_system_message()
    assert "Today: 2026-06-21 (Sunday)" in system["content"]


def test_system_prompt_differs_across_sessions_with_different_snapshots() -> None:
    """Two sessions with different snapshots produce different system messages."""
    session_a = Session()
    session_a.date_snapshot = "2026-06-21 (Sunday)"
    node_a = ProcessNode("a", NodeConfigBase(), instruction="Do the task.")
    node_a.ensure_session(session_a)

    session_b = Session()
    session_b.date_snapshot = "2027-01-01 (Friday)"
    node_b = ProcessNode("b", NodeConfigBase(), instruction="Do the task.")
    node_b.ensure_session(session_b)

    sys_a = node_a.build_system_message()
    sys_b = node_b.build_system_message()
    assert sys_a != sys_b
    assert "Today: 2026-06-21 (Sunday)" in sys_a["content"]
    assert "Today: 2027-01-01 (Friday)" in sys_b["content"]


def test_build_env_snapshot_is_nonempty_with_os_shell_python() -> None:
    """_build_env_snapshot produces a block with OS, Shell, and Python lines."""
    from tinycua.models.session import _build_env_snapshot

    snapshot = _build_env_snapshot()
    assert "Environment:" in snapshot
    assert "OS:" in snapshot
    assert "Shell:" in snapshot
    assert "/bin/sh" in snapshot
    assert "Python:" in snapshot


def test_session_has_env_snapshot_by_default() -> None:
    """A fresh Session captures an env_snapshot at construction."""
    session = Session()
    assert session.env_snapshot
    assert "OS:" in session.env_snapshot


def test_build_runtime_context_includes_env_snapshot() -> None:
    """When env_snapshot is provided, the Environment block appears."""
    env = (
        "Environment:\n"
        "- OS: Linux on x86_64\n"
        "- Shell: /bin/sh (POSIX sh)\n"
        "- Python: 3.12.13"
    )
    ctx = build_runtime_context(env_snapshot=env)
    assert "## Runtime Context" in ctx
    assert "Environment:" in ctx
    assert "/bin/sh" in ctx


def test_build_runtime_context_includes_workspace_when_set() -> None:
    """workspace_dir renders a Workspace line; None omits it."""
    ctx = build_runtime_context(workspace_dir="/workspace/experiment-2")
    assert "Workspace: /workspace/experiment-2" in ctx
    assert "file tools operate here" in ctx

    ctx_no_ws = build_runtime_context()
    assert "Workspace:" not in ctx_no_ws


def test_system_message_includes_env_snapshot_and_workspace() -> None:
    """The system message carries the session's env snapshot + workspace."""
    from pathlib import Path

    from tinycua.config.session_config import SessionConfig

    session = Session(session_config=SessionConfig(workspace_dir=Path("/workspace/x")))
    session.env_snapshot = (
        "Environment:\n- OS: Linux\n- Shell: /bin/sh\n- Python: 3.12.13"
    )
    node = ProcessNode("x", NodeConfigBase(), instruction="Do the task.")
    node.ensure_session(session)

    system = node.build_system_message()
    assert "Environment:" in system["content"]
    assert "/bin/sh" in system["content"]
    assert "Workspace: /workspace/x" in system["content"]


def test_child_session_inherits_env_snapshot() -> None:
    """ensure_session copies the root's env_snapshot to the child."""
    root = Session()
    root.env_snapshot = "Environment:\n- OS: Linux\n- Shell: /bin/sh"
    node = ProcessNode("x", NodeConfigBase(), instruction="Do the task.")

    child = node.ensure_session(root)

    assert "Shell: /bin/sh" in child.env_snapshot
    system = node.build_system_message()
    assert "Environment:" in system["content"]


def test_agents_md_snapshot_rendered_when_present(tmp_path) -> None:
    """AGENTS.md at {workspace}/AGENTS.md renders a Project Instructions section."""
    from pathlib import Path

    from tinycua.config.session_config import SessionConfig

    agents_content = "# Project Rules\n\nAlways write tests first."
    (tmp_path / "AGENTS.md").write_text(agents_content, encoding="utf-8")
    session = Session(session_config=SessionConfig(workspace_dir=Path(tmp_path)))
    node = ProcessNode("x", NodeConfigBase(), instruction="Do the task.")
    node.ensure_session(session)

    system = node.build_system_message()
    assert "## Project Instructions (AGENTS.md)" in system["content"]
    assert "Always write tests first." in system["content"]


def test_agents_md_snapshot_omitted_when_missing(tmp_path) -> None:
    """No AGENTS.md in the workspace → no Project Instructions section."""
    from pathlib import Path

    from tinycua.config.session_config import SessionConfig

    session = Session(session_config=SessionConfig(workspace_dir=Path(tmp_path)))
    node = ProcessNode("x", NodeConfigBase(), instruction="Do the task.")
    node.ensure_session(session)

    system = node.build_system_message()
    assert "Project Instructions" not in system["content"]
    # The node's (child) session cached the empty result (no re-read on next build).
    assert node.session.agents_md_snapshot == ""


def test_agents_md_snapshot_omitted_when_empty(tmp_path) -> None:
    """Empty AGENTS.md → no Project Instructions section."""
    from pathlib import Path

    from tinycua.config.session_config import SessionConfig

    (tmp_path / "AGENTS.md").write_text("   \n  \n", encoding="utf-8")
    session = Session(session_config=SessionConfig(workspace_dir=Path(tmp_path)))
    node = ProcessNode("x", NodeConfigBase(), instruction="Do the task.")
    node.ensure_session(session)

    system = node.build_system_message()
    assert "Project Instructions" not in system["content"]
    assert node.session.agents_md_snapshot == ""


def test_agents_md_snapshot_read_at_most_once(tmp_path) -> None:
    """Two builds read AGENTS.md once — the second uses the cached snapshot."""
    from pathlib import Path

    from tinycua.config.session_config import SessionConfig

    agents_path = tmp_path / "AGENTS.md"
    agents_path.write_text("rule v1", encoding="utf-8")
    session = Session(session_config=SessionConfig(workspace_dir=Path(tmp_path)))
    node = ProcessNode("x", NodeConfigBase(), instruction="Do the task.")
    node.ensure_session(session)

    node.build_system_message()
    assert node.session.agents_md_snapshot == "rule v1"
    # Mutate the file after the first read; the cached snapshot must not change.
    agents_path.write_text("rule v2", encoding="utf-8")
    node.build_system_message()
    assert node.session.agents_md_snapshot == "rule v1"


def test_agents_md_section_appears_between_instruction_and_runtime_context(tmp_path) -> None:
    """AGENTS.md is a static fragment after the node instruction, before runtime context."""
    from pathlib import Path

    from tinycua.config.session_config import SessionConfig

    (tmp_path / "AGENTS.md").write_text("PROJECT RULE", encoding="utf-8")
    session = Session(session_config=SessionConfig(workspace_dir=Path(tmp_path)))
    node = ProcessNode("x", NodeConfigBase(), instruction="Do the task.")
    node.ensure_session(session)

    system = node.build_system_message()
    content = system["content"]
    instr_pos = content.index("Do the task.")
    agents_pos = content.index("PROJECT RULE")
    runtime_pos = content.index("## Runtime Context")
    assert instr_pos < agents_pos < runtime_pos


def test_child_session_inherits_resolved_agents_md(tmp_path) -> None:
    """Child session inherits the root's resolved AGENTS.md snapshot."""
    from pathlib import Path

    from tinycua.config.session_config import SessionConfig

    (tmp_path / "AGENTS.md").write_text("inherited rule", encoding="utf-8")
    root = Session(session_config=SessionConfig(workspace_dir=Path(tmp_path)))
    # Resolve on the root first (simulates the root node building its system msg).
    from tinycua.loops.node import _resolve_agents_md

    _resolve_agents_md(root)
    assert root.agents_md_snapshot == "inherited rule"
    node = ProcessNode("x", NodeConfigBase(), instruction="Do the task.")
    child = node.ensure_session(root)
    assert child.agents_md_snapshot == "inherited rule"
