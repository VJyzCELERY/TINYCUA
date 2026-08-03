"""Validation and retry mixin for TinyCUALoop.

Extracted from ``tinycua_loop.py`` to keep the core loop file under 1000 LOC.
All methods are ``self.``-bound and resolved at runtime via MRO.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from tinycua.config.types import LLMResult, ValidationError, ValidationResult
from tinycua.loops._loop_constants import _UNBOUNDED_RETRY_ATTEMPTS
from tinycua.loops.context_rendering import sanitize_internal_reprs
from tinycua.loops.node_contract import (
    ANY_OF_TOOLS_BY_NODE,
    REQUIRED_TOOLS_BY_NODE,
    RECOVERY_TOOL_MAP,
    TERMINATED_NODE_IDS,
)
from tinycua.loops.node_guidance import failed_tool_retry_message
from tinycua.loops.reviewer_protocol import commit_staged_review
from tinycua.loops.route_classifier import RouteClassifier
from tinycua.models.node_handoff import NodeHandoff

if TYPE_CHECKING:
    from tinycua.loops.node import Node
    from tinycua_sdk.agent.agent import Agent
    from tinycua_sdk.tools.decorators import Tool

logger = logging.getLogger(__name__)


class ValidationRetryMixin:
    """Mixin extracted from TinyCUALoop for modularity."""

    # FR-061: derived from _NODE_CONTRACTS (single source of truth).
    _TERMINATED_NODE_IDS = TERMINATED_NODE_IDS

    def _can_terminate(self, node: Node) -> bool:
        """Return whether the node's real commit state permits termination."""
        if not node.contract.is_satisfied(node.progress.satisfied_requirements):
            return False
        store = self.root_session.task_store
        if node.node_id == "task_create":
            return store.root_task_id is not None
        if node.node_id == "task_executor":
            active = store.get_active_task()
            return active is not None and active.result is not None
        if node.node_id == "result_reviewer":
            return store.active_task_id in store._staged_reviewer_decisions
        if node.node_id == "task_assessor":
            return any(
                handoff.source_node == node.node_id
                for handoff in self._pending_handoffs
            )
        if node.node_id == "task_analyzer":
            handoff = self._current_analyzer_handoff(node)
            if handoff is not None and handoff.payload.get("decision") == "analyze":
                selected = set(handoff.payload.get("selected_task_ids", []))
                return bool(selected) and not self._unresolved_analyzer_target_ids(node)
        return True

    def _current_analyzer_handoff(self, node: Node) -> NodeHandoff | None:
        """Return the assessor handoff assigned to the current analyzer."""
        if self.queue.current is not node:
            return None
        node_input = self.queue.input_for_current()
        return node_input if isinstance(node_input, NodeHandoff) else None

    def _unresolved_analyzer_target_ids(self, node: Node) -> set[str]:
        """Return assessor-selected targets not yet resolved by this analyzer."""
        handoff = self._current_analyzer_handoff(node)
        if handoff is None or handoff.payload.get("decision") != "analyze":
            return set()
        selected = set(handoff.payload.get("selected_task_ids", []))
        resolved = set(handoff.payload.get("_resolved_task_ids", []))
        return selected - resolved

    def _should_stop_commit_batch(self, node: Node | None) -> bool:
        """Stop commits unless an analyzer still has selected targets to resolve."""
        return (
            node is None
            or node.node_id != "task_analyzer"
            or not self._unresolved_analyzer_target_ids(node)
        )

    def _task_is_in_subtree(self, task_id: str, target_id: str) -> bool:
        """Return whether a retained task belongs to a selected local subtree."""
        current = task_id
        while current in self.root_session.task_store.tasks:
            if current == target_id:
                return True
            parent_id = self.root_session.task_store.tasks[current].parent_id
            if parent_id is None:
                break
            current = parent_id
        return task_id == target_id

    def _record_analyzer_planning_resolution(
        self,
        node: Node | None,
        tool_name: str,
        output: Any,
        impacted_target_ids: set[str],
    ) -> None:
        """Acknowledge selected targets changed by a successful mutation."""
        if (
            node is None
            or node.node_id != "task_analyzer"
            or not isinstance(output, dict)
            or output.get("success") is not True
            or not impacted_target_ids
        ):
            return
        handoff = self._current_analyzer_handoff(node)
        if handoff is None or handoff.payload.get("decision") != "analyze":
            return
        findings = handoff.payload.get("findings", [])
        for finding in findings:
            if not isinstance(finding, dict):
                continue
            target_id = finding.get("task_id")
            if not isinstance(target_id, str):
                continue
            if target_id not in impacted_target_ids:
                continue
            task = self.root_session.task_store.tasks.get(target_id)
            planning_note = (
                str(task.metadata.get("planning_note", "")).strip() if task else ""
            )
            resolved = handoff.payload.setdefault("_resolved_task_ids", [])
            if target_id not in resolved:
                resolved.append(target_id)
            rationale = (
                planning_note
                or str(
                    output.get("rationale") or node.progress.action_summary or ""
                ).strip()
            )
            resolution = {
                "assessment_id": finding.get("assessment_id"),
                "summary": (
                    "Retained with a planning note."
                    if planning_note
                    else f"{tool_name} changed the selected local subtree."
                ),
                "rationale": rationale[:2000],
            }
            if task is not None:
                task.metadata["planning_resolution"] = resolution
                self.root_session.task_store._bump_version()

    def _retry_message_for_validation(
        self,
        error: ValidationError,
        node: Node,
        resolved_tools: list[Tool],
        llm_result: LLMResult,
    ) -> str:
        """Build retry guidance as an imperative runtime directive."""
        if failed_message := failed_tool_retry_message(llm_result):
            return failed_message
        if node.node_id == "task_executor" and "task_result_update" in str(error):
            return (
                "Call task_result_update with a concise outcome report. Set "
                "success=true when complete or success=false when failed or blocked."
            )
        if "terminate" in str(error):
            return self._lifecycle_phase_directive(node, resolved_tools)
        return self._natural_retry_message(error, node, resolved_tools)

    def _messages_with_retry_prompt(
        self,
        base_messages: list[dict[str, Any]],
        retry_feedback: list[dict[str, Any]],
        retry_message: str | None,
    ) -> list[dict[str, Any]]:
        """Return base node messages, latest tool feedback, and one retry prompt.

        The retry prompt is emitted as a ``role:"user"`` message with a
        ``[System: ...]`` prefix marking its internal-runtime origin. The user
        role is required for provider role-alternation; the prefix
        distinguishes it from a genuine external user turn. See FR-004.
        """
        messages = [dict(message) for message in base_messages]
        messages.extend(dict(message) for message in retry_feedback)
        if retry_message:
            messages.append(
                {
                    "role": "user",
                    "content": self._retry_prompt_for_llm(retry_message),
                }
            )
        return messages

    @staticmethod
    def _retry_prompt_for_llm(retry_message: str) -> str:
        """Wrap an internal retry directive as a [System: ...] user message.

        The ``[System: ...]`` prefix marks the message as an internal runtime
        directive (not a genuine user turn) while keeping the ``user`` role
        required by OpenAI-compatible provider role alternation. Imperative
        directive voice is preserved as-is (no first/second-person conversion).
        See FR-004.
        """
        return f"[System: {retry_message}]"

    def _tools_for_retry_attempt(
        self,
        node: Node,
        resolved_tools: list[Tool],
        retry_message: str | None,
    ) -> list[Tool]:
        """Narrow retry tools when validation names one required state tool."""
        if self._should_expose_terminate_tool(node, retry_message):
            from tinycua.tools.task_tools import TerminateTool

            if any(tool.name == "terminate" for tool in resolved_tools):
                return resolved_tools
            if node.node_id == "result_reviewer":
                return [*resolved_tools, TerminateTool()]
            return [TerminateTool()]
        required = self._retry_required_tool_name(node, retry_message)
        if required is None:
            return resolved_tools
        narrowed = [tool for tool in resolved_tools if tool.name == required]
        return narrowed or resolved_tools

    def _should_expose_terminate_tool(
        self,
        node: Node,
        retry_message: str | None,
    ) -> bool:
        """Return whether retry should expose explicit node termination."""
        return (
            node.node_id in self._TERMINATED_NODE_IDS
            and retry_message is not None
            and "terminate" in retry_message
        )

    @staticmethod
    def _validation_needs_terminate(validation: ValidationResult) -> bool:
        """Return whether validation only needs explicit node termination."""
        return any("terminate" in error for error in validation.errors)

    @staticmethod
    def _coerce_terminate_only_response(
        resolved_tools: list[Tool],
        llm_result: LLMResult,
    ) -> None:
        """Treat an empty terminate-only LLM turn as terminate()."""
        if [tool.name for tool in resolved_tools] != ["terminate"]:
            return
        if llm_result.tool_calls:
            return
        # ponytail: local models can ignore forced terminate; this only fires
        # after terminate is the sole exposed action.
        llm_result.tool_calls = [
            {
                "id": "call_terminate",
                "type": "function",
                "function": {"name": "terminate", "arguments": "{}"},
            }
        ]

    def _retry_required_tool_name(
        self,
        node: Node,
        retry_message: str | None,
    ) -> str | None:
        """Return a required tool that should be isolated for this retry."""
        if not retry_message:
            return None
        retry_required_by_node = {
            "task_assessor": "task_assessment_decision",
        }
        required = retry_required_by_node.get(node.node_id)
        if required and required in retry_message:
            return required
        return None

    def _prepend_retry_tool_results(
        self,
        llm_result: LLMResult,
        retry_tool_results: list[dict[str, Any]],
    ) -> None:
        """Expose latest retry feedback tool results to current validation."""
        if not retry_tool_results:
            return
        current = self._tool_results_from_llm_result(llm_result)
        llm_result.metadata["tool_results"] = [*retry_tool_results, *current]

    def _tool_results_from_llm_result(
        self,
        llm_result: LLMResult,
    ) -> list[dict[str, Any]]:
        """Return successful/failed tool result records carried by an LLM result."""
        return [
            item
            for item in llm_result.metadata.get("tool_results", [])
            if isinstance(item, dict)
        ]

    def _fill_content_from_recorded_task_result(self, llm_result: LLMResult) -> None:
        """Populate empty content from successful task_result_update state."""
        if llm_result.content.strip():
            return
        for item in reversed(llm_result.metadata.get("tool_results", [])):
            if not isinstance(item, dict) or item.get("name") != "task_result_update":
                continue
            output = item.get("output")
            if not isinstance(output, dict) or output.get("success") is not True:
                continue
            task_id = output.get("task_id")
            if not isinstance(task_id, str):
                continue
            try:
                task = self.root_session.task_store.get_task(task_id)
            except ValueError:
                continue
            if task.result is not None and task.result.content.strip():
                llm_result.content = task.result.content
                return

    def _recover_task_executor_validation_failure(
        self,
        node: Node,
        validation: ValidationResult,
        llm_result: LLMResult,
    ) -> bool:
        """Recover exhausted TaskExecutor validation via local replan.

        Runtime validation failures are not task results. In one-shot worker
        mode, the active task remains unfinished and the runtime gives the
        planner a chance to revise/decompose the local task region before
        execution continues.
        """
        if node.node_id != "task_executor" or node.is_terminal:
            return False
        if self.queue.current is not node:
            return False
        active = self.root_session.task_store.get_active_task()
        if active is None:
            return False
        tool_results = list(llm_result.metadata.get("tool_results", []))
        action_results = self._successful_executor_action_results(tool_results)
        if action_results:
            existing = active.metadata.setdefault("executor_partial_tool_results", [])
            existing.extend(self._json_safe(action_results))
            self._record_node_content_transcript(
                node,
                "TaskExecutor performed workspace/research actions but did not "
                "record task_result_update; continuing the same active task with "
                "partial evidence instead of replanning or marking failure.",
            )
            self._recovery_reentry = True
            return True
        if not self._successful_executor_inspection_results(tool_results):
            # ponytail: no usable tool evidence means fail closed; don't respawn forever.
            return False
        active.metadata["runtime_validation_failure"] = {
            "source_node_id": node.node_id,
            "errors": list(validation.errors),
            "recovery": "executor_retry",
            "tool_results": self._json_safe(tool_results),
            "guidance": (
                "Previous executor attempt did not record task_result_update. "
                "Retry the active task and call task_result_update with the "
                "observed evidence or a concrete blocked result before review."
            ),
        }
        self._record_node_content_transcript(
            node,
            "TaskExecutor validation failed after retries; retrying the same "
            "active task instead of bypassing ResultReviewer into replan.",
        )
        self._recovery_reentry = True
        return True

    def _effective_max_attempts(self, node: Node) -> int:
        """Return bounded retry attempts for the loop-owned call path."""
        retry_policy = node.config.retry_policy
        if retry_policy.max_attempts is None:
            return _UNBOUNDED_RETRY_ATTEMPTS
        return max(retry_policy.max_attempts, 1)

    def _prepare_standard_retry(
        self,
        node: Node,
        resolved_tools: list[Tool],
        last_result: LLMResult,
        validation: ValidationResult,
        attempt: int,
    ) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
        """Build (retry_message, retry_feedback, retry_tool_results) for the next attempt."""
        error = ValidationError("; ".join(validation.errors))
        retry_message = self._retry_message_for_validation(
            error, node, resolved_tools, last_result
        )
        retry_feedback = self._tool_feedback_messages(last_result)
        retry_tool_results = self._tool_results_from_llm_result(last_result)
        self._record_retry_continuation(node, retry_message, attempt)
        return retry_message, retry_feedback, retry_tool_results

    def _natural_retry_message(
        self,
        error: ValidationError,
        node: Node,
        resolved_tools: list[Tool],
    ) -> str:
        """Build an imperative self-correction retry directive.

        Emits imperative voice directly (e.g. "Call X..."), not first-person
        "I need to..." prose. See FR-004.
        """
        del resolved_tools
        error_text = str(error)
        if (
            node.node_id == "task_analyzer"
            and "task_decompose" in error_text
            and "task_update" in error_text
        ):
            # FR-066: include rationale from contract so the model knows WHY.
            contract = node.contract
            decompose_why = contract.tool_rationale.get("task_decompose", "")
            update_why = contract.tool_rationale.get("task_update", "")
            parts = ["Call task_decompose if the roadmap needs structural changes"]
            if decompose_why:
                parts.append(f"({decompose_why})")
            parts.append("or task_update if no further decomposition is useful")
            if update_why:
                parts.append(f"({update_why})")
            return " ".join(parts) + "."
        required = self._missing_or_required_tool_name(node, error_text)
        if required:
            return f"Call {required} with the current evidence before continuing."
        return f"Correct this response before continuing: {error!s}"

    def _record_retry_continuation(
        self,
        node: Node,
        retry_message: str,
        attempt: int,
    ) -> None:
        """Record retry continuation in chat history without session_context reuse."""
        from tinycua.models.chat_record import ChatRecord

        self.root_session.chat_history.append(
            ChatRecord(
                role="assistant",
                record_type="retry",
                content=retry_message,
                visibility="internal",
                source_node_id=node.node_id,
                source_session_id=self.root_session.session_id,
                created_seq=len(self.root_session.chat_history),
                metadata={"attempt": attempt},
            )
        )

    def _validate_node_result(
        self,
        node: Node,
        llm_result: LLMResult,
    ) -> ValidationResult:
        """Validate node output plus TinyCUA runtime invariants."""
        validation = node.validate_output(llm_result)
        for extra_validation in (
            self._validate_task_executor_action(node, llm_result),
            self._validate_tool_owned_task_state(node, llm_result),
            self._validate_task_analyzer_resolutions(node),
            self._validate_result_reviewer_failed_approval(node, llm_result),
            self._validate_result_reviewer_result_exists(node, llm_result),
            self._validate_result_reviewer_inspects_after_decision(node, llm_result),
            self._validate_result_reviewer_report(node, llm_result),
            self._validate_result_reviewer_assurance(node),
            self._validate_decision_route_tool(node, llm_result),
            self._validate_final_response_content(node, llm_result),
        ):
            if not extra_validation.is_valid:
                validation.is_valid = False
                validation.errors.extend(extra_validation.errors)
        if (
            validation.is_valid
            and node.node_id == "result_reviewer"
            and node.progress.lifecycle_phase.value == "commit"
        ):
            active_id = self.root_session.task_store.active_task_id
            staged = self.root_session.task_store._staged_reviewer_decisions
            if active_id in staged:
                try:
                    commit_staged_review(
                        self.root_session.task_store,
                        getattr(self.root_session, "artifact_store", None),
                        active_id,
                    )
                except ValueError as exc:
                    validation.is_valid = False
                    validation.errors.append(str(exc))
        return validation

    def _validate_task_analyzer_resolutions(self, node: Node) -> ValidationResult:
        """Require every assessor-selected task to have a planning resolution."""
        validation = ValidationResult(is_valid=True, errors=[])
        if node.node_id != "task_analyzer":
            return validation
        handoff = self._current_analyzer_handoff(node)
        if handoff is None or handoff.payload.get("decision") != "analyze":
            return validation
        missing = sorted(self._unresolved_analyzer_target_ids(node))
        if missing:
            validation.is_valid = False
            validation.errors.append(
                "TaskAnalyzer must resolve every assessor-selected task before "
                f"completion; unresolved task IDs: {missing}."
            )
        return validation

    def _validate_decision_route_tool(
        self,
        node: Node,
        llm_result: LLMResult,
    ) -> ValidationResult:
        """Validate route-tool arguments against current state-valid labels."""
        validation = ValidationResult(is_valid=True, errors=[])
        required = self._required_route_tool_name(node)
        labels = list(getattr(node, "classification_labels", []))
        if required is None or not labels:
            return validation
        classifier = RouteClassifier(labels)
        for tool_call in llm_result.tool_calls:
            function = tool_call.get("function") or {}
            name = function.get("name") or tool_call.get("name")
            if name != required:
                continue
            arguments = function.get("arguments") or tool_call.get("arguments") or {}
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except json.JSONDecodeError:
                    arguments = {"route": arguments}
            route = arguments.get("route") if isinstance(arguments, dict) else None
            try:
                classifier.classify(str(route))
            except ValueError:
                validation.is_valid = False
                validation.errors.append(
                    f"{required} route must be one of {labels}; got {route!r}."
                )
        return validation

    def _validate_result_reviewer_failed_approval(
        self,
        node: Node,
        llm_result: LLMResult,
    ) -> ValidationResult:
        """Prevent approval from accepting failed executor evidence as done."""
        validation = ValidationResult(is_valid=True, errors=[])
        if node.node_id != "result_reviewer":
            return validation
        tool_results = self._tool_results_from_llm_result(llm_result)
        for item in reversed(tool_results):
            if item.get("name") != "task_review_decision":
                continue
            output = item.get("output")
            if not isinstance(output, dict) or output.get("decision") != "approved":
                return validation
            task_id = output.get("task_id")
            if not isinstance(task_id, str):
                return validation
            try:
                task = self.root_session.task_store.get_task(task_id)
            except ValueError:
                return validation
            if task.result is None or task.result.success is not False:
                return validation
            self._rollback_invalid_reviewer_approval(task_id)
            validation.is_valid = False
            validation.errors.append(
                "ResultReviewer cannot approve a failed task result. Choose "
                "needs_revision, replan, or the next valid postponement after "
                "inspecting the failure evidence."
            )
            return validation
        return validation

    def _validate_result_reviewer_result_exists(
        self,
        node: Node,
        llm_result: LLMResult,
    ) -> ValidationResult:
        """Prevent reviewer from approving a task with no result report."""
        validation = ValidationResult(is_valid=True, errors=[])
        if node.node_id != "result_reviewer":
            return validation
        tool_results = self._tool_results_from_llm_result(llm_result)
        decision_result = None
        for item in reversed(tool_results):
            if item.get("name") == "task_review_decision":
                output = item.get("output")
                if isinstance(output, dict):
                    decision_result = output
                    break
        if not decision_result or decision_result.get("decision") != "approved":
            return validation
        task_id = decision_result.get("task_id")
        if (
            not isinstance(task_id, str)
            or task_id not in self.root_session.task_store.tasks
        ):
            return validation
        task = self.root_session.task_store.tasks[task_id]
        if task.result is not None and task.result.content.strip():
            return validation
        # Parent tasks (root, phases) are verified by the executor after all
        # children complete — the executor calls task_result_update with the
        # verification report. But if the executor didn't record a result (e.g.
        # it verified via tools but forgot task_result_update), don't block the
        # approval with "no outcome report" — the children's results are the
        # evidence. Without this exemption, the reviewer crashes in an
        # unrecoverable loop trying to approve a parent with no result.
        if task.children:
            return validation
        self._rollback_invalid_reviewer_approval(task_id)
        validation.is_valid = False
        validation.errors.append(
            "ResultReviewer cannot approve a task with no outcome report. "
            "The executor must call task_result_update with a non-empty result. "
            "Choose needs_revision to retry execution."
        )
        return validation

    def _validate_result_reviewer_inspects_after_decision(
        self,
        node: Node,
        llm_result: LLMResult,
    ) -> ValidationResult:
        """Keep accepted decisions while allowing post-decision context curation."""
        del node, llm_result
        return ValidationResult(is_valid=True, errors=[])

    def _validate_result_reviewer_report(
        self,
        node: Node,
        llm_result: LLMResult,
    ) -> ValidationResult:
        """Require a report without prescribing evidence syntax."""
        validation = ValidationResult(is_valid=True, errors=[])
        if node.node_id != "result_reviewer":
            return validation
        from tinycua.loops.node_guidance import validate_reviewer_report

        validation.errors.extend(validate_reviewer_report(llm_result.tool_calls))
        validation.is_valid = not validation.errors
        return validation

    def _validate_result_reviewer_assurance(self, node: Node) -> ValidationResult:
        """Require cited empirical observations from the current root review."""
        if node.node_id != "result_reviewer" or node.session is None:
            return ValidationResult(is_valid=True, errors=[])
        from tinycua.loops.reviewer_protocol import reviewer_assurance_validation

        return reviewer_assurance_validation(node, self.root_session.task_store)

    def _rollback_invalid_reviewer_approval(self, task_id: str) -> None:
        """Undo reviewer approval side effects when runtime validation rejects it."""
        task = self.root_session.task_store.tasks.get(task_id)
        if task is None:
            return
        self.root_session.task_store._staged_reviewer_decisions.pop(task_id, None)
        from tinycua.models.task import TaskStatus

        if (
            task.reviewer_decisions
            and task.reviewer_decisions[-1].get("decision") == "approved"
        ):
            task.reviewer_decisions.pop()
        if task.status.value == "completed":
            task.status = TaskStatus.IN_PROGRESS
        parent_id = task.parent_id
        while parent_id is not None:
            parent = self.root_session.task_store.tasks.get(parent_id)
            if parent is None:
                break
            has_unfinished_child = any(
                self.root_session.task_store.tasks[child_id].status
                != TaskStatus.COMPLETED
                for child_id in parent.children
                if child_id in self.root_session.task_store.tasks
            )
            if has_unfinished_child and parent.status == TaskStatus.COMPLETED:
                parent.status = TaskStatus.IN_PROGRESS
                if parent.result and parent.result.metadata.get("aggregated") is True:
                    parent.result = None
            parent_id = parent.parent_id
        self.root_session.task_store.active_task_id = task.task_id

    def _validate_final_response_content(
        self,
        node: Node,
        llm_result: LLMResult,
    ) -> ValidationResult:
        """Validate that the terminal response is user-facing text."""
        validation = ValidationResult(is_valid=True, errors=[])
        if node.node_id != "response":
            return validation
        store = self.root_session.task_store
        if store.root_task_id is not None and not store.all_done():
            validation.is_valid = False
            validation.errors.append(
                "Final response cannot run until every task is completed."
            )
            return validation
        content = llm_result.content.strip()
        if not content:
            # ponytail: when the Response node called tools successfully but
            # produced no accompanying text, synthesize a minimal response from
            # the tool results instead of failing validation. This prevents
            # retry exhaustion on tool-call-only rounds (e.g. passthrough mode
            # where the agent writes a file but doesn't produce a text summary).
            # Upgrade path: give the agent another LLM call to produce proper
            # text instead of synthesizing, if response quality matters.
            tool_results = llm_result.metadata.get("tool_results", [])
            successful = [
                item
                for item in tool_results
                if isinstance(item, dict)
                and isinstance(item.get("output"), dict)
                and item["output"].get("success") is True
            ]
            if successful:
                summaries: list[str] = []
                for item in successful:
                    name = item.get("name", "tool")
                    output = item.get("output", {})
                    path = output.get("path")
                    if path:
                        summaries.append(f"{name}: {path}")
                    else:
                        summaries.append(f"{name}: done")
                llm_result.content = "Done. " + "; ".join(summaries)
                return validation
            validation.is_valid = False
            validation.errors.append("Final response must be non-empty.")
            return validation
        if '"tool_calls"' in content or "</tool_call>" in content:
            validation.is_valid = False
            validation.errors.append(
                "Final response must be natural user-facing text, not a tool-call "
                "protocol payload."
            )
        internal_markers = (
            "Based on the external user request above",
            "Based on the accepted Worker result",
            "Based on the context above",
            "Direct response context",
            "Reply naturally and directly to the user",
            "Task under review:",
            "## Current State",
            "Completed task evidence:",
            '{"aggregation":',
        )
        if any(marker in content for marker in internal_markers):
            validation.is_valid = False
            validation.errors.append(
                "Final response must summarize the outcome, not replay internal "
                "node prompts, task review text, or aggregation JSON."
            )
        if store.root_task_id is not None and store.all_done():
            clarification_markers = (
                "I need clarification",
                "What specific task remains?",
                "Current working directory?",
                "rather than guessing",
            )
            if any(marker in content for marker in clarification_markers):
                validation.is_valid = False
                validation.errors.append(
                    "Final response must summarize completed task outcome, not ask "
                    "for clarification after all tasks are complete."
                )
        return validation

    def _can_stop_after_tool_batch(
        self,
        node: Node,
        llm_result: LLMResult,
        validation: ValidationResult,
    ) -> bool:
        """Return whether a tool batch completed this nonterminal node."""
        if node.is_terminal or not validation.is_valid:
            return False
        if node.contract.requires_terminate:
            return False
        required_route = self._required_route_tool_name(node)
        if required_route is not None:
            return True
        if node.node_id == "digester":
            return self._tool_results_include(llm_result, "digest_information")
        if node.node_id in {
            "task_create",
            "task_analyzer",
            "result_reviewer",
        }:
            return bool(llm_result.metadata.get("tool_results"))
        if node.node_id == "task_assessor":
            return self._tool_results_include(llm_result, "task_assessment_decision")
        if node.node_id == "task_executor":
            return self._tool_results_include(llm_result, "task_result_update")
        return False

    def _tool_results_include(self, llm_result: LLMResult, tool_name: str) -> bool:
        """Return whether metadata contains a result for a named tool."""
        return any(
            isinstance(item, dict) and item.get("name") == tool_name
            for item in llm_result.metadata.get("tool_results", [])
        )

    def _validate_task_executor_action(
        self,
        node: Node,
        llm_result: LLMResult,
    ) -> ValidationResult:
        """Validate that TaskExecutor recorded an outcome through its result tool."""
        validation = ValidationResult(is_valid=True, errors=[])
        if node.node_id != "task_executor":
            return validation
        tool_results = self._tool_results_from_llm_result(llm_result)
        if not tool_results and not node.progress.satisfied_requirements:
            validation.is_valid = False
            validation.errors.append(
                "TaskExecutor must use tools to execute, inspect, verify, record a "
                "result, or report a blocked state; do not return a plan-only answer."
            )
            return validation
        # Require that task_result_update was called
        result_update_calls = [
            item
            for item in tool_results
            if item.get("name") == "task_result_update"
            and isinstance(item.get("output"), dict)
        ]
        if (
            not result_update_calls
            and "task_result_update" not in node.progress.satisfied_requirements
        ):
            validation.is_valid = False
            validation.errors.append(
                "TaskExecutor must call task_result_update with an outcome report "
                "before finishing. Describe what was done, what was found, and "
                "whether the task succeeded or failed."
            )
        return validation

    def _validate_tool_owned_task_state(
        self,
        node: Node,
        llm_result: LLMResult,
    ) -> ValidationResult:
        """Validate task-state nodes mutate state through tools, not prose."""
        validation = ValidationResult(is_valid=True, errors=[])
        tool_results = llm_result.metadata.get("tool_results", [])
        successful_tool_names = {
            str(item.get("name"))
            for item in tool_results
            if isinstance(item, dict)
            and isinstance(item.get("output"), dict)
            and item["output"].get("success") is True
        }
        # FR-062: merge progress.satisfied_requirements (accumulated across
        # recovery stages + re-entries) with the current result's tool_results.
        successful_tool_names |= node.progress.satisfied_requirements
        # Executor failure reports (success=False) are valid blocker signals for reviewer/replan
        has_executor_failure_report = any(
            isinstance(item, dict)
            and item.get("name") == "task_result_update"
            and isinstance(item.get("output"), dict)
            and item["output"].get("success") is False
            for item in tool_results
        )
        # FR-061: use contract-derived maps instead of ad-hoc dicts.
        # Only apply task-state validation to terminated nodes (task-state
        # lifecycle nodes). Route-selection nodes (query_analyst, worker) have
        # required_tools but are validated via validate_output, not here.
        if node.node_id not in TERMINATED_NODE_IDS:
            return validation
        any_of_groups = ANY_OF_TOOLS_BY_NODE.get(node.node_id)
        if any_of_groups is not None:
            # any_of_tools is a frozenset of frozensets — any one group must
            # be fully satisfied. But for the "any-of" validation, the
            # original code treated it as a flat set (intersection). We keep
            # that semantics: if any tool from any group is in the successful
            # set, the node is satisfied.
            flat_any_of = set()
            for group in any_of_groups:
                flat_any_of |= group
            if successful_tool_names.intersection(flat_any_of):
                return validation
            validation.is_valid = False
            validation.errors.append(
                f"{node.node_id} must call at least one successful "
                f"task-state tool from {sorted(flat_any_of)}; task state cannot "
                "be inferred from prose."
            )
            return validation
        required = REQUIRED_TOOLS_BY_NODE.get(node.node_id)
        if node.node_id == "result_aggregation":
            store = self.root_session.task_store
            if store.root_task_id is not None and store.all_done():
                return validation
            validation.is_valid = False
            validation.errors.append(
                "result_aggregation requires an existing completed roadmap; "
                "it cannot synthesize completion from missing task state."
            )
            return validation
        if required is None or required.issubset(successful_tool_names):
            return validation
        # Executor failure reports (success=False) satisfy the structural requirement
        if node.node_id == "task_executor" and has_executor_failure_report:
            return validation
        validation.is_valid = False
        validation.errors.append(
            f"{node.node_id} must call successful task-state tool(s): "
            f"{sorted(required)}. Task state cannot be inferred from prose."
        )
        return validation

    def _should_fallback_terminal_response(
        self,
        node: Node,
        validation: ValidationResult,
    ) -> bool:
        """Return whether response exhaustion can use deterministic fallback text."""
        if node.node_id != "response":
            return False
        if any("not replay internal" in error for error in validation.errors):
            return True
        store = self.root_session.task_store
        if store.root_task_id is None:
            return False
        if not any(task.status.value == "completed" for task in store.tasks.values()):
            return False
        return any(
            "non-empty" in error or "summarize completed task outcome" in error
            for error in validation.errors
        )

    def _recover_task_assessor_validation_failure(
        self,
        node: Node,
        validation: ValidationResult,
    ) -> bool:
        """Preserve a valid assessor handoff; otherwise skip its analyzer."""
        if node.node_id != "task_assessor" or self.queue.current is not node:
            return False
        handoff = next(
            (
                item
                for item in self._pending_handoffs
                if item.source_node == node.node_id
                and item.target_node == "task_analyzer"
                and str(item.payload.get("rationale", "")).strip()
                and (
                    (
                        item.payload.get("decision") == "ready"
                        and item.payload.get("selected_task_ids") == []
                    )
                    or (
                        item.payload.get("decision") == "analyze"
                        and bool(item.payload.get("selected_task_ids"))
                    )
                )
            ),
            None,
        )
        if handoff is not None:
            self._record_node_content_transcript(
                node,
                "TaskAssessor handoff was recorded; preserving the paired analyzer.",
            )
            return True
        if len(self.queue.items) > 1 and self.queue.items[1].node_id == "task_analyzer":
            del self.queue.items[1]
        root_id = self.root_session.task_store.root_task_id
        if root_id and root_id in self.root_session.task_store.tasks:
            self.root_session.task_store.tasks[root_id].metadata[
                "assessor_recovery"
            ] = {
                "source_node_id": node.node_id,
                "errors": list(validation.errors),
                "recovery": "skip_analyzer",
                "reason": (
                    "Assessor did not record selected decomposition targets; "
                    "continuing without analyzer for this assessment pass."
                ),
            }
        self._record_node_content_transcript(
            node,
            "TaskAssessor did not record decomposition targets; skipping the "
            "paired analyzer for this pass and continuing execution lifecycle.",
        )
        return True

    def _recover_task_analyzer_validation_failure(
        self,
        node: Node,
        validation: ValidationResult,
    ) -> bool:
        """Continue autonomously with retained work after planning exhaustion."""
        if node.node_id != "task_analyzer" or self.queue.current is not node:
            return False
        root_id = self.root_session.task_store.root_task_id
        if root_id is None or root_id not in self.root_session.task_store.tasks:
            return False
        store = self.root_session.task_store
        root = self.root_session.task_store.tasks[root_id]
        handoff = self._current_analyzer_handoff(node)
        unresolved = sorted(self._unresolved_analyzer_target_ids(node))
        if handoff is not None:
            for finding in handoff.payload.get("findings", []):
                if not isinstance(finding, dict):
                    continue
                task_id = finding.get("task_id")
                task = store.tasks.get(str(task_id))
                if task is None or task_id not in unresolved:
                    continue
                advisory = {
                    "task_id": task_id,
                    "advisory": str(finding.get("finding", "")).strip(),
                    "assessment_id": finding.get("assessment_id"),
                    "analysis_budget_exhausted": True,
                }
                advisories = list(task.metadata.get("planning_advisories", []))
                next_advisories = (
                    advisories
                    if advisory in advisories
                    else [*advisories, advisory][-5:]
                )
                changed = task.metadata.pop("planning_finding", None) is not None
                if task.metadata.get("planning_advisories") != next_advisories:
                    task.metadata["planning_advisories"] = next_advisories
                    changed = True
                if changed:
                    store._bump_version()
        recovery = {
            "source_node_id": node.node_id,
            "errors": list(validation.errors),
            "recovery": "continue_execution",
            "mode": str(node.config.metadata.get("task_analyzer_mode", "")),
            "unresolved_task_ids": unresolved,
            "reason": (
                "Analyzer exhausted bounded planning attempts; continuing with "
                "retained executable work and planning advisories."
            ),
        }
        if root.metadata.get("analyzer_recovery") != recovery:
            store.update_task(root.task_id, metadata={"analyzer_recovery": recovery})
        self._record_node_content_transcript(
            node,
            "TaskAnalyzer exhausted bounded planning attempts; continuing "
            "autonomously with retained executable work.",
        )
        return True

    async def _structured_output_retry(
        self,
        node: Node,
        agent: Agent,
        resolved_tools: list[Tool],
        last_result: LLMResult,
        validation: ValidationResult,
        *,
        missing_tools: list[str] | None = None,
    ) -> tuple[LLMResult, ValidationResult] | None:
        """Structured-output retry: constrain the LLM via ``response_format: json_schema``."""
        if not missing_tools:
            return None
        # Skip for mock agents (tests) — only real LanguageModel supports
        # response_format. MagicMock auto-creates model_copy, so check type.
        from tinycua_sdk.agent.llm_model import LanguageModel

        model = getattr(getattr(agent, "config", None), "llm_model", None)
        if not isinstance(model, LanguageModel):
            return None
        # Build the json_schema from the first missing tool's parameters.
        tool_name = missing_tools[0]
        required_tool = self._resolve_recovery_tool(node, tool_name, resolved_tools)
        if required_tool is None:
            return None
        tool_params = getattr(required_tool, "parameters", {})
        # Construct the response_format json_schema. The schema wraps the
        # tool's parameters so the LLM produces the arguments object directly.
        response_format = {
            "type": "json_schema",
            "json_schema": {
                "name": tool_name,
                "schema": {
                    "type": "object",
                    "properties": tool_params.get("properties", {}),
                    "required": tool_params.get("required", []),
                    "additionalProperties": tool_params.get(
                        "additionalProperties", False
                    ),
                },
                "strict": False,
            },
        }
        # FR-060: use the same full-context message builder as _recovery_retry
        # (system prompt + continuation + task under review + outcome report +
        # roadmap + trimmed tool results). Previously sent a bare user message
        # with no context — the model had no idea what it was reviewing.
        retry_messages = self._build_recovery_messages(
            node,
            [required_tool],
            last_result,
            validation,
            missing_tools,
        )
        try:
            raw_response = await self._call_agent_llm(
                agent,
                node,
                retry_messages,
                [required_tool],
                force_required_tool=False,
                response_format=response_format,
            )
        except Exception:
            logger.debug(
                "node=%s structured_output_retry llm_call failed",
                node.node_id,
                exc_info=True,
            )
            return None

        # The LLM produced JSON arguments — wrap as a tool call and execute.
        raw_content = raw_response.get("content") or ""
        if not raw_content.strip():
            return None
        import json

        try:
            arguments = json.loads(raw_content)
        except json.JSONDecodeError:
            logger.debug(
                "node=%s structured_output_retry invalid JSON",
                node.node_id,
            )
            return None
        if not isinstance(arguments, dict):
            return None

        injected_tool_call = {
            "id": f"call_structured_{tool_name}",
            "type": "function",
            "function": {
                "name": tool_name,
                "arguments": json.dumps(arguments, default=str),
            },
        }
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
            logger.debug(
                "node=%s structured_output_retry tool exec failed",
                node.node_id,
                exc_info=True,
            )
            return None

        result = LLMResult(
            content=f"[Structured-output {tool_name} call]",
            role="assistant",
            tool_calls=[injected_tool_call],
            metadata={},
        )
        if all_tool_results:
            result.metadata = dict(result.metadata)
            result.metadata["tool_results"] = list(all_tool_results)
        result_validation = self._validate_node_result(node, result)
        if result_validation.is_valid:
            self._record_node_content_transcript(
                node,
                f"Structured-output retry succeeded — the LLM produced a valid "
                f"{tool_name} call via json_schema constraint.",
            )
            return result, result_validation
        # Return the partial result so the caller can accumulate the successful
        # tool call and advance to the next missing prerequisite. Previously
        # returned None, discarding the successful task_decompose and looping
        # forever (experiment-2: 23 cycles, pending 5→50, never terminated).
        return result, result_validation

    async def _recovery_retry(
        self,
        node: Node,
        agent: Agent,
        resolved_tools: list[Tool],
        last_result: LLMResult,
        validation: ValidationResult,
        *,
        missing_tools: list[str] | None = None,
    ) -> tuple[LLMResult, ValidationResult] | None:
        """Focused retry exposing only the missing prerequisite tools (FR-063).

        Returns (result, validation) — partial result even when validation
        fails, so the caller accumulates successful tool calls.
        """
        if missing_tools is not None and missing_tools:
            recovery_tools: list[Tool] = []
            for name in missing_tools:
                tool = self._resolve_recovery_tool(node, name, resolved_tools)
                if tool is not None:
                    recovery_tools.append(tool)
            if not recovery_tools:
                return None
        else:
            recovery_tools = list(resolved_tools)
        missing_str = (
            ", ".join(missing_tools) if missing_tools else "the required tools"
        )
        recovery_messages = self._build_recovery_messages(
            node,
            recovery_tools,
            last_result,
            validation,
            missing_tools,
        )
        try:
            raw_response = await self._call_agent_llm(
                agent, node, recovery_messages, recovery_tools
            )
        except Exception:
            logger.debug("node=%s recovery_retry failed", node.node_id, exc_info=True)
            return None
        recovery_result = LLMResult(
            content=sanitize_internal_reprs(raw_response.get("content") or ""),
            role=raw_response.get("role", "assistant"),
            tool_calls=raw_response.get("tool_calls") or [],
            metadata=raw_response.get("metadata", {}),
            reasoning=raw_response.get("reasoning", ""),
        )
        if not node.is_terminal and node.node_id != "result_aggregation":
            self._coerce_structured_tool_calls(recovery_result, recovery_tools)
        self._coerce_terminate_only_response(recovery_tools, recovery_result)
        all_tool_results: list[dict[str, Any]] = []
        if recovery_result.tool_calls:
            tool_results = await self._execute_tool_calls(
                agent, recovery_result.tool_calls, recovery_tools, node
            )
            if tool_results:
                all_tool_results.extend(tool_results)
        if all_tool_results:
            recovery_result.metadata = dict(recovery_result.metadata)
            recovery_result.metadata["tool_results"] = list(all_tool_results)
        recovery_validation = self._validate_node_result(node, recovery_result)
        if recovery_validation.is_valid:
            self._record_node_content_transcript(
                node,
                f"Recovery retry succeeded — the model called the missing tool(s) ({missing_str}) with a focused context.",
            )
            return recovery_result, recovery_validation
        # Return the partial result so the caller accumulates successful tool
        # calls and advances to the next missing prerequisite (FR-063).
        return recovery_result, recovery_validation

    def _required_tool_for_recovery(
        self, node: Node, validation: ValidationResult
    ) -> Tool | None:
        """Determine the single tool the model needs to call to satisfy validation.

        Returns the Tool object from resolved_tools that the model is missing,
        or None if no single tool can fix the validation failure. This drives
        the tightening retry — the model gets only this one tool so it can't
        pick a wrong one.
        """
        errors = "; ".join(validation.errors).lower()
        node_id = node.node_id
        # FR-061: use contract-derived recovery tool candidates.
        candidates = RECOVERY_TOOL_MAP.get(node_id, ())
        # Find which candidate is mentioned in the validation errors.
        for name in candidates:
            if name in errors:
                # Find the actual tool object in the node's resolved tools.
                resolved = getattr(node.config, "tool_policy", None)
                if resolved is not None:
                    tools = resolved.resolve_tools([])
                    for tool in tools:
                        if getattr(tool, "name", "") == name:
                            return tool
                break
        return None

    async def _tightening_retry(
        self,
        node: Node,
        agent: Agent,
        resolved_tools: list[Tool],
        last_result: LLMResult,
        validation: ValidationResult,
        *,
        missing_tools: list[str] | None = None,
    ) -> tuple[LLMResult, ValidationResult] | None:
        """Narrow to the first missing prerequisite tool with tool_choice=required.

        The model gets only one tool — the next missing prerequisite in the
        chain. It must call that tool (tool_choice=required). The model still
        decides the arguments.
        """
        from datetime import datetime

        # Determine the single tool to force: the first missing prerequisite.
        if missing_tools:
            tool_name = missing_tools[0]
            required_tool = self._resolve_recovery_tool(node, tool_name, resolved_tools)
        else:
            required_tool = self._required_tool_for_recovery(node, validation)
        if required_tool is None:
            return None  # no single tool can fix this — skip tightening

        system_msg = node.build_system_message([required_tool])
        tightening_messages: list[dict[str, Any]] = []
        if system_msg.get("content"):
            tightening_messages.append(system_msg)
        now = datetime.now().astimezone()
        tightening_messages.append(
            {
                "role": "user",
                "content": (
                    f"<context>Current time: {now:%H:%M:%S %z}, "
                    f"timezone: {now.tzname() or 'local'}</context>"
                ),
            }
        )
        errors = "; ".join(validation.errors)
        tool_name = getattr(required_tool, "name", "the required tool")
        specific_guidance = {
            "task_inspect": "Call task_inspect (no task_id) to see the compact task list.",
            "terminate": "Call terminate to end this node.",
            "task_result_update": "Call task_result_update with a concise summary of what you did and whether it succeeded.",
            "task_review_decision": (
                "Call task_review_decision with approved, needs_revision, replan, "
                "postpone_siblings, postpone_final, or compromise."
            ),
            "task_decompose": "Call task_decompose with the task_id and concrete subtasks.",
            "task_create": "Call task_create with a parent_id and missing task title.",
            "task_shrink": "Call task_shrink with a safe action and rationale.",
            "task_update": "Call task_update with the task_id and updated description.",
            "task_assessment_decision": (
                "Call task_assessment_decision with task-bound findings and "
                "advisories. Analyze needs a blocking finding; ready has none."
            ),
            "task_init": "Call task_init with a root task title derived from the request.",
        }
        guidance = specific_guidance.get(tool_name, f"Call {tool_name} now.")
        tightening_messages.append(
            {
                "role": "user",
                "content": (
                    f"The previous response did not satisfy: {errors}\n\n"
                    f"You have one tool available: {tool_name}. {guidance}\n\n"
                    f"Do not write prose — call {tool_name} now."
                ),
            }
        )
        try:
            raw_response = await self._call_agent_llm(
                agent,
                node,
                tightening_messages,
                [required_tool],
                force_required_tool=True,
            )
        except Exception:
            return None
        tightening_result = LLMResult(
            content=sanitize_internal_reprs(raw_response.get("content") or ""),
            role=raw_response.get("role", "assistant"),
            tool_calls=raw_response.get("tool_calls") or [],
            metadata=raw_response.get("metadata", {}),
            reasoning=raw_response.get("reasoning", ""),
        )
        self._coerce_structured_tool_calls(tightening_result, [required_tool])
        self._coerce_terminate_only_response([required_tool], tightening_result)
        all_tool_results: list[dict[str, Any]] = []
        if tightening_result.tool_calls:
            tool_results = await self._execute_tool_calls(
                agent,
                tightening_result.tool_calls,
                [required_tool],
                node,
            )
            if tool_results:
                all_tool_results.extend(tool_results)
        if all_tool_results:
            tightening_result.metadata = dict(tightening_result.metadata)
            tightening_result.metadata["tool_results"] = list(all_tool_results)
        tightening_validation = self._validate_node_result(node, tightening_result)
        if tightening_validation.is_valid:
            self._record_node_content_transcript(
                node,
                f"Tightening retry succeeded — the model called {tool_name} "
                f"with only that tool available.",
            )
            return tightening_result, tightening_validation
        return None

    def _stream_retry_message(
        self,
        agent: Agent,
        node: Node,
        resolved_tools: list[Tool],
        error: ValidationError,
        attempt: int,
        llm_result: LLMResult,
    ) -> str:
        """Build retry guidance for the canonical streaming path."""
        del agent, attempt
        return self._retry_message_for_validation(
            error, node, resolved_tools, llm_result
        )

    def _tool_feedback_messages(self, llm_result: LLMResult) -> list[dict[str, Any]]:
        """Return latest tool-call feedback messages for a retry attempt."""
        tool_results = llm_result.metadata.get("tool_results", [])
        normalized_tool_calls = self._normalize_tool_calls(llm_result.tool_calls)
        if not normalized_tool_calls:
            return []
        messages: list[dict[str, Any]] = []
        messages.append(
            {
                "role": "assistant",
                "content": llm_result.content,
                "tool_calls": normalized_tool_calls,
            }
        )
        messages.extend(
            self._tool_result_feedback_messages(
                [item for item in tool_results if isinstance(item, dict)],
                normalized_tool_calls,
            )
        )
        return messages

    def _response_fallback_content(self) -> str:
        """Return deterministic user-facing text when response synthesis fails."""
        store = self.root_session.task_store
        if store.root_task_id is not None and store.root_task_id in store.tasks:
            completed = [
                task
                for task in store.tasks.values()
                if task.result is not None and task.status.value == "completed"
            ]
            if completed:
                task = completed[-1]
                artifacts = [
                    artifact.get("path")
                    for artifact in task.artifacts
                    if artifact.get("path")
                ]
                suffix = f" Artifact: {artifacts[-1]}" if artifacts else ""
                return f"Done: {task.result.summary}{suffix}"
            return "I couldn't complete the request cleanly."
        user_text = self._latest_user_text().strip()
        if user_text.lower() in {"hi", "hello", "hey"}:
            return f"{user_text.capitalize()}!"
        return user_text or "Hello!"
