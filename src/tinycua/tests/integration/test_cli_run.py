"""Integration tests for tinycua run CLI."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestCLIRunArgumentParsing:
    """Verify all CLI flags and positional arguments are correctly parsed."""

    def test_run_requires_prompt(self):
        """Given no prompt, the CLI exits with usage error (code 2)."""
        result = subprocess.run(
            [sys.executable, "-m", "tinycua.cli.main", "run"],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0

    def test_run_accepts_prompt_positional(self):
        """Given a prompt as positional arg, the CLI accepts it."""
        from tinycua.cli.run import parse_args

        args = parse_args(["hello world"])
        assert args.prompt == "hello world"

    def test_run_accepts_prompt_option_and_dir(self, tmp_path):
        """Given --prompt and --dir, one-shot args are normalized."""
        from tinycua.cli.run import parse_args

        args = parse_args(["--dir", str(tmp_path), "--prompt", "hello world"])

        assert args.prompt == "hello world"
        assert args.dir == tmp_path

    def test_run_dir_defaults_to_cwd(self):
        """--dir defaults to the current working directory."""
        from tinycua.cli.run import parse_args

        args = parse_args(["build app"])
        assert args.dir == Path.cwd()

    def test_run_has_no_stream_flag(self, tmp_path):
        """Streaming is always on; --stream is no longer a flag."""
        from tinycua.cli.run import parse_args

        # parse_args must accept the core flags without --stream
        args = parse_args(["--dir", str(tmp_path), "build app"])
        assert not hasattr(args, "stream"), (
            "--stream was removed; streaming is the default behavior"
        )

    def test_run_worker_effort_default_medium(self, tmp_path):
        """--worker-effort defaults to medium (overridable from env)."""
        from tinycua.cli.run import parse_args

        args = parse_args(["--dir", str(tmp_path), "build app"])
        assert args.worker_effort == "medium"

    def test_run_worker_effort_from_env_takes_priority(self, monkeypatch, tmp_path):
        """TINYCUA_WORKER_EFFORT in env overrides the medium default."""
        from tinycua.cli.run import parse_args

        monkeypatch.setenv("TINYCUA_WORKER_EFFORT", "high")
        args = parse_args(["--dir", str(tmp_path), "build app"])
        assert args.worker_effort == "high"

    def test_run_accepts_provider_url_flag(self, tmp_path):
        """--provider-url is the primary name for the provider base URL."""
        from tinycua.cli.run import parse_args

        args = parse_args(
            ["--dir", str(tmp_path), "--provider-url", "http://x:1234/v1", "build app"]
        )
        assert args.provider_url == "http://x:1234/v1"
        # --base-url is kept as a hidden alias for backward compat.
        assert args.base_url == "http://x:1234/v1"

    def test_run_accepts_base_url_alias(self, tmp_path):
        """--base-url still works as an alias for --provider-url."""
        from tinycua.cli.run import parse_args

        args = parse_args(
            ["--dir", str(tmp_path), "--base-url", "http://x:1234/v1", "build app"]
        )
        assert args.provider_url == "http://x:1234/v1"

    def test_run_provider_type_defaults_to_chat_completions(self, tmp_path):
        """--provider-type defaults to openai-chat-completions."""
        from tinycua.cli.run import parse_args

        args = parse_args(["--dir", str(tmp_path), "build app"])
        assert args.provider_type == "openai-chat-completions"

    def test_run_provider_type_from_env_takes_priority(self, monkeypatch, tmp_path):
        """TINYCUA_PROVIDER_TYPE in env overrides the chat-completions default."""
        from tinycua.cli.run import parse_args

        monkeypatch.setenv("TINYCUA_PROVIDER_TYPE", "openai-responses")
        args = parse_args(["--dir", str(tmp_path), "build app"])
        assert args.provider_type == "openai-responses"

    def test_run_accepts_provider_type_flag(self, tmp_path):
        """--provider-type selects the SDK provider (responses vs chat-completions)."""
        from tinycua.cli.run import parse_args

        args = parse_args(
            ["--dir", str(tmp_path), "--provider-type", "openai-responses", "build app"]
        )
        assert args.provider_type == "openai-responses"

    def test_run_accepts_env_file(self, tmp_path):
        """--env specifies an env file path to load before resolving defaults."""
        from tinycua.cli.run import parse_args

        args = parse_args(["--dir", str(tmp_path), "--env", str(tmp_path / ".env"), "build app"])
        assert args.env_file == tmp_path / ".env"

    def test_run_defaults(self):
        """Given minimal args, defaults are applied correctly."""
        from tinycua.cli.run import parse_args

        args = parse_args(["test"])
        assert args.timeout == 600
        assert args.dir == Path.cwd()
        assert args.model is None  # resolved from env at run time
        assert args.provider_type == "openai-chat-completions"
        assert args.worker_effort == "medium"
        assert args.verbose is False

    def test_run_accepts_all_flags(self, tmp_path):
        """Given all flags, they are parsed correctly."""
        from tinycua.cli.run import parse_args

        args = parse_args([
            "--timeout", "30",
            "--dir", str(tmp_path),
            "--provider-url", "http://localhost:8080/v1",
            "--provider-type", "openai-responses",
            "--api-key", "sk-test",
            "--model", "llama-3-8b",
            "--worker-effort", "high",
            "--verbose",
            "my task",
        ])
        assert args.prompt == "my task"
        assert args.timeout == 30
        assert args.dir == tmp_path
        assert args.provider_url == "http://localhost:8080/v1"
        assert args.provider_type == "openai-responses"
        assert args.api_key == "sk-test"
        assert args.model == "llama-3-8b"
        assert args.worker_effort == "high"
        assert args.verbose is True


class TestCLIRunConfigLoading:
    """Verify environment variable and CLI config loading."""

    def test_config_from_env_vars(self):
        """Given env vars, config is loaded correctly."""
        from tinycua.cli.config import load_config

        with patch.dict("os.environ", {
            "TINYCUA_BASE_URL": "http://env-host:8080/v1",
            "TINYCUA_API_KEY": "env-key",
            "TINYCUA_MODEL": "env-model",
        }):
            config = load_config(base_url=None, api_key=None, model=None)
            assert config["base_url"] == "http://env-host:8080/v1"
            assert config["api_key"] == "env-key"
            assert config["model"] == "env-model"

    def test_cli_overrides_env_vars(self):
        """Given both env vars and CLI flags, CLI flags win."""
        from tinycua.cli.config import load_config

        with patch.dict("os.environ", {
            "TINYCUA_BASE_URL": "http://env-host:8080/v1",
            "TINYCUA_API_KEY": "env-key",
        }):
            config = load_config(
                base_url="http://cli-host:9090/v1",
                api_key="cli-key",
                model=None,
            )
            assert config["base_url"] == "http://cli-host:9090/v1"
            assert config["api_key"] == "cli-key"

    def test_missing_base_url_raises(self):
        """Given no base_url in env or CLI, raises ValueError."""
        from tinycua.cli.config import load_config

        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ValueError, match="base_url"):
                load_config(base_url=None, api_key=None, model=None)

    def test_missing_api_key_raises(self):
        """Given no api_key in env or CLI, raises ValueError."""
        from tinycua.cli.config import load_config

        with patch.dict("os.environ", {
            "TINYCUA_BASE_URL": "http://localhost:8080/v1",
        }, clear=True):
            with pytest.raises(ValueError, match="api_key"):
                load_config(base_url=None, api_key=None, model=None)


class TestCLIRunExitCodes:
    """Verify exit codes for success, error, and timeout scenarios."""

    def test_exit_code_0_on_success(self, tmp_path):
        """Given a successful run, exit code is 0 and artifacts are written."""
        from tinycua.cli.run import run_command

        mock_loop = MagicMock()
        mock_loop._working_messages = []
        mock_loop.get_usage_events = MagicMock(return_value=[])
        mock_loop.get_execution_trace = MagicMock(return_value=[])
        mock_loop.get_state_snapshot = MagicMock(
            return_value={
                "task_tree": {},
                "task_tree_text": "No tasks.",
                "transcript_text": "[USER] test task",
            }
        )
        mock_loop.get_final_response_events = MagicMock(return_value=[])
        mock_loop.get_transcript_events = MagicMock(return_value=[])

        mock_agent = MagicMock()
        mock_agent.loop = mock_loop

        mock_run_streaming = MagicMock(return_value="stream-coro")
        with patch("tinycua.cli.run.create_tinycua_agent", return_value=mock_agent), \
             patch("tinycua.cli.run.run_streaming", new=mock_run_streaming), \
             patch("tinycua.cli.run._run_async_safely", return_value="done"), \
             patch("tinycua.cli.run.load_config", return_value={
                 "base_url": "http://localhost:8080/v1",
                 "api_key": "test",
                 "model": "test-model",
                 "provider_type": "openai-chat-completions",
             }):
                exit_code = run_command(
                    prompt="test task",
                    dir=tmp_path,
                    provider_url=None,
                    provider_type=None,
                    api_key=None,
                    model=None,
                    worker_effort="medium",
                    timeout=10,
                    verbose=False,
                    env_file=None,
                )
                assert exit_code == 0
                artifact_dir = tmp_path / ".tinycua-artifacts"
                assert (artifact_dir / "execution_trace.json").exists()
                assert (artifact_dir / "state_snapshot.json").exists()
                assert (artifact_dir / "task_tree.json").exists()
                assert (artifact_dir / "task_tree.txt").exists()
                assert (artifact_dir / "transcript.txt").exists()
                assert (artifact_dir / "transcript_events.json").exists()
                assert (artifact_dir / "final_response_events.json").exists()

    def test_exit_code_1_on_error(self, tmp_path):
        """Given an agent crash, exit code is 1."""
        from tinycua.cli.run import run_command

        with patch("tinycua.cli.run.create_tinycua_agent") as mock_factory:
            mock_factory.side_effect = RuntimeError("endpoint unreachable")

            with patch("tinycua.cli.run.load_config", return_value={
                "base_url": "http://localhost:8080/v1",
                "api_key": "test",
                "model": "test-model",
                "provider_type": "openai-chat-completions",
            }):
                exit_code = run_command(
                    prompt="test task",
                    dir=tmp_path,
                    provider_url=None,
                    provider_type=None,
                    api_key=None,
                    model=None,
                    worker_effort="medium",
                    timeout=10,
                    verbose=False,
                    env_file=None,
                )
                assert exit_code == 1

    def test_exit_code_124_on_timeout(self, tmp_path):
        """Given timeout exceeded, exit code is 124."""
        import asyncio
        from tinycua.cli.run import run_command

        with patch("tinycua.cli.run.create_tinycua_agent") as mock_factory:
            mock_agent = MagicMock()
            mock_factory.return_value = mock_agent

            with patch("tinycua.cli.run.load_config", return_value={
                "base_url": "http://localhost:8080/v1",
                "api_key": "test",
                "model": "test-model",
                "provider_type": "openai-chat-completions",
            }):
                mock_run_streaming = MagicMock(return_value="stream-coro")
                with patch("tinycua.cli.run.run_streaming", new=mock_run_streaming), \
                     patch("tinycua.cli.run._run_async_safely", side_effect=asyncio.CancelledError):
                    exit_code = run_command(
                        prompt="test task",
                        dir=tmp_path,
                        provider_url=None,
                        provider_type=None,
                        api_key=None,
                        model=None,
                        worker_effort="medium",
                        timeout=1,  # 1 second timeout
                        verbose=False,
                        env_file=None,
                    )
                    assert exit_code == 124


class TestCLIRunTranscriptWriting:
    """Verify transcript JSONL file is produced."""

    def test_transcript_file_created(self, tmp_path):
        """Given a successful run, transcript.jsonl exists in output dir."""
        from tinycua.cli.transcript import write_transcript

        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Create hello.txt"},
            {"role": "assistant", "content": "I'll create that file."},
        ]
        write_transcript(messages, tmp_path / "transcript.jsonl")

        assert (tmp_path / "transcript.jsonl").exists()
        lines = (tmp_path / "transcript.jsonl").read_text().strip().split("\n")
        assert len(lines) == 3
        for line in lines:
            record = json.loads(line)
            assert record.get("type") == "message"
            assert "message" in record
            assert "role" in record["message"]


class TestCLIRunLogWriting:
    """Verify structured agent log is produced."""

    def test_log_file_created(self, tmp_path):
        """Given a run, agent.log exists in output dir."""
        from tinycua.cli.logging import write_log_entry

        write_log_entry(tmp_path / "agent.log", "start", "info", {"prompt": "test"})
        write_log_entry(tmp_path / "agent.log", "complete", "info", {"duration": 1.2})

        assert (tmp_path / "agent.log").exists()
        lines = (tmp_path / "agent.log").read_text().strip().split("\n")
        assert len(lines) == 2
        for line in lines:
            entry = json.loads(line)
            assert "timestamp" in entry
            assert "event" in entry
            assert "level" in entry


class TestCLIRunMainDispatch:
    """Verify main.py dispatches to run subcommand."""

    def test_main_without_subcommand_shows_help(self):
        """Given no subcommand, main shows help and exits."""
        result = subprocess.run(
            [sys.executable, "-m", "tinycua.cli.main"],
            capture_output=True,
            text=True,
        )
        # Should exit with 0 (help displayed) or show usage
        assert result.returncode == 0 or "usage" in result.stderr.lower() or "usage" in result.stdout.lower()

    def test_main_run_subcommand_dispatches(self):
        """Given 'run' subcommand, main dispatches to run_command."""
        result = subprocess.run(
            [sys.executable, "-m", "tinycua.cli.main", "run"],
            capture_output=True,
            text=True,
        )
        # Should fail because no prompt provided, but dispatch should work
        assert result.returncode != 0
