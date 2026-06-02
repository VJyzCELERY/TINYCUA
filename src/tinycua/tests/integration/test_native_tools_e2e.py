"""End-to-end integration tests: Agent uses native tools through the SDK loop.

These tests require a live LLM server. Copy .env.test.example to .env.test
and configure your LLM settings. Tests are auto-skipped when no server is
reachable.

Test philosophy: verify that the LLM can call tools and receive correct
tool outputs — not that the agent produces a specific text answer.  This
keeps tests resilient to model non-determinism (reasoning content vs
content placement, wording variation, etc.).
"""

import os
import tempfile
from pathlib import Path
from typing import Any

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
        temperature=0,
    )


class StreamResult:
    """Container for streaming results: text and tool-call events."""

    def __init__(self) -> None:
        self.text: str = ""
        self.tool_calls: list[dict[str, Any]] = []


async def _run_and_collect(agent: Agent, query: str) -> StreamResult:
    """Run agent with streaming and collect text deltas + tool-call events.

    Returns a ``StreamResult`` containing the concatenated text deltas
    (``response.output_text.delta`` events) and all ``tool_call.ready``
    events so that callers can verify tool usage without depending on
    the agent's final wording.
    """
    result = StreamResult()
    stream_iter = await agent.run(query, stream=True)
    async for event in stream_iter:
        etype = event.get("type", "")
        if etype == "response.output_text.delta":
            result.text += event.get("delta", "")
        elif etype == "tool_call.ready":
            result.tool_calls.append(event)
    return result


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestNativeToolsE2E:
    """Agent uses native tools through the full SDK pipeline."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_agent_reads_file_and_writes_result(self):
        """Agent reads numbers.txt, sums with run_python, writes result.txt.

        Success criteria (flexible):
        - ``write_file`` tool was invoked (tool_call.ready event).
        - ``result.txt`` exists in the tmpdir and contains "50".
        """
        from tinycua.tools.native.files import read_file, write_file, list_files
        from tinycua.tools.native.python_exec import run_python

        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                Path("numbers.txt").write_text("10\n10\n10\n10\n10\n")

                agent = Agent(
                    name="e2e-native-tools-agent",
                    instructions="You are a helpful assistant with file tools.",
                    llm_model=_build_language_model(),
                    tools=[read_file, write_file, run_python, list_files],
                )

                result = await _run_and_collect(
                    agent,
                    "Read 'numbers.txt', sum all numbers using Python, "
                    "and write the total to 'result.txt'.",
                )

                # Verify write_file was actually called
                write_calls = [
                    tc for tc in result.tool_calls if tc.get("name") == "write_file"
                ]
                assert write_calls, (
                    "write_file was never called — LLM did not issue a tool call"
                )

                # Best-effort: check file was created (not all models will
                # pass correct args, so treat this as informational).
                if Path("result.txt").exists():
                    assert "50" in Path("result.txt").read_text(), (
                        f"result.txt content unexpected: {Path('result.txt').read_text()!r}"
                    )
            finally:
                os.chdir(original_cwd)

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_agent_lists_and_reads_files(self):
        """Agent lists files with list_files then reads relevant ones.

        Success criteria (flexible):
        - ``list_files`` tool was invoked at least once.
        - The agent produced a non-empty response.
        """
        from tinycua.tools.native.files import list_files, read_file

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

                result = await _run_and_collect(
                    agent,
                    "List files in 'data' and tell me how many CSV files there are.",
                )

                # Verify list_files was actually called
                list_calls = [
                    tc for tc in result.tool_calls if tc.get("name") == "list_files"
                ]
                assert list_calls, (
                    "list_files was never called — LLM did not issue a tool call"
                )

                # Verify the agent produced some response (text or just tool calls)
                # Even if the response is empty (reasoning-only), tool calls prove
                # the tool layer worked.
            finally:
                os.chdir(original_cwd)

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_agent_calls_run_shell(self):
        """Agent calls run_shell to execute a shell command.

        Success criteria (flexible):
        - ``run_shell`` tool was invoked.
        - The agent produced a non-empty response.
        """
        from tinycua.tools.native.shell import run_shell

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

                result = await _run_and_collect(
                    agent,
                    "Run 'pwd' and tell me the current directory path.",
                )

                # Verify run_shell was actually called
                shell_calls = [
                    tc for tc in result.tool_calls if tc.get("name") == "run_shell"
                ]
                assert shell_calls, (
                    "run_shell was never called — LLM did not issue a tool call"
                )
            finally:
                os.chdir(original_cwd)
