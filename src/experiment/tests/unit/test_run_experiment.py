"""Unit tests for experiment runner helpers."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from run_experiment import (
    AGENTS,
    build_metadata,
    load_prompt,
    prepare_result_dirs,
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
    """Every agent gets an isolated experiment directory."""
    paths = prepare_result_dirs(tmp_path, 2, overwrite=False)

    assert tuple(paths) == AGENTS
    for agent, path in paths.items():
        assert path == tmp_path / agent / "experiment-2"
        assert path.is_dir()


def test_prepare_result_dirs_requires_overwrite(tmp_path: Path) -> None:
    """Existing outputs are guarded by default."""
    existing = tmp_path / "tinycua" / "experiment-2"
    existing.mkdir(parents=True)

    with pytest.raises(FileExistsError):
        prepare_result_dirs(tmp_path, 2, overwrite=False)


def test_build_metadata_shape() -> None:
    """Metadata is JSON-safe and marks failures."""
    started = datetime(2026, 1, 1, tzinfo=UTC)
    ended = datetime(2026, 1, 1, 0, 0, 2, 500_000, tzinfo=UTC)

    metadata = build_metadata(3, "hermes", started, ended, 7)

    assert metadata == {
        "experiment_num": 3,
        "agent": "hermes",
        "started_at": "2026-01-01T00:00:00+00:00",
        "ended_at": "2026-01-01T00:00:02.500000+00:00",
        "duration_seconds": 2.5,
        "exit_code": 7,
        "status": "failed",
    }
    json.dumps(metadata)
