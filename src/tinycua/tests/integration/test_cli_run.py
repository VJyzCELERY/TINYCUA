"""Integration tests for tinycua run CLI."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

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

    def test_run_defaults(self):
        """Given minimal args, defaults are applied correctly."""
        from tinycua.cli.run import parse_args

        args = parse_args(["test"])
        assert args.timeout == 600
        assert args.output_dir == Path("/tmp_workspace/results")
        assert args.workspace == Path("/tmp_workspace")
        assert args.model == "llama3"
        assert args.verbose is False

    def test_run_accepts_all_flags(self):
        """Given all flags, they are parsed correctly."""
        from tinycua.cli.run import parse_args

        args = parse_args([
            "--timeout", "30",
            "--output-dir", "./out",
            "--workspace", "/ws",
            "--base-url", "http://localhost:8080/v1",
            "--api-key", "sk-test",
            "--model", "llama-3-8b",
            "--verbose",
            "my task",
        ])
        assert args.prompt == "my task"
        assert args.timeout == 30
        assert args.output_dir == Path("./out")
        assert args.workspace == Path("/ws")
        assert args.base_url == "http://localhost:8080/v1"
        assert args.api_key == "sk-test"
        assert args.model == "llama-3-8b"
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
        }, clear=False):
            with pytest.raises(ValueError, match="api_key"):
                load_config(base_url=None, api_key=None, model=None)


class TestCLIRunExitCodes:
    """Verify exit codes for success, error, and timeout scenarios."""

    def test_exit_code_0_on_success(self):
        """Given a successful run, exit code is 0."""
        from tinycua.cli.run import run_command

        with patch("tinycua.cli.run.create_tinycua_agent") as mock_factory:
            mock_agent = AsyncMock()
            mock_agent.run = AsyncMock(return_value="done")
            mock_factory.return_value = mock_agent

            with patch("tinycua.cli.run.load_config", return_value={
                "base_url": "http://localhost:8080/v1",
                "api_key": "test",
                "model": "test-model",
            }):
                exit_code = run_command(
                    prompt="test task",
                    timeout=10,
                    output_dir=Path("./tmp_test_out"),
                    workspace=Path("./tmp_test_ws"),
                    base_url=None, api_key=None, model=None,
                    verbose=False,
                )
                assert exit_code == 0

    def test_exit_code_1_on_error(self):
        """Given an agent crash, exit code is 1."""
        from tinycua.cli.run import run_command

        with patch("tinycua.cli.run.create_tinycua_agent") as mock_factory:
            mock_factory.side_effect = RuntimeError("endpoint unreachable")

            with patch("tinycua.cli.run.load_config", return_value={
                "base_url": "http://localhost:8080/v1",
                "api_key": "test",
                "model": "test-model",
            }):
                exit_code = run_command(
                    prompt="test task",
                    timeout=10,
                    output_dir=Path("./tmp_test_out"),
                    workspace=Path("./tmp_test_ws"),
                    base_url=None, api_key=None, model=None,
                    verbose=False,
                )
                assert exit_code == 1

    def test_exit_code_124_on_timeout(self):
        """Given timeout exceeded, exit code is 124."""
        import asyncio
        from tinycua.cli.run import run_command

        async def slow_run(*args, **kwargs):
            await asyncio.sleep(100)
            return "never"

        with patch("tinycua.cli.run.create_tinycua_agent") as mock_factory:
            mock_agent = AsyncMock()
            mock_agent.run = slow_run
            mock_factory.return_value = mock_agent

            with patch("tinycua.cli.run.load_config", return_value={
                "base_url": "http://localhost:8080/v1",
                "api_key": "test",
                "model": "test-model",
            }):
                exit_code = run_command(
                    prompt="test task",
                    timeout=1,  # 1 second timeout
                    output_dir=Path("./tmp_test_out"),
                    workspace=Path("./tmp_test_ws"),
                    base_url=None, api_key=None, model=None,
                    verbose=False,
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
            assert "role" in record


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
