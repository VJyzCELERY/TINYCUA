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
    """Mixin providing the LLM-judge recovery stage for the retry loop."""

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
        return None

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
