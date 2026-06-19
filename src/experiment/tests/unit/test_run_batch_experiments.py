"""Unit tests for batch experiment automation helpers."""

from pathlib import Path

import pytest

from run_batch_experiments import archive_results, load_experiments


def test_load_experiments_parses_prompt_list(tmp_path: Path) -> None:
    """Manifest lines map experiment numbers to prompts."""
    manifest = tmp_path / "prompts.txt"
    manifest.write_text(
        "# smoke batch\n"
        "Experiment_1: Hello there\n"
        "Experiment_2: Make a clock: with animation\n"
    )

    assert load_experiments(manifest) == [
        (1, "Hello there"),
        (2, "Make a clock: with animation"),
    ]


def test_load_experiments_rejects_empty_manifest(tmp_path: Path) -> None:
    """No prompts means no batch."""
    manifest = tmp_path / "prompts.txt"
    manifest.write_text("# nothing\n")

    with pytest.raises(ValueError, match="no experiments"):
        load_experiments(manifest)


def test_archive_results_moves_only_requested_experiments(tmp_path: Path) -> None:
    """Archiving cleans active results for selected experiment numbers only."""
    output_root = tmp_path / "results"
    archive_root = tmp_path / "archives"
    manifest = tmp_path / "prompts.txt"
    manifest.write_text("Experiment_1: A\nExperiment_2: B\n")
    wanted = output_root / "tinycua" / "experiment-1" / "logs"
    wanted.mkdir(parents=True)
    (wanted / "prompt.txt").write_text("A")
    other = output_root / "tinycua" / "experiment-3" / "logs"
    other.mkdir(parents=True)

    archive_dir = archive_results(
        output_root,
        archive_root,
        [(1, "A"), (2, "B")],
        manifest,
        archive_name="batch",
    )

    assert (archive_dir / "manifest.txt").read_text() == manifest.read_text()
    assert (archive_dir / "results" / "tinycua" / "experiment-1" / "logs" / "prompt.txt").exists()
    assert not (output_root / "tinycua" / "experiment-1").exists()
    assert (output_root / "tinycua" / "experiment-3").exists()
