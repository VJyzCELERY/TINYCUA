"""Unit tests for batch experiment automation helpers."""

from pathlib import Path

import pytest

import run_batch_experiments
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
    archived_prompt = (
        archive_dir / "results" / "tinycua" / "experiment-1" / "logs" / "prompt.txt"
    )
    assert archived_prompt.exists()
    assert not (output_root / "tinycua" / "experiment-1").exists()
    assert (output_root / "tinycua" / "experiment-3").exists()


def test_run_uses_script_dir_as_cwd(monkeypatch) -> None:
    """Subprocesses do not inherit a stale/deleted shell cwd."""
    calls = []

    def fake_run(command, cwd):
        calls.append((command, cwd))

        class Result:
            returncode = 0

        return Result()

    monkeypatch.setattr(run_batch_experiments.subprocess, "run", fake_run)

    assert (
        run_batch_experiments._run(["uv", "run", "python", "judge.py"], dry_run=False)
        == 0
    )
    assert calls == [
        (["uv", "run", "python", "judge.py"], run_batch_experiments.SCRIPT_DIR)
    ]


def test_run_experiment_uses_uv(capsys) -> None:
    """Batch runner calls the project command through uv."""
    run_batch_experiments._run_experiment(
        1,
        "Hello",
        Path("results"),
        None,
        ("tinycua",),
        dry_run=True,
    )

    output = capsys.readouterr().out
    assert "$ uv run python run_experiment.py" in output
    assert "--agents tinycua" in output


def test_main_judges_and_archives_failed_runs(tmp_path: Path, monkeypatch) -> None:
    """Failed runs are still judged and archived."""
    manifest = tmp_path / "prompts.txt"
    manifest.write_text("Experiment_1: ok\nExperiment_2: fail\n")
    judged = []
    archived = []

    monkeypatch.setattr(run_batch_experiments, "_run_setup", lambda dry_run: 0)
    monkeypatch.setattr(
        run_batch_experiments,
        "_run_experiment",
        lambda num, prompt, output_root, timeout_seconds, agents, dry_run: 1
        if num == 2
        else 0,
    )
    monkeypatch.setattr(
        run_batch_experiments,
        "_run_judge",
        lambda num, output_root, agents, dry_run: judged.append(num) or 0,
    )
    monkeypatch.setattr(
        run_batch_experiments,
        "archive_results",
        lambda output_root, archive_root, experiments, manifest, agents: archived.extend(
            experiments
        )
        or tmp_path,
    )

    code = run_batch_experiments.main(["--manifest", str(manifest)])

    assert code == 1
    assert judged == [1, 2]
    assert archived == [(1, "ok"), (2, "fail")]
