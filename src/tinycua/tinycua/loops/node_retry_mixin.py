"""Node retry driver mixin for TinyCUALoop."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from tinycua.agent.tools.native.output_persist import (
    enforce_turn_budget,
    evict_superseded_file_reads,
)
from tinycua.config.types import LLMResult, ValidationResult
from tinycua.loops._loop_constants import (
    _MAX_PROVIDER_RETRIES,
    _MAX_TOOL_CONTINUATIONS,
)
from tinycua.loops.context_rendering import sanitize_internal_reprs
from tinycua.loops.node_contract import LifecyclePhase, NodeState

if TYPE_CHECKING:
    from tinycua_sdk.agent.agent import Agent
    from tinycua_sdk.tools.decorators import Tool

    from tinycua.loops.node import Node

logger = logging.getLogger("tinycua.loops.tinycua_loop")


class NodeRetryMixin:
    """Drive node calls through provider, tool, and validation retries."""

    async def _call_llm_with_provider_retry(
        self,
        agent: Agent,
        node: Node,
        attempt: int,
        attempt_messages: list[dict[str, Any]],
        attempt_tools: list[Tool],
        base_messages: list[dict[str, Any]],
        retry_feedback: list[dict[str, Any]],
        retry_message: str | None,
        provider_retries_ref: list[int],
        *,
        break_on_error: bool = False,
    ) -> dict[str, Any] | None:
        """Call the LLM with catch-compact-retry on provider errors (FR-086).

        Catches any non-cancel exception, force-compacts session_context, and
        retries with a smaller prompt. After ``_MAX_PROVIDER_RETRIES`` failed
        retries, re-raises the original exception.

        Args:
            agent: The SDK agent instance.
            node: The node being executed.
            attempt: The current attempt number (for logging).
            attempt_messages: The messages list for this attempt (rebuilt
                in-place after compaction when ``break_on_error`` is False).
            attempt_tools: The tools list for this attempt.
            base_messages: Base messages for rebuilding after compaction.
            retry_feedback: Retry feedback messages for rebuilding.
            retry_message: Retry message string for rebuilding.
            provider_retries_ref: A one-element list ``[count]`` acting as a
                mutable counter shared across call sites.
            break_on_error: When True (continuation rounds), force-compaction
                then return ``None`` to signal the caller to break to the
                next attempt. When False (initial call), retry in-place.

        Returns:
            The raw LLM response dict, or ``None`` when ``break_on_error`` is
            True and a provider error was caught (caller breaks to next
            attempt).

        Raises:
            The original exception after ``_MAX_PROVIDER_RETRIES`` retries.
        """
        while True:
            try:
                return await self._call_agent_llm(
                    agent,
                    node,
                    attempt_messages,
                    attempt_tools,
                )
            except (asyncio.CancelledError, KeyboardInterrupt):
                raise
            except Exception as exc:
                provider_retries_ref[0] += 1
                if provider_retries_ref[0] > _MAX_PROVIDER_RETRIES:
                    raise
                suffix = ", aborting continuation" if break_on_error else ""
                logger.warning(
                    "provider_error_retry node=%s attempt=%d retry=%d error=%s — forcing compaction%s",
                    node.node_id,
                    attempt,
                    provider_retries_ref[0],
                    str(exc)[:200],
                    suffix,
                )
                await self._force_compact(node, agent)
                if break_on_error:
                    return None  # caller breaks to next attempt
                attempt_messages[:] = self._messages_with_retry_prompt(
                    base_messages,
                    retry_feedback,
                    retry_message,
                )

    def _reset_progress_for_retry(self, node: Node) -> None:
        """Reset node progress while retaining recovery evidence on re-entry."""
        if not self._recovery_reentry:
            node.progress.reset()
            return
        preserved = dict(node.progress.accumulated_tool_results)
        preserved_history = list(node.progress.stage_tool_history)
        recovery_attempts = dict(node.progress.recovery_attempts)
        recovery_fingerprint = node.progress.recovery_fingerprint
        recovery_escalations = list(node.progress.recovery_escalations)
        recovery_last_error = node.progress.recovery_last_error
        node.progress.reset()
        node.progress.accumulated_tool_results = preserved
        node.progress.stage_tool_history = preserved_history
        node.progress.recovery_attempts = recovery_attempts
        node.progress.recovery_fingerprint = recovery_fingerprint
        node.progress.recovery_escalations = recovery_escalations
        node.progress.recovery_last_error = recovery_last_error
        self._recovery_reentry = False

    def _record_attempt_tool_results(
        self,
        result: LLMResult,
        tool_results: list[dict[str, Any]],
        retry_tool_results: list[dict[str, Any]],
    ) -> None:
        """Attach accumulated tool results to the final attempt response."""
        if not tool_results:
            return
        result.metadata = dict(result.metadata)
        result.metadata["tool_results"] = list(tool_results)
        self._prepend_retry_tool_results(result, retry_tool_results)
        self._fill_content_from_recorded_task_result(result)

    async def _retry_invalid_attempt(
        self,
        node: Node,
        agent: Agent,
        resolved_tools: list[Tool],
        result: LLMResult,
        validation: ValidationResult,
        attempt: int,
        max_attempts: int,
        lazy_attempts: int,
    ) -> tuple[
        str,
        LLMResult,
        ValidationResult,
        int,
        tuple[str, list[dict[str, Any]], list[dict[str, Any]]] | None,
    ]:
        """Return the next retry action and optional standard retry context."""
        if attempt >= max_attempts:
            return "exhausted", result, validation, lazy_attempts, None
        retry_signal = await self._handle_retry_attempt(
            node, agent, resolved_tools, result, validation, attempt, lazy_attempts
        )
        if retry_signal is not None:
            action, result, validation, lazy_attempts = retry_signal
            return action, result, validation, lazy_attempts, None
        retry_context = self._prepare_standard_retry(
            node, resolved_tools, result, validation, attempt
        )
        return "retry", result, validation, lazy_attempts, retry_context

    async def _call_node_with_retry(  # noqa: C901
        self,
        node: Node,
        agent: Agent,
        messages: list[dict[str, Any]],
        resolved_tools: list[Tool],
        *,
        reset_progress: bool = True,
    ) -> tuple[LLMResult, int, ValidationResult]:
        """Loop-owned LLM call, validation, and retry lifecycle."""
        max_attempts = self._effective_max_attempts(node)
        last_result = LLMResult()
        last_validation = ValidationResult(is_valid=True, errors=[])
        base_messages = [dict(message) for message in messages]
        retry_message: str | None = None
        retry_feedback: list[dict[str, Any]] = []
        retry_tool_results: list[dict[str, Any]] = []
        lazy_attempts = 0  # FR-091: lazy retry counter; None doesn't burn a slot.
        if reset_progress:
            self._reset_progress_for_retry(node)

        for attempt in range(1, max_attempts + 1):
            # Milestone 2: track per-node state transitions.
            node.progress.attempt_count = attempt
            node.progress.transition(
                NodeState.EXECUTING if attempt == 1 else NodeState.RETRYING,
                reason="attempt" if attempt == 1 else "retry",
            )
            # FR-086: per-attempt provider-error retry counter (mutable list
            # so the helper and continuation site share the same count).
            provider_retries_ref = [0]
            # FR-085: continuous monitoring — compact whenever the session
            # exceeds threshold, not just on retries. Runs on attempt 1 too,
            # as long as a prior call's usage data exists (chicken-and-egg
            # guard in _maybe_compact: _last_input_tokens <= 0 → skip).
            await self._maybe_compact(node, agent)
            attempt_messages = self._messages_with_retry_prompt(
                base_messages,
                retry_feedback,
                retry_message,
            )
            attempt_tools = self._attempt_tools(node, resolved_tools, retry_message)
            # FR-086: catch provider errors, force-compaction, and retry.
            raw_response = await self._call_llm_with_provider_retry(
                agent,
                node,
                attempt,
                attempt_messages,
                attempt_tools,
                base_messages,
                retry_feedback,
                retry_message,
                provider_retries_ref,
            )
            last_result = LLMResult(
                content=sanitize_internal_reprs(raw_response.get("content") or ""),
                role=raw_response.get("role", "assistant"),
                tool_calls=raw_response.get("tool_calls") or [],
                metadata=raw_response.get("metadata", {}),
                reasoning=raw_response.get("reasoning", ""),
            )
            # Milestone 8 Stream B: track token usage for compaction triggers.
            self._track_input_tokens(node, last_result)
            if not node.is_terminal and node.node_id != "result_aggregation":
                self._coerce_structured_tool_calls(last_result, attempt_tools)
            self._coerce_terminate_only_response(attempt_tools, last_result)
            attempt_tools = self._tools_for_lifecycle_result(
                node, last_result, resolved_tools
            )
            all_tool_results: list[dict[str, Any]] = []
            continuation_rounds = 0
            while continuation_rounds < _MAX_TOOL_CONTINUATIONS:
                tool_results = await self._execute_tool_calls(
                    agent,
                    last_result.tool_calls,
                    attempt_tools,
                    node,
                )
                if not tool_results:
                    break
                all_tool_results.extend(tool_results)
                # Milestone 2: track visited + satisfied tools in node progress.
                self._track_tool_calls_in_progress(node, tool_results)
                self._enrich_task_results_from_tool_batch(node, all_tool_results)
                normalized_tool_calls = self._normalize_tool_calls(
                    last_result.tool_calls
                )
                last_result.tool_calls = normalized_tool_calls
                last_result.metadata = dict(last_result.metadata)
                last_result.metadata["tool_results"] = list(all_tool_results)
                self._prepend_retry_tool_results(last_result, retry_tool_results)
                self._fill_content_from_recorded_task_result(last_result)
                phase_before = node.progress.lifecycle_phase
                attempt_tools = self._advance_lifecycle_tools(
                    node, last_result, resolved_tools, attempt_tools
                )
                last_validation = self._validate_node_result(node, last_result)
                if self._can_stop_tool_batch(node, last_result, last_validation):
                    return last_result, attempt, last_validation
                if self._validation_needs_terminate(last_validation) or (
                    node.progress.lifecycle_phase == LifecyclePhase.TERMINATE
                    and any(
                        item.get("name") == "terminate"
                        and isinstance(item.get("output"), dict)
                        and item["output"].get("success") is True
                        for item in tool_results
                    )
                ):
                    break
                assistant_msg: dict[str, Any] = {
                    "role": "assistant",
                    "content": last_result.content,
                    "tool_calls": normalized_tool_calls,
                }
                # Reasoning coherency: re-inject reasoning_content so the
                # model retains its thinking trace across tool-call turns
                # (Qwen3 maintainers: multi-step tool use requires it). Gated
                # on non-empty so non-reasoning models are unaffected.
                if last_result.reasoning:
                    assistant_msg["reasoning_content"] = last_result.reasoning
                attempt_messages.append(assistant_msg)
                self._append_tool_result_messages(
                    attempt_messages, tool_results, normalized_tool_calls
                )
                self._append_lifecycle_phase_directive(
                    attempt_messages, node, phase_before, attempt_tools
                )
                # Evict superseded file reads: when the model re-reads a file
                # it just edited, the older reads are stale (the file changed).
                # Stub them so the prompt stops growing from redundant re-reads
                # (experiment-4 executor re-read api.py 8× → ballooned to 68K).
                # This passes the FULL attempt_messages (assistant tool_calls +
                # tool results interleaved) so the path mapping can resolve.
                evict_superseded_file_reads(attempt_messages)
                # High safety-net ceiling only — NOT a tight budget. Normal
                # operation never hits it; it's an OOM guard for pathological
                # runaway (e.g. 100 distinct large file reads).
                enforce_turn_budget(attempt_messages)
                continuation_rounds += 1
                if continuation_rounds >= _MAX_TOOL_CONTINUATIONS:
                    break
                # FR-086: catch provider errors during continuation rounds
                # (context overflow from accumulated tool results). On error,
                # force-compaction and break to the next attempt.
                raw_response = await self._call_llm_with_provider_retry(
                    agent,
                    node,
                    attempt,
                    attempt_messages,
                    attempt_tools,
                    base_messages,
                    retry_feedback,
                    retry_message,
                    provider_retries_ref,
                    break_on_error=True,
                )
                if raw_response is None:
                    break  # provider error → next attempt rebuilds from compacted context
                last_result = LLMResult(
                    content=sanitize_internal_reprs(raw_response.get("content") or ""),
                    role=raw_response.get("role", "assistant"),
                    tool_calls=raw_response.get("tool_calls") or [],
                    metadata={
                        **raw_response.get("metadata", {}),
                        "tool_results": list(all_tool_results),
                    },
                )
                if not node.is_terminal and node.node_id != "result_aggregation":
                    self._coerce_structured_tool_calls(last_result, attempt_tools)
                self._coerce_terminate_only_response(attempt_tools, last_result)
                attempt_tools = self._tools_for_lifecycle_result(
                    node, last_result, resolved_tools
                )
            self._record_attempt_tool_results(
                last_result, all_tool_results, retry_tool_results
            )
            if self._advance_lifecycle_phase(node, last_result):
                retry_tool_results = self._tool_results_from_llm_result(last_result)
                retry_message = self._lifecycle_phase_directive(node, resolved_tools)
                retry_feedback = self._tool_feedback_messages(last_result)
                continue
            last_validation = self._validate_node_result(node, last_result)
            if last_validation.is_valid:
                return last_result, attempt, last_validation
            (
                action,
                last_result,
                last_validation,
                lazy_attempts,
                retry_context,
            ) = await self._retry_invalid_attempt(
                node,
                agent,
                resolved_tools,
                last_result,
                last_validation,
                attempt,
                max_attempts,
                lazy_attempts,
            )
            if action == "return":
                return last_result, attempt, last_validation
            if action != "retry":
                break
            retry_message, retry_feedback, retry_tool_results = retry_context or (
                "",
                [],
                [],
            )

        node._handle_exhaustion(last_validation, max_attempts)
        return last_result, max_attempts, last_validation
