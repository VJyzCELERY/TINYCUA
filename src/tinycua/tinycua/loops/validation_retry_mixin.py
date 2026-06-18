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

if TYPE_CHECKING:
    from tinycua.loops.node import Node
    from tinycua_sdk.agent.agent import Agent
    from tinycua_sdk.tools.decorators import Tool

logger = logging.getLogger(__name__)

class ValidationRetryMixin:
    """Mixin extracted from TinyCUALoop for modularity."""

    def _retry_message_for_validation(
        self,
        error: ValidationError,
        node: Node,
        resolved_tools: list[Tool],
        llm_result: LLMResult,
    ) -> str:
        """Build retry guidance without pretending to be a new user turn."""
        if node.node_id == "task_executor" and "task_result_update" in str(error):
            tool_results = self._tool_results_from_llm_result(llm_result)
            if self._successful_executor_action_results(tool_results):
                return (
                    "I need to call task_result_update with the observed tool "
                    "results for the active task."
                )
            return (
                "I need to use an appropriate action or research tool for the "
                "active task, then call task_result_update with that evidence."
            )
        return self._natural_retry_message(error, node, resolved_tools)

    def _messages_with_retry_prompt(
        self,
        base_messages: list[dict[str, Any]],
        retry_feedback: list[dict[str, Any]],
        retry_message: str | None,
    ) -> list[dict[str, Any]]:
        """Return base node messages, latest tool feedback, and one retry prompt."""
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
        """Convert internal retry note into an ephemeral user correction."""
        text = retry_message.replace("I need to", "You need to")
        return f"Correction for the previous response: {text}"

    def _tools_for_retry_attempt(
        self,
        node: Node,
        resolved_tools: list[Tool],
        retry_message: str | None,
    ) -> list[Tool]:
        """Narrow retry tools when validation names one required state tool."""
        required = self._retry_required_tool_name(node, retry_message)
        if required is None:
            return resolved_tools
        narrowed = [tool for tool in resolved_tools if tool.name == required]
        return narrowed or resolved_tools

    def _retry_required_tool_name(
        self,
        node: Node,
        retry_message: str | None,
    ) -> str | None:
        """Return a required tool that should be isolated for this retry."""
        if not retry_message:
            return None
        retry_required_by_node = {"task_assessor": "node_handoff"}
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
        current = [
            item for item in llm_result.metadata.get("tool_results", [])
            if isinstance(item, dict)
        ]
        llm_result.metadata["tool_results"] = [*retry_tool_results, *current]

    def _tool_results_from_llm_result(
        self,
        llm_result: LLMResult,
    ) -> list[dict[str, Any]]:
        """Return successful/failed tool result records carried by an LLM result."""
        return [
            item for item in llm_result.metadata.get("tool_results", [])
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

    def _route_task_executor_failure_to_reviewer(
        self,
        node: Node,
        validation: ValidationResult,
        llm_result: LLMResult,
    ) -> bool:
        """TaskExecutor validation failures are not reviewer-owned results."""
        del node, validation, llm_result
        return False

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
            terminal_nodes = [queued for queued in self.queue.items[1:] if queued.is_terminal]
            self.queue.clear_after_current()
            from tinycua.config.node_config import create_node_config
            from tinycua.loops.task_nodes import TinyCUAResultReviewerNode
            from tinycua.loops.task_nodes import TinyCUATaskExecutorNode

            self.queue.items.extend(
                [
                    TinyCUATaskExecutorNode(
                        node_id="task_executor",
                        config=create_node_config("task_executor"),
                    ),
                    TinyCUAResultReviewerNode(
                        node_id="result_reviewer",
                        config=create_node_config("result_reviewer"),
                    ),
                ]
            )
            existing_terminal_ids = {
                queued.node_id for queued in self.queue.items if queued.is_terminal
            }
            for terminal in terminal_nodes:
                if terminal.node_id not in existing_terminal_ids:
                    self.queue.items.append(terminal)
                    existing_terminal_ids.add(terminal.node_id)
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
        terminal_nodes = [queued for queued in self.queue.items[1:] if queued.is_terminal]
        self.queue.clear_after_current()
        from tinycua.config.node_config import create_node_config
        from tinycua.loops.task_nodes import TinyCUAResultReviewerNode
        from tinycua.loops.task_nodes import TinyCUATaskExecutorNode

        self.queue.items.extend(
            [
                TinyCUATaskExecutorNode(
                    node_id="task_executor",
                    config=create_node_config("task_executor"),
                ),
                TinyCUAResultReviewerNode(
                    node_id="result_reviewer",
                    config=create_node_config("result_reviewer"),
                ),
            ]
        )
        existing_terminal_ids = {
            queued.node_id for queued in self.queue.items if queued.is_terminal
        }
        for terminal in terminal_nodes:
            if terminal.node_id not in existing_terminal_ids:
                self.queue.items.append(terminal)
                existing_terminal_ids.add(terminal.node_id)
        return True

    def _validation_failure_content(
        self,
        node: Node,
        validation: ValidationResult,
    ) -> str:
        """Build a visible failure response from runtime validation errors."""
        errors = "; ".join(validation.errors) or "unknown validation failure"
        return (
            f"TinyCUA could not complete the request because {node.node_id} "
            f"failed runtime validation: {errors}"
        )

    def _effective_max_attempts(self, node: Node) -> int:
        """Return bounded retry attempts for the loop-owned call path."""
        retry_policy = node.config.retry_policy
        if retry_policy.max_attempts is None:
            return _UNBOUNDED_RETRY_ATTEMPTS
        return max(retry_policy.max_attempts, 1)

    def _natural_retry_message(
        self,
        error: ValidationError,
        node: Node,
        resolved_tools: list[Tool],
    ) -> str:
        """Build an assistant self-correction retry continuation."""
        del resolved_tools
        error_text = str(error)
        if (
            node.node_id == "task_analyzer"
            and "task_decompose" in error_text
            and "task_update" in error_text
        ):
            return (
                "I need to call task_decompose if the task tree needs structural "
                "changes, or task_update if no further decomposition is useful."
            )
        required = self._missing_or_required_tool_name(node, error_text)
        if required:
            return (
                f"I need to call {required} with the current evidence before continuing."
            )
        return (
            f"I need to correct this response before continuing: {error!s}"
        )

    def _structured_tool_retry_message(
        self,
        error: ValidationError,
        node: Node,
        resolved_tools: list[Tool],
    ) -> str:
        """Build a JSON-protocol retry instruction without prose framing."""
        protocol_tools = self._structured_tool_protocol_tools(node, resolved_tools)
        return (
            f"I need to use the available tool correctly before continuing: {error!s}. "
            "My next "
            "response must be ONLY strict JSON matching the tool-call protocol: "
            '{"tool_calls":[{"name":"tool_name","arguments":{}}]}. '
            "Choose one or more valid tools and arguments from these available "
            f"tools: {', '.join(tool.name for tool in protocol_tools)}."
        )

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
            self._validate_result_reviewer_failed_approval(node, llm_result),
            self._validate_result_reviewer_result_exists(node, llm_result),
            self._validate_result_reviewer_must_inspect(node, llm_result),
            self._validate_final_response_content(node, llm_result),
        ):
            if not extra_validation.is_valid:
                validation.is_valid = False
                validation.errors.extend(extra_validation.errors)
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
        tool_results = [
            item for item in llm_result.metadata.get("tool_results", [])
            if isinstance(item, dict)
        ]
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
                "needs_revision, rejected, or replan after "
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
        tool_results = [
            item for item in llm_result.metadata.get("tool_results", [])
            if isinstance(item, dict)
        ]
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
        if not isinstance(task_id, str) or task_id not in self.root_session.task_store.tasks:
            return validation
        task = self.root_session.task_store.tasks[task_id]
        if task.result is not None and task.result.content.strip():
            return validation
        self._rollback_invalid_reviewer_approval(task_id)
        validation.is_valid = False
        validation.errors.append(
            "ResultReviewer cannot approve a task with no outcome report. "
            "The executor must call task_result_update with a non-empty result. "
            "Choose needs_revision to retry execution."
        )
        return validation

    def _validate_result_reviewer_must_inspect(
        self,
        node: Node,
        llm_result: LLMResult,
    ) -> ValidationResult:
        """Require task_inspect before reviewer makes a decision."""
        validation = ValidationResult(is_valid=True, errors=[])
        if node.node_id != "result_reviewer":
            return validation
        tool_results = [
            item for item in llm_result.metadata.get("tool_results", [])
            if isinstance(item, dict)
        ]
        # Check that task_inspect was called
        has_inspect = any(
            item.get("name") == "task_inspect"
            and isinstance(item.get("output"), dict)
            for item in tool_results
        )
        if has_inspect:
            return validation
        # No task_inspect — reject unless the reviewer decided not to approve
        decision_result = None
        for item in reversed(tool_results):
            if item.get("name") == "task_review_decision":
                output = item.get("output")
                if isinstance(output, dict):
                    decision_result = output
                    break
        if decision_result and decision_result.get("decision") != "approved":
            # Non-approval decisions without inspect are acceptable
            # (e.g., needs_revision, rejected, replan based on obvious failure)
            return validation
        self._rollback_invalid_reviewer_approval(
            decision_result.get("task_id", "") if decision_result else ""
        )
        validation.is_valid = False
        validation.errors.append(
            "ResultReviewer must call task_inspect to review task state "
            "before making a decision. Inspect the task tree first."
        )
        return validation

    def _rollback_invalid_reviewer_approval(self, task_id: str) -> None:
        """Undo reviewer approval side effects when runtime validation rejects it."""
        task = self.root_session.task_store.tasks.get(task_id)
        if task is None:
            return
        from tinycua.models.task import TaskStatus

        if task.reviewer_decisions and task.reviewer_decisions[-1].get("decision") == "approved":
            task.reviewer_decisions.pop()
        if task.status.value == "completed":
            task.status = TaskStatus.IN_PROGRESS
        parent_id = task.parent_id
        while parent_id is not None:
            parent = self.root_session.task_store.tasks.get(parent_id)
            if parent is None:
                break
            has_unfinished_child = any(
                self.root_session.task_store.tasks[child_id].status != TaskStatus.COMPLETED
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
        content = llm_result.content.strip()
        if not content:
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
        store = self.root_session.task_store
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
        if (
            store.root_task_id is not None
            and not store.all_done()
        ):
            validation.is_valid = False
            validation.errors.append(
                "Final response cannot synthesize success before every task in "
                "the worker task tree is actually completed. Failed tasks must "
                "be retried or locally replanned before terminal response."
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
            return self._tool_results_include(llm_result, "node_handoff")
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
        """Validate that TaskExecutor performed work through tools and left a result."""
        validation = ValidationResult(is_valid=True, errors=[])
        if node.node_id != "task_executor":
            return validation
        tool_results = [item for item in llm_result.metadata.get("tool_results", []) if isinstance(item, dict)]
        if not tool_results:
            validation.is_valid = False
            validation.errors.append(
                "TaskExecutor must use tools to execute, inspect, verify, record a "
                "result, or report a blocked state; do not return a plan-only answer."
            )
            return validation
        # Require that task_result_update was called
        result_update_calls = [
            item for item in tool_results
            if item.get("name") == "task_result_update"
            and isinstance(item.get("output"), dict)
        ]
        if not result_update_calls:
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
        # Executor failure reports (success=False) are valid blocker signals for reviewer/replan
        has_executor_failure_report = any(
            isinstance(item, dict)
            and item.get("name") == "task_result_update"
            and isinstance(item.get("output"), dict)
            and item["output"].get("success") is False
            for item in tool_results
        )
        required_by_node = {
            "task_create": {"task_init"},
            "task_executor": {"task_result_update"},
            "result_reviewer": {"task_review_decision"},
        }
        any_of_by_node = {
            "task_analyzer": {"task_decompose", "task_update"},
            "task_assessor": {"node_handoff"},
        }
        any_of = any_of_by_node.get(node.node_id)
        if any_of is not None:
            if successful_tool_names.intersection(any_of):
                return validation
            validation.is_valid = False
            validation.errors.append(
                f"{node.node_id} must call at least one successful "
                f"task-state tool from {sorted(any_of)}; task state cannot "
                "be inferred from prose."
            )
            return validation
        required = required_by_node.get(node.node_id)
        if node.node_id == "result_aggregation":
            store = self.root_session.task_store
            if store.root_task_id is not None and store.all_done():
                return validation
            validation.is_valid = False
            validation.errors.append(
                "result_aggregation requires an existing completed task tree; "
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
        """Skip analyzer when assessor cannot select decomposition targets."""
        if node.node_id != "task_assessor" or self.queue.current is not node:
            return False
        if len(self.queue.items) > 1 and self.queue.items[1].node_id == "task_analyzer":
            del self.queue.items[1]
        root_id = self.root_session.task_store.root_task_id
        if root_id and root_id in self.root_session.task_store.tasks:
            self.root_session.task_store.tasks[root_id].metadata["assessor_recovery"] = {
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
        """Skip an optional analyzer pass only when the tree can already execute.

        Generic, content-free recovery: if the root task already has children,
        the analyzer missed its tool call but the task tree is executable, so
        record the miss and continue. If the root has NO children, the analyzer
        must not be short-circuited — fail closed so the node can retry its
        required contract. The runtime must never fabricate tasks, prompt-class
        decompositions, or hardcoded titles here (spec FR-015/FR-018).
        """
        if node.node_id != "task_analyzer" or self.queue.current is not node:
            return False
        root_id = self.root_session.task_store.root_task_id
        if root_id is None or root_id not in self.root_session.task_store.tasks:
            return False
        root = self.root_session.task_store.tasks[root_id]
        if not root.children:
            # No decomposition exists; the analyzer must satisfy its own
            # contract. Do not fabricate a vertical slice or any task content.
            return False
        root.metadata["analyzer_recovery"] = {
            "source_node_id": node.node_id,
            "errors": list(validation.errors),
            "recovery": "skip_analyzer",
            "reason": (
                "Analyzer did not record additional decomposition or metadata; "
                "continuing with the existing task tree."
            ),
        }
        self._record_node_content_transcript(
            node,
            "TaskAnalyzer did not record additional task-state changes; "
            "continuing with the existing task tree.",
        )
        return True

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
        return self._retry_message_for_validation(error, node, resolved_tools, llm_result)

    def _append_tool_feedback_messages(
        self,
        messages: list[dict[str, Any]],
        llm_result: LLMResult,
    ) -> None:
        """Append assistant tool calls and tool results for streamed retries."""
        messages.extend(self._tool_feedback_messages(llm_result))

    def _tool_feedback_messages(self, llm_result: LLMResult) -> list[dict[str, Any]]:
        """Return latest tool-call feedback messages for a retry attempt."""
        tool_results = llm_result.metadata.get("tool_results", [])
        normalized_tool_calls = self._normalize_tool_calls(llm_result.tool_calls)
        if not normalized_tool_calls and not tool_results:
            return []
        messages: list[dict[str, Any]] = []
        if normalized_tool_calls:
            messages.append(
                {
                    "role": "assistant",
                    "content": llm_result.content,
                    "tool_calls": normalized_tool_calls,
                }
            )
        for index, tool_result in enumerate(tool_results):
            if not isinstance(tool_result, dict):
                continue
            tool_call = (
                normalized_tool_calls[index]
                if index < len(normalized_tool_calls)
                else {}
            )
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.get("id")
                    or str(tool_result.get("name", "")),
                    "name": str(tool_result.get("name", "")),
                    "content": json.dumps(tool_result, default=str),
                }
            )
        return messages

    def _response_fallback_content(self) -> str:
        """Return deterministic user-facing text when response synthesis fails."""
        store = self.root_session.task_store
        if store.root_task_id is not None and store.root_task_id in store.tasks:
            completed = [
                task for task in store.tasks.values()
                if task.result is not None and task.status.value == "completed"
            ]
            if completed:
                task = completed[-1]
                artifacts = [artifact.get("path") for artifact in task.artifacts if artifact.get("path")]
                suffix = f" Artifact: {artifacts[-1]}" if artifacts else ""
                return f"Done: {task.result.summary}{suffix}"
            return "I couldn't complete the request cleanly."
        user_text = self._latest_user_text().strip()
        if user_text.lower() in {"hi", "hello", "hey"}:
            return f"{user_text.capitalize()}!"
        return user_text or "Hello!"
