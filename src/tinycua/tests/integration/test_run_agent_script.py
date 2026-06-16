"""Contracts for scripts/run_agent.py notebook replacement."""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[2]
SCRIPT_PATH = PROJECT_DIR / "scripts" / "run_agent.py"


def _load_script_module():
    """Load run_agent.py without executing its main guard."""
    spec = importlib.util.spec_from_file_location("run_agent_script", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_run_agent_script_accepts_requested_invocation_shape(tmp_path: Path) -> None:
    """The script supports --stream, --dir, and --prompt."""
    module = _load_script_module()

    args = module.parse_args(
        [
            "--stream",
            "--dir",
            str(tmp_path),
            "--prompt",
            "Say hello",
        ]
    )

    assert args.stream is True
    assert args.dir == tmp_path
    assert args.prompt == "Say hello"


def test_build_language_model_from_loaded_config() -> None:
    """Script/CLI config is converted to SDK LanguageModel kwargs."""
    from tinycua.cli.config import build_language_model

    model = build_language_model(
        {
            "base_url": "http://localhost:1234/v1",
            "api_key": "test-key",
            "model": "test-model",
        }
    )

    assert model.provider == "openai-chat-completions"
    assert model.base_url == "http://localhost:1234/v1"
    assert model.model_name == "test-model"
    assert model.api_key.get_secret_value() == "test-key"


def test_stream_event_printer_shows_raw_tokens_and_tool_calls(capsys) -> None:
    """Stream mode prints raw token text plus concise tool activity only."""
    module = _load_script_module()
    printer = module._LiveStreamPrinter()

    module._print_stream_event(
        {"type": "node.started", "node_id": "task_executor"},
        printer,
    )
    module._print_stream_event(
        {
            "type": "response.reasoning.delta",
            "node_id": "task_executor",
            "delta": "thinking aloud",
        },
        printer,
    )
    module._print_stream_event(
        {
            "type": "tool_call.ready",
            "node_id": "task_executor",
            "name": "write_file",
            "arguments": '{"path":"app.py"}',
        },
        printer,
    )
    module._print_stream_event(
        {"type": "response.output_text.delta", "node_id": "response", "delta": "ok"},
        printer,
    )

    output = capsys.readouterr().out
    assert "tool-call" in output
    assert "write_file" in output
    assert "thinking aloud" in output
    assert "ok" in output
    assert "node.started" not in output
    assert "response.reasoning.delta" not in output
    assert "response.output_text.delta" not in output
    assert '"arguments"' not in output


def test_stream_event_printer_summarizes_json_tool_protocol(capsys) -> None:
    """JSON tool protocol text is shown as a tool call, not raw JSON tokens."""
    module = _load_script_module()

    module._print_stream_event(
        {
            "type": "response.output_text.delta",
            "node_id": "query_analyst",
            "delta": '{"tool_calls":[{"name":"select_query_route","arguments":{}}]}',
        }
    )

    output = capsys.readouterr().out
    assert "[tool-call]" in output
    assert "select_query_route" in output
    assert "tool_calls" not in output


def test_stream_event_printer_buffers_chunked_json_tool_protocol(capsys) -> None:
    """Chunked JSON tool protocol is not printed as visible token text."""
    module = _load_script_module()
    printer = module._LiveStreamPrinter()

    for delta in [
        '{"tool_calls"',
        ':[{"name":"select_query_route",',
        '"arguments":{"route":"worker"}}]}',
    ]:
        module._print_stream_event(
            {
                "type": "response.output_text.delta",
                "node_id": "query_analyst",
                "delta": delta,
            },
            printer,
        )

    output = capsys.readouterr().out
    assert "[tool-call]" in output
    assert "select_query_route" in output
    assert "tool_calls" not in output
    assert "arguments" not in output


def test_stream_event_printer_prints_chunked_output_text(capsys) -> None:
    """Normal output text deltas are printed as raw generated text."""
    module = _load_script_module()
    printer = module._LiveStreamPrinter()

    for delta in ["hel", "lo", " world"]:
        module._print_stream_event(
            {
                "type": "response.output_text.delta",
                "node_id": "response",
                "delta": delta,
            },
            printer,
        )

    output = capsys.readouterr().out
    assert "hello world" in output
    assert "response.output_text.delta" not in output


def test_transcript_event_printer_shows_tool_results(capsys) -> None:
    """Tool-result transcript events are printed during stream mode."""
    module = _load_script_module()

    class LoopStub:
        def get_transcript_events(self):
            return [
                {
                    "type": "transcript.tool_result",
                    "node_label": "TaskExecutor",
                    "tool_name": "write_file",
                    "content": (
                        '{"name":"write_file","allowed":true,'
                        '"output":{"success":true,"path":"app.py"}}'
                    ),
                }
            ]

    seen = module._print_new_transcript_events(LoopStub(), 0)

    output = capsys.readouterr().out
    assert seen == 1
    assert "tool-result" in output
    assert "TaskExecutor" in output
    assert "write_file" in output
    assert "path=app.py" in output
    assert '"output"' not in output


def test_summary_does_not_dump_raw_trace_or_transcript_json(
    capsys,
    tmp_path: Path,
) -> None:
    """Console summary points to artifacts instead of dumping raw JSON payloads."""
    module = _load_script_module()

    class LoopStub:
        def get_state_snapshot(self):
            return {"task_tree_text": "No tasks."}

        def get_execution_trace(self):
            return [
                {
                    "node_id": "response",
                    "node_type": "ResponseNode",
                    "route_label": "terminal",
                    "is_terminal": True,
                    "llm_content": '{"tool_calls":[{"name":"write_file"}]}',
                    "tool_calls": [{"name": "write_file", "arguments": {}}],
                    "tool_results": [{"output": {"success": True}}],
                }
            ]

        def get_transcript_text(self, *, include_node_calls: bool):
            return '[Response] LLM input {"messages": []}'

    module._print_summary(LoopStub(), tmp_path, tmp_path / ".tinycua-artifacts", "Done")

    output = capsys.readouterr().out
    assert "Done" in output
    assert "Full trace/transcript JSON saved under" in output
    assert "tool_calls" not in output
    assert "LLM input" not in output


def test_run_agent_script_help_mentions_requested_command() -> None:
    """The script can be invoked directly by uv run python."""
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--help"],
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "--stream" in result.stdout
    assert "--dir" in result.stdout
    assert "--prompt" in result.stdout


def test_env_example_contains_script_required_values() -> None:
    """The env example documents the model settings needed by the script."""
    content = (PROJECT_DIR / ".env.example").read_text(encoding="utf-8")

    assert "uv run python ./scripts/run_agent.py --stream --dir" in content
    assert "TINYCUA_BASE_URL=" in content
    assert "TINYCUA_API_KEY=" in content
    assert "TINYCUA_MODEL=" in content
    assert "TINYCUA_WORKER_EFFORT=medium" in content


def test_run_agent_loads_project_env_by_default(monkeypatch) -> None:
    """Default env loading discovers src/tinycua/.env from any cwd."""
    module = _load_script_module()
    monkeypatch.chdir(PROJECT_DIR.parent)
    monkeypatch.delenv("TINYCUA_BASE_URL", raising=False)

    env_path = PROJECT_DIR / ".env"
    original = env_path.read_text(encoding="utf-8") if env_path.exists() else None
    env_path.write_text("TINYCUA_BASE_URL=http://project-env.test/v1\n", encoding="utf-8")
    try:
        module._load_env(Path(".env"))
        assert os.environ["TINYCUA_BASE_URL"] == "http://project-env.test/v1"
    finally:
        os.environ.pop("TINYCUA_BASE_URL", None)
        if original is None:
            env_path.unlink(missing_ok=True)
        else:
            env_path.write_text(original, encoding="utf-8")
