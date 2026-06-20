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
    ) -> tuple[LLMResult, ValidationResult] | None:
        """Tightest recovery: an LLM judge decides the tool call with no context.

        When the focused retry and tightening retry both fail, the model is
        stuck and cannot produce the required tool call on its own. This stage
        bypasses the stuck model: a separate LLM call sees only the validation
        error, the required tool name, and the model's last response — no node
        context, no tool history, no session state. The judge produces the
        exact tool call (name + arguments), which we inject directly and
        execute. The stuck model never gets to decide again.

        Returns (result, validation) if the injected call passes validation,
        otherwise None (caller logs state and loops back to stage 1).
        """
        required_tool = self._required_tool_for_recovery(node, validation)
        if required_tool is None:
            return None  # no single tool can fix this — judge cannot help

        tool_name = getattr(required_tool, "name", "the required tool")
        errors = "; ".join(validation.errors)
        last_content = (last_result.content or "").strip()[:2000]

        tool_schema = {
            "name": tool_name,
            "parameters": getattr(required_tool, "parameters", {}),
        }

        judge_messages: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": (
                    "You are a tool-call judge. An AI agent failed to call the "
                    "required tool. You must produce the exact tool call that "
                    "satisfies the requirement. Output ONLY a JSON object with "
                    "'name' and 'arguments' keys. No prose, no explanation."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Requirement that was not satisfied: {errors}\n\n"
                    f"The agent's last response was:\n{last_content}\n\n"
                    f"Produce a single tool call to '{tool_name}' that satisfies "
                    f"the requirement. Tool schema:\n"
                    f"{json.dumps(tool_schema, default=str)}\n\n"
                    f"Output ONLY: {{\"name\": \"{tool_name}\", "
                    f"\"arguments\": {{...}}}}"
                ),
            },
        ]
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