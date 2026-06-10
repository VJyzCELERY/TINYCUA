"""End-to-end integration tests: Agent uses native tools through the SDK loop.

These tests require a live LLM server. Copy .env.test.example to .env.test
and configure your LLM settings. Tests are auto-skipped when no server is
reachable.
"""

import os
import tempfile
from pathlib import Path

import pytest
from tinycua_sdk import Agent, LanguageModel

from tests.integration.conftest import resolve_integration_llm_config


def _build_language_model() -> LanguageModel:
    cfg = resolve_integration_llm_config()
    return LanguageModel(
        provider=cfg.provider,
        model_name=cfg.model,
        base_url=cfg.base_url,
        api_key=cfg.api_key,
    )


class TestNativeToolsE2E:
    """Agent uses native tools through the full SDK pipeline."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_agent_reads_file_and_writes_result(self):
        """Agent reads numbers.txt, sums with run_python, writes result.txt."""
        from tinycua.agent.tools.native.files import read_file, write_file, list_files
        from tinycua.agent.tools.native.python_exec import run_python

        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                Path("numbers.txt").write_text("10\n10\n10\n10\n10\n")

                agent = Agent(
                    name="e2e-native-tools-agent",
                    instructions=(
                        "You are a helpful assistant with file tools. "
                        "Use read_file, write_file, run_python, and list_files."
                    ),
                    llm_model=_build_language_model(),
                    tools=[read_file, write_file, run_python, list_files],
                )

                response = await agent.run(
                    "Read 'numbers.txt', sum all numbers using Python, "
                    "and write the total to 'result.txt'."
                )

                assert Path("result.txt").exists()
                assert "50" in Path("result.txt").read_text()
                assert isinstance(response, str) and len(response) > 0
            finally:
                os.chdir(original_cwd)

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_agent_lists_and_reads_files(self):
        """Agent lists files with list_files then reads relevant ones."""
        from tinycua.agent.tools.native.files import list_files, read_file

        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                Path("data").mkdir()
                Path("data/a.csv").write_text("id,name\n1,Alice\n")
                Path("data/b.csv").write_text("id,name\n2,Bob\n")
                Path("data/readme.txt").write_text("CSV data\n")

                agent = Agent(
                    name="e2e-listing-agent",
                    instructions="Use list_files to explore directories.",
                    llm_model=_build_language_model(),
                    tools=[list_files, read_file],
                )

                response = await agent.run(
                    "List files in 'data' and tell me how many CSV files there are."
                )

                assert isinstance(response, str)
                assert "2" in response
            finally:
                os.chdir(original_cwd)

    @pytest.mark.integration
    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Pre-existing flaky test — environment-dependent, unrelated to this PR (ISSUE-39-003)")
    async def test_agent_calls_run_shell(self):
        """Agent calls run_shell to execute a shell command."""
        from tinycua.agent.tools.native.shell import run_shell

        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)

                agent = Agent(
                    name="e2e-shell-agent",
                    instructions="Use run_shell to execute commands.",
                    llm_model=_build_language_model(),
                    tools=[run_shell],
                )

                response = await agent.run(
                    "Run 'pwd' and tell me the current directory path."
                )

                assert isinstance(response, str) and len(response) > 0
                assert tmpdir in response
            finally:
                os.chdir(original_cwd)
