"""LLM-judge recovery stage for the unbounded retry loop.

Extracted from ``validation_retry_mixin.py`` to keep that file under the
1500 LOC hard acceptance gate. All methods are ``self.``-bound and resolved
at runtime via MRO — the mixin is composed into ``TinyCUALoop``.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from tinycua.config.types import LLMResult, ValidationResult
from tinycua.loops.context_rendering import sanitize_internal_reprs

if TYPE_CHECKING:
    from tinycua.loops.node import Node
    from tinycua_sdk.agent.agent import Agent
    from tinycua_sdk.tools.decorators import Tool

logger = logging.getLogger(__name__)


class RecoveryStagesMixin:
    """Mixin providing recovery message building + LLM-judge stage for the retry loop."""

    def _build_recovery_messages(
        self,
        node: Node,
        recovery_tools: list[Tool],
        last_result: LLMResult,
        validation: ValidationResult,
        missing_tools: list[str] | None,
    ) -> list[dict[str, Any]]:
        """Build the recovery retry message list (FR-066 goal-oriented)."""
        from datetime import datetime

        system_msg = node.build_system_message(recovery_tools)
        recovery_messages: list[dict[str, Any]] = []
        if system_msg.get("content"):
            recovery_messages.append(system_msg)
        now = datetime.now().astimezone()
        recovery_messages.append(
            {"role": "user", "content": f"<context>Current time: {now:%H:%M:%S %z}, timezone: {now.tzname() or 'local'}</context>"}
        )
        last_content = (last_result.content or "").strip()
        tool_call_summary = ""
        if last_result.tool_calls:
            names = [tc.get("function", {}).get("name", "?") for tc in last_result.tool_calls if isinstance(tc, dict)]
            tool_call_summary = f" (called: {', '.join(names)})"
        recovery_messages.append({"role": "assistant", "content": f"[My last response]{tool_call_summary}: {last_content}"})
        # FR-060: trimmed one-line summaries of previous tool results so the
        # model knows what its commands returned without re-running them.
        tool_results = last_result.metadata.get("tool_results", []) if isinstance(last_result.metadata, dict) else []
        if tool_results:
            from tinycua.loops.node_guidance import summarize_tool_result

            summary_lines = []
            for item in tool_results[-10:]:
                if not isinstance(item, dict):
                    continue
                name = item.get("name", "?")
                content_str = str(item.get("content", "") or item.get("output", ""))
                summary = summarize_tool_result(content_str)
                summary_lines.append(f"  - {name}: {summary}")
            if summary_lines:
                recovery_messages.append(
                    {"role": "user", "content": "Previous tool results (trimmed — do not re-run these):\n" + "\n".join(summary_lines)},
                )
        missing_str = ", ".join(missing_tools) if missing_tools else "the required tools"
        node_continuation = node.build_continuation(node.session) if node.session else ""
        # FR-066: goal-oriented recovery directive — goal + progress +
        # why-missing + recent attempts + directive.
        contract = node.contract
        directive_parts: list[str] = []
        if contract and contract.goal:
            directive_parts.append(f"## Node Goal\n{contract.goal}")
        progress_block = node.build_progress_block()
        if progress_block:
            directive_parts.append(progress_block)
        first_missing = missing_tools[0] if missing_tools else ""
        if contract and first_missing and contract.tool_rationale.get(first_missing):
            directive_parts.append(
                f"## Why {first_missing} Is Required\n{contract.tool_rationale[first_missing]}"
            )
        history = node.progress.stage_tool_history
        if history:
            hist_lines = ["## Recent Recovery Attempts"]
            for entry in history[-5:]:
                tools = ", ".join(entry.get("successful_tools") or entry.get("tools", []))
                if tools:
                    new = ", ".join(entry.get("new_tools", [])) or "(no new tools)"
                    summary = entry.get("result_summary", "")[:120]
                    hist_lines.append(f"- {entry['stage']}: called {tools} → {new}. {summary}")
                else:
                    hist_lines.append(f"- {entry['stage']}: failed to produce a valid call")
            hist_lines.append(
                "\nYou already called these tools. Do NOT repeat them. Call the next missing tool."
            )
            directive_parts.append("\n".join(hist_lines))
        directive_parts.append(
            f"Call {missing_str} now — do not repeat what you already did.\n\n{node_continuation}"
        )
        recovery_messages.append(
            {"role": "user", "content": "\n\n".join(directive_parts)}
        )
        return recovery_messages

    async def _judge_retry(
        self,
        node: Node,
        agent: Agent,
        resolved_tools: list[Tool],
        last_result: LLMResult,
        validation: ValidationResult,
        *,
        missing_tools: list[str] | None = None,
    ) -> tuple[LLMResult, ValidationResult] | None:
        """Last-resort recovery: an LLM judge injects the first missing tool call.

        Re-enabled (FR-012 updated): the judge now sees the FULL session
        context — system prompt, continuation (task under review, outcome
        report, roadmap), and trimmed tool results — so it makes an
        INFORMED injection, not a blind guess. This is the absolute final
        retry stage before node re-entry; the model gets 15 structured +
        10 focused chances first. The judge produces the exact tool call,
        which we inject and execute.

        Returns (result, validation) if the injected call passes validation,
        otherwise None (caller logs state and loops back or signals re-entry).
        """
        # Determine the tool to inject: the first missing prerequisite.
        if missing_tools:
            tool_name = missing_tools[0]
            required_tool = self._resolve_recovery_tool(node, tool_name, resolved_tools)
        else:
            required_tool = self._required_tool_for_recovery(node, validation)
        if required_tool is None:
            return None  # no single tool can fix this — judge cannot help

        tool_name = getattr(required_tool, "name", "the required tool")
        errors = "; ".join(validation.errors)

        tool_schema = {
            "name": tool_name,
            "parameters": getattr(required_tool, "parameters", {}),
        }

        # FR-060: build full-context messages using _build_recovery_messages
        # (system prompt + continuation + trimmed tool results), then append
        # the judge directive. The judge now sees what task it's reviewing,
        # what the outcome report says, and what tool results were produced.
        judge_messages = self._build_recovery_messages(
            node, [required_tool], last_result, validation, missing_tools,
        )
        # Replace the last user message (the recovery directive) with the
        # judge directive — same context, different instruction.
        judge_messages[-1] = {
            "role": "user",
            "content": (
                f"The agent failed to call '{tool_name}' after multiple "
                f"retries. Validation error: {errors}\n\n"
                f"Using the session context and task state above, produce a "
                f"single tool call to '{tool_name}' that satisfies the "
                f"requirement. Tool schema:\n"
                f"{json.dumps(tool_schema, default=str)}\n\n"
                f"Output ONLY: {{\"name\": \"{tool_name}\", "
                f"\"arguments\": {{...}}}}"
            ),
        }
        try:
            raw_response = await self._call_agent_llm(
                agent,
                node,
                judge_messages,
                [],  # no tools — the judge produces text, not tool calls
            )
        except Exception:
            logger.debug("node=%s judge_retry llm_call failed", node.node_id, exc_info=True)
            return None

        judge_text = sanitize_internal_reprs(raw_response.get("content") or "")
        if not judge_text.strip():
            return None

        injected_tool_call = self._parse_judge_tool_call(judge_text, tool_name)
        if injected_tool_call is None:
            logger.debug("node=%s judge_retry could not parse judge output", node.node_id)
            return None  # judge didn't produce valid JSON — loop back

        all_tool_results: list[dict[str, Any]] = []
        try:
            tool_results = await self._execute_tool_calls(
                agent,
                [injected_tool_call],
                [required_tool],
            )
            if tool_results:
                all_tool_results.extend(tool_results)
        except Exception:
            logger.debug("node=%s judge_retry tool exec failed", node.node_id, exc_info=True)
            return None

        judge_result = LLMResult(
            content=f"[Judge-injected {tool_name} call]",
            role="assistant",
            tool_calls=[injected_tool_call],
            metadata={},
        )
        if all_tool_results:
            judge_result.metadata = dict(judge_result.metadata)
            judge_result.metadata["tool_results"] = list(all_tool_results)
        judge_validation = self._validate_node_result(node, judge_result)
        if judge_validation.is_valid:
            self._record_node_content_transcript(
                node,
                f"Judge retry succeeded — an LLM judge injected a {tool_name} "
                f"call after the model could not produce one.",
            )
            return judge_result, judge_validation
        # Return the partial result so the caller accumulates successful tool
        # calls and advances to the next missing prerequisite (FR-063).
        return judge_result, judge_validation

    @staticmethod
    def _parse_judge_tool_call(
        judge_text: str,
        expected_name: str,
    ) -> dict[str, Any] | None:
        """Parse the judge's JSON output into a provider-compatible tool-call dict.

        The judge outputs ``{"name": "...", "arguments": {...}}``. We extract
        that, validate the name matches, and return a provider-compatible
        tool-call dict. Returns None if the text is not valid JSON or the
        name doesn't match.
        """
        text = judge_text.strip()
        # Strip markdown code fences if present.
        if text.startswith("```"):
            text = text.split("\n", 1)[-1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
        # Find the first JSON object in the text.
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        try:
            parsed = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return None
        if not isinstance(parsed, dict):
            return None
        name = parsed.get("name")
        if name != expected_name:
            return None
        arguments = parsed.get("arguments", {})
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments) if arguments else {}
            except json.JSONDecodeError:
                arguments = {}
        if not isinstance(arguments, dict):
            arguments = {}
        return {
            "id": f"call_judge_{expected_name}",
            "type": "function",
            "function": {
                "name": expected_name,
                "arguments": json.dumps(arguments, default=str),
            },
        }


class RecoveryGuardMixin:
    """No-progress guard + stage outcome recording for the recovery loop (FR-063).

    Extracted from ``orchestration_mixin.py`` to keep that file under the
    1500 LOC gate. Composed into ``TinyCUALoop`` via MRO.
    """

    @staticmethod
    def _record_stage_outcome(
        node: Node,
        stage_name: str,
        recovery_result: tuple[LLMResult, ValidationResult],
        accumulated_before: set[str],
        accumulated_after: set[str],
    ) -> None:
        """Record what a recovery stage produced for guard rationale (FR-063).

        Logs the stage name, tools called, success, result summary, and which
        new tools were added to the accumulated set. The no-progress guard
        and recovery messages use this to show the model what it already did.
        """
        from tinycua.loops.node_guidance import summarize_tool_result

        llm_result, _ = recovery_result
        tool_results = llm_result.metadata.get("tool_results", []) if isinstance(
            llm_result.metadata, dict
        ) else []
        tools_called = [
            tr.get("name", "?") for tr in tool_results
            if isinstance(tr, dict)
        ]
        successful_tools = [
            tr.get("name", "?") for tr in tool_results
            if isinstance(tr, dict)
            and isinstance(tr.get("output"), dict)
            and tr["output"].get("success") is True
        ]
        summaries = []
        for tr in tool_results:
            if isinstance(tr, dict) and isinstance(tr.get("output"), dict) and tr["output"].get("success"):
                content_str = str(tr.get("content", "") or tr.get("output", ""))
                summaries.append(f"{tr.get('name', '?')}: {summarize_tool_result(content_str)[:120]}")
        new_tools = sorted(accumulated_after - accumulated_before)
        node.progress.stage_tool_history.append({
            "stage": stage_name,
            "tools": tools_called,
            "successful_tools": successful_tools,
            "result_summary": "; ".join(summaries)[:300],
            "new_tools": new_tools,
        })

    @staticmethod
    def _is_no_progress(
        accumulated_before: set[str],
        accumulated_results: dict[str, dict],
        node: Node,
    ) -> bool:
        """Check if a stage executed a tool but added no new successful tool.

        Only fires when the stage's tool call succeeded (accumulated grew with
        a successful tool) but accumulated_results didn't gain a NEW key —
        meaning the model re-called a tool it already called. Stage failures
        (LLM didn't produce a valid call) don't trigger the guard.
        """
        accumulated_after = set(accumulated_results.keys())
        if accumulated_after != accumulated_before:
            return False  # new tool was added — progress was made
        history = node.progress.stage_tool_history
        if history and history[-1].get("successful_tools"):
            logger.info(
                "node=%s no-progress guard: model re-called existing tool (%s), "
                "skipping to next recovery stage",
                node.node_id,
                history[-1].get("successful_tools"),
            )
            return True
        return False
