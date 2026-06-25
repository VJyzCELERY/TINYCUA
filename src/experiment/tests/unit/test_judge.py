"""Unit tests for judge script helpers (hermes-judge container mode)."""

import subprocess

from judge import (
    _copy_workdir,
    _container_path,
    _judge_container_running,
    build_judge_prompt,
    build_cross_judge_prompt,
    extract_hermes_verdict,
    parse_model_snapshot,
)


# --- extract_hermes_verdict ---


def test_extract_verdict_single_line_after_session_id() -> None:
    """Hermes quiet mode: session_id line then verdict on next line."""
    raw = "session_id: 20260623_172537_6b6643\nPONG"
    assert extract_hermes_verdict(raw) == "PONG"


def test_extract_verdict_multi_line_verdict() -> None:
    """Multi-line verdict text preserved after the session_id line."""
    raw = "session_id: abc123\n## Scores\n\n| Criterion | Score |\n|---|---|\n| Task | 5 |"
    assert extract_hermes_verdict(raw) == "## Scores\n\n| Criterion | Score |\n|---|---|\n| Task | 5 |"


def test_extract_verdict_no_session_id_returns_raw() -> None:
    """If there's no session_id line, return the stripped output."""
    assert extract_hermes_verdict("just a plain response") == "just a plain response"


def test_extract_verdict_empty_input() -> None:
    """Empty or whitespace-only input returns empty string."""
    assert extract_hermes_verdict("") == ""
    assert extract_hermes_verdict("   \n  \n") == ""


def test_extract_verdict_only_session_id_line() -> None:
    """A lone session_id line with no verdict yields empty string."""
    assert extract_hermes_verdict("session_id: 20260623_172537_6b6643") == ""


def test_extract_verdict_strips_surrounding_whitespace() -> None:
    """Leading/trailing whitespace around the verdict is stripped."""
    raw = "\n  session_id: abc\n  verdict body  \n"
    assert extract_hermes_verdict(raw) == "verdict body"


# --- parse_model_snapshot ---


def test_parse_model_snapshot_extracts_three_fields() -> None:
    """A standard `hermes config show` Model block yields model/provider/base_url."""
    sample = (
        "◆ Model\n"
        "  Model:        {'default': 'gpt-5.5', 'provider': 'openai-codex',"
        " 'base_url': 'https://chatgpt.com/backend-api/codex'}\n"
        "  Max turns:    30\n"
    )
    fields = parse_model_snapshot(sample)
    assert fields["judge_model"] == "gpt-5.5"
    assert fields["judge_provider"] == "openai-codex"
    assert fields["judge_base_url"] == "https://chatgpt.com/backend-api/codex"


def test_parse_model_snapshot_missing_block_returns_failed_marker() -> None:
    """No Model block → failed-marker dict."""
    fields = parse_model_snapshot("no model block here\njust other text")
    assert fields["judge_model"] == "(snapshot failed)"
    assert fields["judge_provider"] == "(snapshot failed)"
    assert fields["judge_base_url"] == "(snapshot failed)"


def test_parse_model_snapshot_malformed_literal_returns_failed_marker() -> None:
    """A Model block with a non-literal value → failed-marker dict."""
    fields = parse_model_snapshot("Model: {not a valid dict")
    assert fields["judge_model"] == "(snapshot failed)"


def test_parse_model_snapshot_empty_string_fields_yield_unset_marker() -> None:
    """Empty string values in the dict become '(unset)' not empty."""
    fields = parse_model_snapshot("Model: {'default': '', 'provider': '', 'base_url': ''}")
    assert fields["judge_model"] == "(unset)"
    assert fields["judge_provider"] == "(unset)"
    assert fields["judge_base_url"] == "(unset)"


# --- _judge_container_running ---


def test_judge_container_running_detects_up_state(monkeypatch) -> None:
    """A running judge container yields a row containing 'Up'."""
    fake_stdout = (
        "NAME                 IMAGE              COMMAND               SERVICE   STATUS\n"
        "experiment-judge-1   experiment-judge   \"tail -f /dev/null\"   judge     Up 7 minutes\n"
    )
    monkeypatch.setattr(
        subprocess, "run",
        lambda *a, **k: subprocess.CompletedProcess(args=a, returncode=0, stdout=fake_stdout, stderr=""),
    )
    assert _judge_container_running() is True


def test_judge_container_running_detects_stopped_state(monkeypatch) -> None:
    """A stopped/absent container has no 'Up' row in `docker compose ps`."""
    # `docker compose ps judge` prints just the header when the container is gone,
    # or a row with a non-Up status when stopped.
    for fake_stdout in (
        "NAME                 IMAGE              COMMAND               SERVICE   STATUS\n",
        "NAME                 IMAGE              COMMAND               SERVICE   STATUS\n"
        "experiment-judge-1   experiment-judge   \"tail -f /dev/null\"   judge     Exited (0)\n",
    ):
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **k: subprocess.CompletedProcess(args=a, returncode=0, stdout=fake_stdout, stderr=""),
        )
        assert _judge_container_running() is False, fake_stdout


