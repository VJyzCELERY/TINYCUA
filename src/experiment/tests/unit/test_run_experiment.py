"""Unit tests for experiment runner helpers."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
import run_experiment

from run_experiment import (
    AGENTS,
    _format_stream_line,
    _hermes_poll_timed_out,
    _hermes_process_poll_completed,
    _hermes_process_poll_started,
    _no_response_sentinel,
    build_permission_repair_command,
    build_metadata,
    load_prompt,
    parse_agents,
    prepare_result_dirs,
    read_hermes_process_poll_timeout_seconds,
    read_timeout_seconds,
    sanitize_workdir,
)


def test_load_prompt_from_file_strips_only_newline(tmp_path: Path) -> None:
    """Prompt files keep meaningful leading text."""
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text(" make a clock\n")

    assert load_prompt(None, prompt_file) == " make a clock"


def test_load_prompt_rejects_empty_text() -> None:
    """Whitespace prompts are invalid."""
    with pytest.raises(ValueError, match="prompt"):
        load_prompt("   ", None)


def test_prepare_result_dirs_creates_agent_paths(tmp_path: Path) -> None:
    """Every agent gets an isolated experiment directory with workdir/ and logs/."""
    paths = prepare_result_dirs(tmp_path, 2, overwrite=False)

    assert tuple(paths) == AGENTS
    for agent, path in paths.items():
        assert path["workdir"] == tmp_path / agent / "experiment-2" / "workdir"
        assert path["logs"] == tmp_path / agent / "experiment-2" / "logs"
        assert path["workdir"].is_dir()
        assert path["logs"].is_dir()


def test_prepare_result_dirs_creates_sibling_system_artifact_dir(
    tmp_path: Path,
) -> None:
    """TinyCUA audit state mounts beside, never inside, the judged workdir."""
    paths = prepare_result_dirs(tmp_path, 2, overwrite=False)

    tinycua = paths["tinycua"]
    system_artifacts = tinycua["system_artifacts"]
    assert (
        system_artifacts == tmp_path / "tinycua" / "experiment-2" / "system-artifacts"
    )
    assert system_artifacts.is_dir()
    # The system-artifact directory is a sibling of the judged workdir.
    assert system_artifacts.parent == tinycua["workdir"].parent
    assert system_artifacts != tinycua["workdir"]
    assert not system_artifacts.is_relative_to(tinycua["workdir"])


def test_sanitize_workdir_does_not_touch_sibling_system_artifacts(
    tmp_path: Path,
) -> None:
    """Judging cleans the workdir without consuming external audit state."""
    paths = prepare_result_dirs(tmp_path, 2, overwrite=False)
    system_artifacts = paths["tinycua"]["system_artifacts"]
    marker = system_artifacts / "revisions.jsonl"
    marker.write_text("{}")

    sanitize_workdir("tinycua", paths["tinycua"]["workdir"])

    assert marker.exists()
    assert not (paths["tinycua"]["workdir"] / "system-artifacts").exists()


def test_prepare_result_dirs_can_select_agents(tmp_path: Path) -> None:
    """A rerun can isolate one harness without touching other outputs."""
    existing = tmp_path / "opencode" / "experiment-2"
    existing.mkdir(parents=True)
    paths = prepare_result_dirs(
        tmp_path,
        2,
        overwrite=True,
        agents=("tinycua",),
    )

    assert tuple(paths) == ("tinycua",)
    assert existing.exists()
    assert (tmp_path / "tinycua" / "experiment-2" / "workdir").is_dir()


def test_system_artifacts_mount_is_tinycua_only(tmp_path: Path, monkeypatch) -> None:
    """Only TinyCUA receives its private system-artifacts mount."""
    mounted: dict[str, Path | None] = {}

    def fake_run_agent(agent: str, *args, system_artifacts: Path | None = None) -> int:
        mounted[agent] = system_artifacts
        return 0

    monkeypatch.setattr(run_experiment, "run_agent", fake_run_agent)

    assert (
        run_experiment.main(
            [
                "--prompt",
                "test",
                "--agents",
                "tinycua,opencode",
                "--num",
                "1",
                "--output-root",
                str(tmp_path),
            ]
        )
        == 0
    )
    assert mounted["tinycua"] is not None
    assert mounted["opencode"] is None


def test_non_tinycua_run_agent_ignores_system_artifacts(
    tmp_path: Path, monkeypatch
) -> None:
    """Direct harness callers cannot mount TinyCUA's system artifacts."""
    command: list[str] = []

    class Completed:
        returncode = 0

    def capture(args, **kwargs):  # noqa: ANN001, ARG001
        command.extend(args)
        return Completed()

    monkeypatch.setattr(run_experiment.subprocess, "run", capture)
    logs = tmp_path / "logs"
    logs.mkdir()

    run_experiment.run_agent(
        "opencode", 1, "prompt", tmp_path, logs, 1, system_artifacts=tmp_path / "system"
    )

    assert "EXPERIMENT_SYSTEM_ARTIFACTS=/workspace/system-artifacts" not in command


