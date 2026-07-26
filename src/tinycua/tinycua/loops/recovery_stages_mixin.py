"""LLM-judge recovery stage for the unbounded retry loop.

Extracted from ``validation_retry_mixin.py`` to keep that file under the
1500 LOC hard acceptance gate. All methods are ``self.``-bound and resolved
at runtime via MRO — the mixin is composed into ``TinyCUALoop``.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import TYPE_CHECKING, Any

from tinycua.config.types import LLMResult, ValidationResult
from tinycua.loops.context_rendering import sanitize_internal_reprs
from tinycua.loops.node_contract import RECOVERY_CHAINS

if TYPE_CHECKING:
    from tinycua.loops.node import Node
    from tinycua_sdk.agent.agent import Agent
    from tinycua_sdk.tools.decorators import Tool

logger = logging.getLogger(__name__)
orchestration_logger = logging.getLogger("tinycua.loops.orchestration_mixin")


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
                node,
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
    """Coordinate recovery and guard against retries without progress.

    Extracted from ``orchestration_mixin.py`` to keep that file under the
    1500 LOC gate. Composed into ``TinyCUALoop`` via MRO.
    """

    # FR-061: derived from _NODE_CONTRACTS (single source of truth).
    _RECOVERY_CHAINS = RECOVERY_CHAINS

    def _resolve_recovery_tool(
        self,
        node: Node,
        tool_name: str,
        resolved_tools: list[Tool],
    ) -> Tool | None:
        """Resolve a recovery tool from scope or construct terminate on demand."""
        if tool_name == "terminate":
            from tinycua.tools.task_tools import TerminateTool

            return TerminateTool()
        for tool in resolved_tools:
            if getattr(tool, "name", "") == tool_name:
                return tool
        policy = getattr(node.config, "tool_policy", None)
        if policy is not None:
            for tool in policy.resolve_tools([]):
                if getattr(tool, "name", "") == tool_name:
                    return tool
        return None

    def _log_recovery_cycle(
        self,
        node: Node,
        validation: ValidationResult,
        cycle: int,
        stage_results: dict[str, bool],
    ) -> None:
        """Log system state on every recovery cycle for traceability."""
        store = self.root_session.task_store
        total = len(store.tasks)
        completed = sum(
            1 for task in store.tasks.values() if task.status.value == "completed"
        )
        pending = sum(
            1 for task in store.tasks.values() if task.status.value == "pending"
        )
        in_progress = sum(
            1 for task in store.tasks.values() if task.status.value == "in_progress"
        )
        stages = ", ".join(
            f"{name}={'OK' if passed else 'FAIL'}"
            for name, passed in stage_results.items()
        )
        orchestration_logger.warning(
            "node=%s stuck — recovery cycle=%d errors=%s "
            "task_store root=%s active=%s completed=%d/%d pending=%d in_progress=%d "
            "stages=[%s] queue=%s retrying with tightened context",
            node.node_id,
            cycle,
            "; ".join(validation.errors) or "unknown",
            store.root_task_id or "none",
            store.active_task_id or "none",
            completed,
            total,
            pending,
            in_progress,
            stages,
            [queued.node_id for queued in self.queue.items],
        )

    async def _unbounded_recovery(
        self,
        node: Node,
        agent: Agent,
        resolved_tools: list[Tool],
        llm_result: LLMResult,
        validation: ValidationResult,
    ) -> tuple[LLMResult, ValidationResult] | None:
        """Recover through finite, progress-aware strategy budgets."""
        cycle = 0
        current_result = llm_result
        current_validation = validation
        accumulated_results = dict(node.progress.accumulated_tool_results)
        self._accumulate_results(llm_result, accumulated_results)
        node.progress.accumulated_tool_results = dict(accumulated_results)
        strategy_budgets = {
            "structured_output_retry": 15,
            "focused_retry": 10,
            "judge_retry": 3,
        }
        attempts = node.progress.recovery_attempts
        made_progress = False
        error_history: list[str] = []
        while not current_validation.is_valid:
            cycle += 1
            stage_results: dict[str, bool] = {}
            missing = self._missing_recovery_tools_from_set(
                node, set(accumulated_results)
            )
            made_progress = self._refresh_recovery_fingerprint(
                node,
                current_validation,
                missing,
                accumulated_results,
                attempts,
                strategy_budgets,
                made_progress,
            )
            if missing == ["terminate"]:
                terminated = await self._direct_terminate(node, agent)
                if terminated is not None:
                    current_result, current_validation = terminated
                    self._accumulate_results(current_result, accumulated_results)
                    node.progress.accumulated_tool_results = dict(accumulated_results)
                    current_validation = self._revalidate_with_accumulated(
                        node, current_result, accumulated_results
                    )
                    if current_validation.is_valid:
                        return current_result, current_validation
                stage_results["direct_terminate"] = terminated is not None

            stage = await self._next_recovery_stage(
                node,
                agent,
                resolved_tools,
                current_result,
                current_validation,
                missing,
                attempts,
                strategy_budgets,
            )
            if stage is None:
                return self._handle_recovery_exhaustion(
                    node, current_validation, attempts, made_progress
                )
            stage_name, next_stage, recovery = stage
            attempts[stage_name] = attempts.get(stage_name, 0) + 1
            stage_results[stage_name] = recovery is not None
            outcome = self._apply_recovery_stage(
                node,
                stage_name,
                recovery,
                accumulated_results,
                attempts,
                strategy_budgets,
            )
            if outcome is not None:
                current_result, current_validation = outcome
                if current_validation.is_valid:
                    return outcome
            if next_stage is not None:
                self._record_recovery_escalation(
                    node,
                    stage_name,
                    next_stage,
                    attempts,
                    strategy_budgets,
                )

            repeated = await self._recover_repeated_error(
                node,
                agent,
                current_validation,
                missing,
                accumulated_results,
                attempts,
                strategy_budgets,
                error_history,
            )
            if repeated is not None:
                current_result, current_validation = repeated
                if current_validation.is_valid:
                    return repeated
            self._log_recovery_cycle(node, current_validation, cycle, stage_results)

    def _refresh_recovery_fingerprint(
        self,
        node: Node,
        validation: ValidationResult,
        missing: list[str],
        accumulated_results: dict[str, dict[str, Any]],
        attempts: dict[str, int],
        budgets: dict[str, int],
        made_progress: bool,
    ) -> bool:
        """Reset the active strategy budget after material recovery progress."""
        fingerprint = self._recovery_fingerprint(
            node, validation, missing, accumulated_results
        )
        if fingerprint == node.progress.recovery_fingerprint:
            return made_progress
        made_progress = bool(node.progress.recovery_fingerprint)
        active_strategy = next(
            (
                strategy
                for strategy, budget in budgets.items()
                if attempts.get(strategy, 0) < budget
            ),
            None,
        )
        node.progress.recovery_fingerprint = fingerprint
        if active_strategy is not None:
            attempts[active_strategy] = 0
        return made_progress

    async def _next_recovery_stage(
        self,
        node: Node,
        agent: Agent,
        resolved_tools: list[Tool],
        current_result: LLMResult,
        current_validation: ValidationResult,
        missing: list[str],
        attempts: dict[str, int],
        budgets: dict[str, int],
    ) -> tuple[
        str,
        str | None,
        tuple[LLMResult, ValidationResult] | None,
    ] | None:
        """Run the first recovery stage with budget remaining."""
        if attempts.get("structured_output_retry", 0) < budgets[
            "structured_output_retry"
        ]:
            recovery = await self._structured_output_retry(
                node,
                agent,
                resolved_tools,
                current_result,
                current_validation,
                missing_tools=missing,
            )
            return "structured_output_retry", "focused_retry", recovery
        if attempts.get("focused_retry", 0) < budgets["focused_retry"]:
            recovery = await self._recovery_retry(
                node,
                agent,
                resolved_tools,
                current_result,
                current_validation,
                missing_tools=missing,
            )
            return "focused_retry", "judge_retry", recovery
        if attempts.get("judge_retry", 0) < budgets["judge_retry"]:
            recovery = await self._judge_retry(
                node,
                agent,
                resolved_tools,
                current_result,
                current_validation,
                missing_tools=missing,
            )
            return "judge_retry", None, recovery
        return None

    def _apply_recovery_stage(
        self,
        node: Node,
        stage_name: str,
        recovery: tuple[LLMResult, ValidationResult] | None,
        accumulated_results: dict[str, dict[str, Any]],
        attempts: dict[str, int],
        budgets: dict[str, int],
    ) -> tuple[LLMResult, ValidationResult] | None:
        """Accumulate and revalidate one recovery stage result."""
        if recovery is None:
            return None
        previous_successful = set(accumulated_results)
        result, _ = recovery
        self._accumulate_results(result, accumulated_results)
        node.progress.accumulated_tool_results = dict(accumulated_results)
        self._record_stage_outcome(
            node,
            stage_name,
            recovery,
            previous_successful,
            set(accumulated_results),
        )
        validation = self._revalidate_with_accumulated(
            node, result, accumulated_results
        )
        if self._is_no_progress(previous_successful, accumulated_results, node):
            attempts[stage_name] = budgets[stage_name]
        return result, validation

    def _handle_recovery_exhaustion(
        self,
        node: Node,
        validation: ValidationResult,
        attempts: dict[str, int],
        made_progress: bool,
    ) -> None:
        """Signal re-entry after progress or raise an honest terminal failure."""
        error = "; ".join(validation.errors) or "unknown recovery failure"
        node.progress.recovery_last_error = error
        if made_progress:
            orchestration_logger.info(
                "node=%s recovery_progress_reentry attempts=%s fingerprint=%s",
                node.node_id,
                attempts,
                node.progress.recovery_fingerprint,
            )
            self._recovery_reentry = True
            return None
        orchestration_logger.error(
            "node=%s recovery_exhausted attempts=%s fingerprint=%s error=%s",
            node.node_id,
            attempts,
            node.progress.recovery_fingerprint,
            error,
        )
        node._record_failure(validation, sum(attempts.values()))
        from tinycua.loops.node import NodeExecutionError

        raise NodeExecutionError(f"Recovery exhausted: {error}")

    async def _recover_repeated_error(
        self,
        node: Node,
        agent: Agent,
        validation: ValidationResult,
        missing: list[str],
        accumulated_results: dict[str, dict[str, Any]],
        attempts: dict[str, int],
        budgets: dict[str, int],
        error_history: list[str],
    ) -> tuple[LLMResult, ValidationResult] | None:
        """Change strategy after the same validation error repeats three times."""
        current_error = "; ".join(validation.errors)
        error_history.append(current_error)
        if len(error_history) < 3 or len(set(error_history[-3:])) != 1:
            return None
        error_lower = current_error.lower()
        recent = node.progress.stage_tool_history[-3:]
        stages_ran_tools = any(entry.get("successful_tools") for entry in recent)
        if "call terminate" in error_lower and missing == ["terminate"]:
            orchestration_logger.info(
                "node=%s same-error guard: 'call terminate' ×3", node.node_id
            )
            terminated = await self._direct_terminate(node, agent)
            if terminated is None:
                return None
            result, _ = terminated
            self._accumulate_results(result, accumulated_results)
            return result, self._revalidate_with_accumulated(
                node, result, accumulated_results
            )
        if stages_ran_tools and (
            "task_result_update" in error_lower or "task-state tool" in error_lower
        ):
            orchestration_logger.info(
                "node=%s same-error guard: '%s' ×3, skipping to judge",
                node.node_id,
                current_error[:80],
            )
            attempts["structured_output_retry"] = budgets["structured_output_retry"]
            attempts["focused_retry"] = budgets["focused_retry"]
        return None

    @staticmethod
    def _recovery_fingerprint(
        node: Node,
        validation: ValidationResult,
        missing: list[str],
        accumulated_results: dict[str, dict[str, Any]],
    ) -> str:
        """Return a stable, content-safe recovery progress fingerprint."""
        store = node.session.task_store if node.session is not None else None
        payload = {
            "errors": sorted(validation.errors),
            "missing": missing,
            "tools": accumulated_results,
            "task_version": store.version if store is not None else 0,
            "active_task": store.active_task_id if store is not None else None,
        }
        encoded = json.dumps(payload, sort_keys=True, default=str).encode()
        return hashlib.sha256(encoded).hexdigest()[:16]

    @staticmethod
    def _record_recovery_escalation(
        node: Node,
        strategy: str,
        next_strategy: str,
        attempts: dict[str, int],
        budgets: dict[str, int],
    ) -> None:
        """Record a one-time transition after an unchanged strategy exhausts."""
        if attempts.get(strategy, 0) < budgets[strategy]:
            return
        if any(
            item["strategy"] == strategy
            for item in node.progress.recovery_escalations
        ):
            return
        node.progress.recovery_escalations.append(
            {
                "strategy": strategy,
                "next_strategy": next_strategy,
                "attempts": attempts[strategy],
            },
        )

    async def _direct_terminate(
        self,
        node: Node,
        agent: Agent,
    ) -> tuple[LLMResult, ValidationResult] | None:
        """Call terminate directly without an LLM round-trip."""
        from tinycua.tools.task_tools import TerminateTool

        terminate_tool = TerminateTool()
        self._bind_session_tools([terminate_tool], node)
        terminate_call: dict[str, Any] = {
            "id": "call_direct_terminate",
            "type": "function",
            "function": {
                "name": "terminate",
                "arguments": "{}",
            },
        }
        try:
            tool_results = await self._execute_tool_calls(
                agent, [terminate_call], [terminate_tool], node
            )
        except Exception:
            orchestration_logger.debug(
                "node=%s direct_terminate failed", node.node_id, exc_info=True
            )
            return None
        result = LLMResult(
            content="[Direct terminate — no LLM call needed]",
            role="assistant",
            tool_calls=[terminate_call],
            metadata={"tool_results": tool_results},
        )
        self._record_node_content_transcript(
            node,
            "Direct terminate: terminate called without LLM (no parameters to decide).",
        )
        return result, self._validate_node_result(node, result)

    @staticmethod
    def _accumulate_results(
        llm_result: LLMResult,
        accumulated: dict[str, dict[str, Any]],
    ) -> None:
        """Add successful tool results from a result to the accumulated dict."""
        for item in llm_result.metadata.get("tool_results", []):
            if (
                isinstance(item, dict)
                and isinstance(item.get("output"), dict)
                and item["output"].get("success") is True
            ):
                accumulated[str(item.get("name"))] = item

    def _revalidate_with_accumulated(
        self,
        node: Node,
        llm_result: LLMResult,
        accumulated: dict[str, dict[str, Any]],
    ) -> ValidationResult:
        """Re-validate with accumulated tool results merged into the result."""
        existing = llm_result.metadata.get("tool_results", [])
        existing_names = {
            str(item.get("name")) for item in existing if isinstance(item, dict)
        }
        merged = list(existing)
        for name, item in accumulated.items():
            if name not in existing_names:
                merged.append(item)
        if len(merged) != len(existing):
            llm_result.metadata = dict(llm_result.metadata)
            llm_result.metadata["tool_results"] = merged
        return self._validate_node_result(node, llm_result)

    def _missing_recovery_tools_from_set(
        self,
        node: Node,
        accumulated_successful: set[str],
    ) -> list[str]:
        """Return prerequisite tools not yet called, using the accumulated set."""
        chain = self._RECOVERY_CHAINS.get(node.node_id, ())
        if not chain:
            return []
        return [name for name in chain if name not in accumulated_successful]

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