def test_judge_container_running_nonzero_exit_is_false(monkeypatch) -> None:
    """A non-zero exit from `docker compose ps` (e.g. no compose file) → False."""
    monkeypatch.setattr(
        subprocess, "run",
        lambda *a, **k: subprocess.CompletedProcess(args=a, returncode=1, stdout="", stderr="no compose file"),
    )
    assert _judge_container_running() is False


def test_judge_container_running_subprocess_error_is_false(monkeypatch) -> None:
    """A subprocess/SubprocessError → False (don't crash the judge script)."""
    def raise_timeout(*a, **k):
        raise subprocess.TimeoutExpired(cmd=a, timeout=15)
    monkeypatch.setattr(subprocess, "run", raise_timeout)
    assert _judge_container_running() is False


# --- _container_path ---


def test_container_path_maps_under_experiment_dir() -> None:
    """Host paths under the experiment dir become /workspace/... paths."""
    from pathlib import Path

    from judge import EXPERIMENT_DIR

    host = EXPERIMENT_DIR / "tmp" / "judge-2" / "submission"
    assert _container_path(host) == "/workspace/tmp/judge-2/submission"


def test_container_path_outside_experiment_dir_falls_back_to_host() -> None:
    """Host paths outside the experiment dir fall back to the raw string."""
    from pathlib import Path

    # /tmp is definitely outside the experiment dir.
    assert _container_path(Path("/tmp/something")) == "/tmp/something"


# --- build_judge_prompt ---


def test_build_judge_prompt_includes_task_and_submission_path() -> None:
    """Prompt contains the task and the container submission path."""
    prompt = build_judge_prompt(
        "Make a clock", workdir_empty=False,
        submission_dir_container="/workspace/tmp/judge-2/submission",
    )
    assert "Make a clock" in prompt
    assert "/workspace/tmp/judge-2/submission" in prompt
    assert "Inspect the files" in prompt


def test_build_judge_prompt_empty_workdir_uses_stdout() -> None:
    """Empty workdir tells judge to read stdout.log."""
    prompt = build_judge_prompt(
        "Say hello", workdir_empty=True,
        submission_dir_container="/workspace/tmp/judge-2/submission",
    )
    assert "stdout.log" in prompt
    assert "conversational response" in prompt


def test_build_judge_prompt_does_not_inject_criteria() -> None:
    """The rubric lives in SOUL.md now — no `## Judging Criteria` in prompt."""
    prompt = build_judge_prompt(
        "task", workdir_empty=False,
        submission_dir_container="/workspace/tmp/judge-2/submission",
    )
    assert "## Judging Criteria" not in prompt


# --- build_cross_judge_prompt ---


def test_build_cross_judge_prompt_includes_submissions_and_format() -> None:
    """Cross-judge prompt lists submissions and the comparative format."""
    submissions = [
        ("A", "/workspace/tmp/judge-2/submission-A", False),
        ("B", "/workspace/tmp/judge-2/submission-B", True),
    ]
    prompt = build_cross_judge_prompt("Build a clock", submissions)
    assert "Build a clock" in prompt
    assert "Submission A" in prompt
    assert "Submission B" in prompt
    assert "/workspace/tmp/judge-2/submission-A" in prompt
    assert "stdout.log" in prompt  # B is empty → stdout.log path
    assert "## Ranking" in prompt
    assert "## Per-Submission Scores" in prompt


def test_build_cross_judge_prompt_does_not_inject_criteria() -> None:
    """No `## Judging Criteria` block — rubric is in SOUL.md."""
    submissions = [("A", "/workspace/tmp/judge-2/submission-A", False)]
    prompt = build_cross_judge_prompt("task", submissions)
    assert "## Judging Criteria" not in prompt


# --- _copy_workdir ---


def test_copy_workdir_skips_harness_artifacts(tmp_path) -> None:
    """Judge never sees harness identity/cache artifacts."""
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    dst.mkdir()
    (src / "report.md").write_text("real output")
    (src / "AGENTS.md").write_text("harness identity")
    (src / ".openclaw").mkdir()
    (src / ".tinycua_context_cache").mkdir()

    assert _copy_workdir(src, dst)

    assert (dst / "report.md").exists()
    assert not (dst / "AGENTS.md").exists()
    assert not (dst / ".openclaw").exists()
    assert not (dst / ".tinycua_context_cache").exists()


def test_copy_workdir_returns_false_when_only_harness_artifacts(tmp_path) -> None:
    """Artifact-only workdirs are treated as empty so stdout can be judged."""
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    dst.mkdir()
    (src / "AGENTS.md").write_text("harness identity")

    assert not _copy_workdir(src, dst)
    assert not any(dst.iterdir())