def test_parse_agents_rejects_unknown() -> None:
    """Agent filters must be real harness names."""
    assert parse_agents("opencode,tinycua") == ("opencode", "tinycua")
    with pytest.raises(ValueError, match="unknown"):
        parse_agents("tinycua,nope")


def test_no_response_sentinel_matches_openclaw_failure(tmp_path: Path) -> None:
    """OpenClaw exits 0 but prints a no-response warning; the runner must flag it."""
    log = tmp_path / "stdout.log"
    log.write_text(
        "[agent/embedded] embedded run agent end: isError=false\n"
        "⚠️ Agent couldn't generate a response. Note: some tool actions may have already been executed — please verify before retrying.\n"
    )

    assert _no_response_sentinel("openclaw", log.read_text()) is True
    assert _no_response_sentinel("opencode", log.read_text()) is False
    assert _no_response_sentinel("openclaw", "all good, response shipped") is False


def test_prepare_result_dirs_requires_overwrite(tmp_path: Path) -> None:
    """Existing outputs are guarded by default."""
    existing = tmp_path / "tinycua" / "experiment-2"
    existing.mkdir(parents=True)

    with pytest.raises(FileExistsError):
        prepare_result_dirs(tmp_path, 2, overwrite=False)


def test_build_metadata_shape() -> None:
    """Metadata is JSON-safe and marks failures. Without llm_started, duration is full runtime."""
    started = datetime(2026, 1, 1, tzinfo=UTC)
    ended = datetime(2026, 1, 1, 0, 0, 2, 500_000, tzinfo=UTC)

    metadata = build_metadata(3, "hermes", started, ended, 7)

    assert metadata == {
        "experiment_num": 3,
        "agent": "hermes",
        "started_at": "2026-01-01T00:00:00+00:00",
        "llm_started_at": None,
        "ended_at": "2026-01-01T00:00:02.500000+00:00",
        "warmup_seconds": None,
        "duration_seconds": 2.5,
        "exit_code": 7,
        "status": "failed",
    }
    json.dumps(metadata)


def test_build_metadata_with_warmup() -> None:
    """When llm_started is set, duration excludes warmup and warmup_seconds is populated."""
    started = datetime(2026, 1, 1, tzinfo=UTC)
    llm_started = datetime(2026, 1, 1, 0, 0, 1, tzinfo=UTC)  # 1s warmup
    ended = datetime(2026, 1, 1, 0, 0, 5, tzinfo=UTC)  # 4s runtime after warmup

    metadata = build_metadata(1, "opencode", started, ended, 0, llm_started)

    assert metadata["warmup_seconds"] == 1.0
    assert metadata["duration_seconds"] == 4.0
    assert metadata["llm_started_at"] == "2026-01-01T00:00:01+00:00"


def test_read_timeout_seconds_from_env_file(tmp_path: Path) -> None:
    """Runner timeout defaults from experiment .env."""
    env_file = tmp_path / ".env"
    env_file.write_text("# comment\nEXPERIMENT_TIMEOUT_SECONDS=12\n")

    assert read_timeout_seconds(env_file) == 12


