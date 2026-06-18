"""Unit tests for judge script helpers."""

import json

from judge import build_judge_prompt, extract_verdict_text, read_env


# --- read_env ---


def test_read_env_returns_default_when_no_file(tmp_path) -> None:
    """Missing .env returns the default."""
    assert read_env("JUDGE_MODEL", "fallback", env_file=tmp_path / ".env") == "fallback"


def test_read_env_reads_key(tmp_path) -> None:
    """Correct key is read from .env."""
    env_file = tmp_path / ".env"
    env_file.write_text("JUDGE_MODEL=openai/gpt-5.4\nJUDGE_VARIANT=high\n")
    assert read_env("JUDGE_MODEL", env_file=env_file) == "openai/gpt-5.4"
    assert read_env("JUDGE_VARIANT", env_file=env_file) == "high"


def test_read_env_skips_comments(tmp_path) -> None:
    """Commented and blank lines are ignored."""
    env_file = tmp_path / ".env"
    env_file.write_text("# comment\n\nJUDGE_MODEL=openai/gpt-5.4\n")
    assert read_env("JUDGE_MODEL", env_file=env_file) == "openai/gpt-5.4"


# --- extract_verdict_text ---


def test_extract_verdict_single_text() -> None:
    """A single text event is extracted."""
    raw = json.dumps({"type": "text", "part": {"text": "Hello!"}})
    assert extract_verdict_text(raw) == "Hello!"


def test_extract_verdict_multiple_texts_joined() -> None:
    """Multiple text events are joined with blank lines."""
    raw = (
        json.dumps({"type": "text", "part": {"text": "Part 1"}}) + "\n"
        + json.dumps({"type": "text", "part": {"text": "Part 2"}})
    )
    assert extract_verdict_text(raw) == "Part 1\n\nPart 2"


def test_extract_verdict_ignores_non_text() -> None:
    """Non-text events (reasoning, step_start, etc.) are skipped."""
    raw = (
        json.dumps({"type": "step_start", "part": {}}) + "\n"
        + json.dumps({"type": "reasoning", "part": {"text": "thinking..."}}) + "\n"
        + json.dumps({"type": "text", "part": {"text": "Verdict"}})
    )
    assert extract_verdict_text(raw) == "Verdict"


def test_extract_verdict_empty_input() -> None:
    """Empty or non-JSON input returns empty string."""
    assert extract_verdict_text("") == ""
    assert extract_verdict_text("not json") == ""


# --- build_judge_prompt ---


def test_build_judge_prompt_includes_task_and_criteria() -> None:
    """Prompt contains the task and criteria text."""
    prompt = build_judge_prompt("Make a clock", "## Criteria\n1. Quality", workdir_empty=False)
    assert "Make a clock" in prompt
    assert "## Criteria" in prompt
    assert "Inspect the files" in prompt


def test_build_judge_prompt_empty_workdir_uses_stdout() -> None:
    """Empty workdir tells judge to read stdout.log."""
    prompt = build_judge_prompt("Say hello", "criteria", workdir_empty=True)
    assert "stdout.log" in prompt
    assert "conversational response" in prompt
