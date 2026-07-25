"""Markdown-synthesis retry ("lazy retry") mixin for TinyCUALoop (FR-087..FR-093).

Extracted from ``validation_retry_mixin.py`` to keep that file under the
1500 LOC hard acceptance gate. All methods are ``self.``-bound and resolved
at runtime via MRO — composed into ``TinyCUALoop`` alongside the other
loop mixins.

When a node's LLM response completes without emitting its required state
tool, lazy retry makes one no-tools non-streaming LLM continuation asking
the model to fill a small markdown template, then synthesizes the state
tool call from the parsed response.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any, AsyncIterator

from tinycua.config.types import LLMResult, ValidationResult
from tinycua.loops._loop_constants import _LAZY_BUDGET
from tinycua.loops.context_rendering import sanitize_internal_reprs
from tinycua.loops.lazy_templates import (
    LAZY_STATE_TOOLS,
    LAZY_TEMPLATES,
    parse_lazy_markdown,
)

if TYPE_CHECKING:
    from tinycua.loops.node import Node
    from tinycua_sdk.agent.agent import Agent
    from tinycua_sdk.tools.decorators import Tool

logger = logging.getLogger(__name__)


class LazyRetryMixin:
    """Mixin providing the markdown-synthesis retry path (FR-087..FR-093).

    Composed into ``TinyCUALoop`` via MRO. The gate, the lazy call, and the
    task_id resolver live here; the wire-in sites (in-loop retry, stream
    retry, pre-``_unbounded_recovery``) are in ``tinycua_loop.py`` and
    ``orchestration_mixin.py``.
    """

    def _lazy_gate_passes(
        self,
        node: Node,
        last_result: LLMResult,
        validation: ValidationResult,
    ) -> bool:
        """Return whether lazy retry should fire for this validation failure.

        Gate (FR-088): all must hold —
          1. session_config.recovery_strategy == "markdown_synthesis"
          2. node.node_id has a registered markdown template (v1: reviewer,
             executor, query_analyst, worker)
          3. _missing_recovery_tools_from_set returns a non-empty list AND at
             least one missing tool is a registered state tool (the others,
             e.g. terminate/task_inspect, are handled by standard recovery
             after lazy synthesizes the state tool)

        Generic tool-exec failures, empty-response, reviewer-report,
        route-arg, and "cannot approve failed task" errors skip lazy retry
        (those don't surface as missing-state-tool chains).
        """
        del last_result, validation  # gate is structural, not content-based
        cfg = getattr(self, "session_config", None)
        if (
            cfg is None
            or getattr(cfg, "recovery_strategy", "standard") != "markdown_synthesis"
        ):
            return False
        if node.node_id not in LAZY_TEMPLATES:
            return False
        accumulated_successful = set(node.progress.accumulated_tool_results.keys())
        accumulated_successful |= node.progress.satisfied_requirements
        missing = self._missing_recovery_tools_from_set(node, accumulated_successful)
        if not missing:
            return False
        return any(name in LAZY_STATE_TOOLS for name in missing)

    async def _maybe_lazy_recovery(
        self,
        node: Node,
        agent: Agent,
        resolved_tools: list[Tool],
        last_result: LLMResult,
        validation: ValidationResult,
    ) -> tuple[LLMResult, ValidationResult] | None:
        """One no-tools markdown continuation to synthesize a missing state tool.

        Returns (result, validation) on a ran call (partial result even when
        validation still fails — so the caller accumulates successful tool
        calls). Returns None on parse failure / unresolvable task_id / exec
        error / gate-fail (caller falls back to standard retry, FR-090/091).
        """
        if not self._lazy_gate_passes(node, last_result, validation):
            return None
        target_tool_name, template = LAZY_TEMPLATES[node.node_id]
        accumulated_successful = set(node.progress.accumulated_tool_results.keys())
        missing = self._missing_recovery_tools_from_set(node, accumulated_successful)
        # Only synthesize if the registered target tool is actually missing;
        # the chain may include terminate/task_inspect which standard recovery
        # handles after lazy synthesizes the state tool.
        if target_tool_name not in missing:
            return None
        # Build full-context messages, then swap the last user message with the
        # markdown synthesis instruction (FR-089).
        lazy_messages = self._build_recovery_messages(
            node,
            [],
            last_result,
            validation,
            missing,
        )
        # Fill the {labels} placeholder for route templates.
        instruction_template = template
        if "{labels}" in instruction_template:
            labels = list(getattr(node, "classification_labels", []))
            instruction_template = instruction_template.replace(
                "{labels}",
                " | ".join(labels) if labels else "<route>",
            )
        instruction = (
            "Summarize what you have done in this session, then write it using "
            "exactly this format (fill in the bracketed sections, do not add any "
            f"other text outside the template):\n\n{instruction_template}"
        )
        if lazy_messages:
            lazy_messages[-1] = {"role": "user", "content": instruction}
        else:
            lazy_messages = [{"role": "user", "content": instruction}]
        # One non-streaming LLM continuation with no tools exposed.
        try:
            raw_response = await self._call_agent_llm(
                agent,
                node,
                lazy_messages,
                [],
                stream=False,
                force_required_tool=False,
            )
        except Exception:
            logger.debug(
                "node=%s lazy_retry llm_call failed", node.node_id, exc_info=True
            )
            return None
        content = sanitize_internal_reprs(raw_response.get("content") or "")
        if not content.strip():
            return None
        # Parse the markdown response (FR-090).
        allowed_labels = set(getattr(node, "classification_labels", [])) or None
        parsed = parse_lazy_markdown(
            node.node_id, content, allowed_labels=allowed_labels
        )
        if not parsed:
            logger.debug("node=%s lazy_retry could not parse markdown", node.node_id)
            return None
        # Resolve task_id for task-state tools (UUID → roadmap number → active).
        if "task_id" in parsed:
            resolved_id = self._resolve_lazy_task_id(
                parsed["task_id"], node, last_result
            )
            if resolved_id is None:
                logger.debug(
                    "node=%s lazy_retry unresolvable task_id=%s",
                    node.node_id,
                    parsed["task_id"],
                )
                return None
            parsed["task_id"] = resolved_id
        # Resolve the target Tool object and bind its session state.
        required_tool = self._resolve_recovery_tool(
            node, target_tool_name, resolved_tools
        )
        if required_tool is None:
            return None
        # Session-bound task tools need their store wired before execution —
        # _resolve_recovery_tool may construct a fresh, unbound instance.
        self._bind_session_tools([required_tool], node)
        # Synthesize the provider-compatible tool call dict.
        arguments = json.dumps(parsed, default=str)
        synthesized = {
            "id": f"call_lazy_{target_tool_name}",
            "type": "function",
            "function": {
                "name": target_tool_name,
                "arguments": arguments,
            },
        }
        # Execute the synthesized tool call.
        try:
            tool_results = await self._execute_tool_calls(
                agent,
                [synthesized],
                [required_tool],
            )
        except Exception:
            logger.debug(
                "node=%s lazy_retry tool exec failed", node.node_id, exc_info=True
            )
            return None
        result = LLMResult(
            content=f"[Lazy-synthesized {target_tool_name} call]",
            role="assistant",
            tool_calls=[synthesized],
            metadata={},
        )
        if tool_results:
            result.metadata = dict(result.metadata)
            result.metadata["tool_results"] = list(tool_results)
        self._record_node_content_transcript(
            node,
            f"Lazy retry synthesized a {target_tool_name} call from a "
            f"markdown continuation after the model failed to emit the state tool.",
        )
        return result, self._validate_node_result(node, result)

    async def _handle_retry_attempt(
        self,
        node: Node,
        agent: Agent,
        resolved_tools: list[Tool],
        last_result: LLMResult,
        last_validation: ValidationResult,
        attempt: int,
        lazy_attempts: int,
    ) -> tuple[str, LLMResult, ValidationResult, int] | None:
        """Handle one retry attempt: lazy first, then signal the caller.

        Returns (action, result, validation, lazy_attempts) where action is
        "return" (valid → caller returns), "break" (terminate missing → caller
        breaks to _unbounded_recovery), or None (lazy didn't fire → caller does
        standard retry). The caller owns the standard retry path.
        """
        outcome = await self._maybe_lazy_in_stream_loop(
            node, agent, resolved_tools, last_result, last_validation, lazy_attempts
        )
        if outcome is None:
            return None
        lazy_result, revalidated, new_attempts = outcome
        action = "return" if revalidated.is_valid else "break"
        return action, lazy_result, revalidated, new_attempts

    async def _maybe_lazy_pre_recovery(
        self,
        node: Node,
        agent: Agent,
        resolved_tools: list[Tool],
        llm_result: LLMResult,
        validation: ValidationResult,
    ) -> tuple[LLMResult, ValidationResult, bool] | None:
        """Lazy retry before _unbounded_recovery (sync path, FR-087..FR-093).

        Returns (lazy_result, revalidated, True) when lazy synthesized the
        state tool and the result is valid — caller finalizes the node.
        Returns (lazy_result, revalidated, False) when lazy ran but
        validation still fails (terminate missing) — caller passes
        (lazy_result, revalidated) to _unbounded_recovery.
        Returns None when the gate fails or lazy returned None — caller
        runs _unbounded_recovery with the original (llm_result, validation).
        """
        if not self._lazy_gate_passes(node, llm_result, validation):
            return None
        lazy = await self._maybe_lazy_recovery(
            node,
            agent,
            resolved_tools,
            llm_result,
            validation,
        )
        if lazy is None:
            return None
        lazy_result, _ = lazy
        self._accumulate_results(
            lazy_result,
            node.progress.accumulated_tool_results,
        )
        revalidated = self._revalidate_with_accumulated(
            node,
            lazy_result,
            node.progress.accumulated_tool_results,
        )
        return lazy_result, revalidated, revalidated.is_valid

    async def _maybe_lazy_in_stream_loop(
        self,
        node: Node,
        agent: Agent,
        resolved_tools: list[Tool],
        llm_result: LLMResult,
        validation: ValidationResult,
        lazy_attempts: int,
    ) -> tuple[LLMResult, ValidationResult, int] | None:
        """Lazy retry inside the streaming/sync in-loop retry (FR-091).

        Returns (lazy_result, revalidated, new_lazy_attempts) when lazy ran
        (counts toward _LAZY_BUDGET). Returns None when the gate fails or
        lazy returned None (caller falls through to standard retry; the
        slot is NOT burned).
        """
        if lazy_attempts >= _LAZY_BUDGET:
            return None
        if not self._lazy_gate_passes(node, llm_result, validation):
            return None
        lazy = await self._maybe_lazy_recovery(
            node,
            agent,
            resolved_tools,
            llm_result,
            validation,
        )
        if lazy is None:
            return None
        lazy_result, _ = lazy
        self._accumulate_results(
            lazy_result,
            node.progress.accumulated_tool_results,
        )
        revalidated = self._revalidate_with_accumulated(
            node,
            lazy_result,
            node.progress.accumulated_tool_results,
        )
        return lazy_result, revalidated, lazy_attempts + 1

    async def _stream_lazy_valid_completion(
        self,
        node: Node,
        lazy_result: LLMResult,
        stream_messages: list[dict[str, Any]] | None,
        include_meta: bool,
        node_type: str,
        attempt_number: int,
        final_only: bool,
        emit_lifecycle: bool,
    ) -> AsyncIterator[dict[str, Any]]:
        """Emit the valid-completion stream for an in-loop lazy-synthesized result."""
        async for event in self._stream_valid_node_completion(
            node,
            lazy_result.content,
            lazy_result.tool_calls,
            stream_messages,
            include_meta,
            node_type,
            attempt_number,
            final_only,
            emit_lifecycle,
        ):
            yield event

    async def _finalize_lazy_stream_recovery(
        self,
        node: Node,
        lazy_result: LLMResult,
        combined: str,
        emit_lifecycle: bool,
        include_meta: bool,
        final_only: bool,
        node_type: str,
        max_attempts: int,
    ) -> AsyncIterator[dict[str, Any]]:
        """Record + emit completion events for a lazy-recovered streamed node."""
        recovery_content = lazy_result.content or combined
        self._record_node_output(
            node, recovery_content, lazy_result.tool_calls, clear_prior=True
        )
        if recovery_content:
            self._record_node_content_transcript(node, recovery_content)
        on_complete_response = self._build_on_complete_response(node, lazy_result)
        node.on_complete(self.queue, on_complete_response)
        async for event in self._stream_node_completed(
            node,
            recovery_content,
            emit_lifecycle,
            include_meta,
            final_only,
            node_type,
            max_attempts,
        ):
            yield event

    def _resolve_lazy_task_id(
        self,
        task_id: str,
        node: Node,
        last_result: LLMResult,
    ) -> str | None:
        """Resolve a task_id from the markdown via UUID → roadmap number → active.

        Route nodes have no task_id; this is only called for task-state tools.
        """
        store = self.root_session.task_store
        # 1. Direct UUID lookup.
        if task_id in store.tasks:
            return task_id
        # 2. Roadmap number resolution via the session-bound mixin helper.
        try:
            from tinycua.tools.task_tools import SessionTaskToolMixin

            mixin = SessionTaskToolMixin.__new__(SessionTaskToolMixin)
            mixin._session = node.session or self.root_session
            mixin._store = store
            resolved_id, error = mixin._resolve_task_ref(task_id)
            if error is None and resolved_id is not None:
                return resolved_id
        except Exception:  # noqa: BLE001 - best-effort fallback
            pass
        # 3. Active task fallback.
        active_id = store.active_task_id
        if active_id and active_id in store.tasks:
            return active_id
        # 4. Last-resort: a task_id from the most recent task_result_update.
        for item in reversed(last_result.metadata.get("tool_results", [])):
            if not isinstance(item, dict):
                continue
            if item.get("name") != "task_result_update":
                continue
            output = item.get("output")
            if isinstance(output, dict) and output.get("task_id") in store.tasks:
                return str(output["task_id"])
        return None