def test_read_hermes_poll_timeout_from_env_file(tmp_path: Path) -> None:
    """Hermes process-poll timeout is separately configurable."""
    env_file = tmp_path / ".env"
    env_file.write_text("EXPERIMENT_HERMES_PROCESS_POLL_TIMEOUT_SECONDS=7\n")

    assert read_hermes_process_poll_timeout_seconds(env_file) == 7


def test_hermes_process_poll_detection() -> None:
    """Known Hermes background-process poll hangs are detectable."""
    line = 'Tool call: process with args: {"action":"poll","session_id":"x"}'

    assert _hermes_process_poll_started(line)
    assert _hermes_process_poll_completed("tool process completed (0.1s)")
    assert _hermes_poll_timed_out(10.0, 5, 15.1)
    assert not _hermes_poll_timed_out(10.0, 0, 99.0)


def test_sanitize_workdir_removes_harness_artifacts(tmp_path: Path) -> None:
    """Harness identity artifacts are removed before judging."""
    (tmp_path / "report.md").write_text("real output")
    (tmp_path / "AGENTS.md").write_text("openclaw identity")
    (tmp_path / ".openclaw").mkdir()
    (tmp_path / ".openclaw" / "session.jsonl").write_text("secret")
    (tmp_path / ".tinycua_context_cache").mkdir()

    sanitize_workdir("openclaw", tmp_path)
    sanitize_workdir("tinycua", tmp_path)

    assert (tmp_path / "report.md").exists()
    assert not (tmp_path / "AGENTS.md").exists()
    assert not (tmp_path / ".openclaw").exists()
    assert not (tmp_path / ".tinycua_context_cache").exists()


def test_build_permission_repair_command_uses_host_ids(tmp_path: Path) -> None:
    """Permission repair runs as root in a helper container but restores host IDs."""
    command = build_permission_repair_command(tmp_path, uid=1000, gid=1001)

    assert command[:5] == [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{tmp_path.resolve()}:/result",
    ]
    assert "chown -R 1000:1001 /result" in command[-1]
    assert "chmod -R u+rwX,go+rX /result" in command[-1]


# --- _format_stream_line ---


def test_format_passes_through_non_json() -> None:
    """Human-readable output (hermes/openclaw/tinycua) passes through unchanged."""
    assert _format_stream_line("Hello, world!\n") == "Hello, world!\n"


def test_format_text_event() -> None:
    """opencode text events show the response text."""
    line = json.dumps({"type": "text", "part": {"text": "Hello!"}})
    assert _format_stream_line(line) == "  | Hello!\n"


def test_format_reasoning_event_truncates() -> None:
    """Reasoning events collapse to one line, max 120 chars."""
    long_text = "x" * 200
    line = json.dumps({"type": "reasoning", "part": {"text": long_text}})
    result = _format_stream_line(line)
    assert result.startswith("  ~ ")
    assert len(result) < 130  # 120 chars + prefix + newline


def test_format_step_events() -> None:
    """step_start/step_finish show minimal markers."""
    assert (
        _format_stream_line(json.dumps({"type": "step_start", "part": {}}))
        == "  > step\n"
    )
    assert (
        _format_stream_line(json.dumps({"type": "step_finish", "part": {}}))
        == "  < step done\n"
    )


def test_format_unknown_event_shows_label() -> None:
    """Unknown JSON events (e.g. tool_call) show a type label, not raw JSON."""
    line = json.dumps({"type": "tool_call", "part": {"name": "write_file"}})
    assert _format_stream_line(line) == "  . write_file\n"


def test_format_non_object_json_passes_through() -> None:
    """A valid-but-non-object JSON line (bare string/number/list) is passed
    through instead of crashing with AttributeError on event.get()."""
    assert _format_stream_line('"just a string"\n') == '"just a string"\n'
    assert _format_stream_line("42\n") == "42\n"
    assert _format_stream_line("[1, 2, 3]\n") == "[1, 2, 3]\n"
