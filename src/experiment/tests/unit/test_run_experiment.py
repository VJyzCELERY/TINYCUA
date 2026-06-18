"""Unit tests for experiment runner helpers."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from run_experiment import (
    AGENTS,
    _format_stream_line,
    build_metadata,
    load_prompt,
    prepare_result_dirs,
    read_timeout_seconds,
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
    assert _format_stream_line(json.dumps({"type": "step_start", "part": {}})) == "  > step\n"
    assert _format_stream_line(json.dumps({"type": "step_finish", "part": {}})) == "  < step done\n"


def test_format_unknown_event_shows_label() -> None:
    """Unknown JSON events (e.g. tool_call) show a type label, not raw JSON."""
    line = json.dumps({"type": "tool_call", "part": {"name": "write_file"}})
    assert _format_stream_line(line) == "  . write_file\n"
