"""Concrete worker-mode task nodes."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from tinycua.loops.node import ProcessNode
from tinycua.models.task import AggregatedResult, ReviewerDecision, TaskResult, TaskStatus

if TYPE_CHECKING:
    from tinycua.config.types import LLMResult
    from tinycua.loops.node_queue import NodeQueue
    from tinycua.models.node_input import NodeInputLike


def _candidate_lines(content: str) -> list[str]:
    """Extract actionable subtask titles from model text."""
    titles: list[str] = []
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        line = re.sub(r"^[-*•]\s*", "", line)
        line = re.sub(r"^\d+[.)]\s*", "", line)
        if 4 <= len(line) <= 120:
            titles.append(line)
    return titles[:5]


class TinyCUATaskAnalyzerNode(ProcessNode):
    """Analyze or refine task structure."""

    def parse_loop_result(
        self,
        llm_result: LLMResult,
        node_input: NodeInputLike | None,
    ) -> None:
        """Create concrete subtasks from analysis text when none exist."""
        del node_input
        if self.session is None or self.session.task_store.root_task_id is None:
            return
        store = self.session.task_store
        root = store.tasks[store.root_task_id]
        if root.children:
            root.metadata["reanalyzed"] = True
            return
        titles = _candidate_lines(llm_result.content)
        if not titles:
            titles = [f"Plan {root.title}", f"Execute {root.title}"]
        for title in titles:
            store.create_task(title, parent_id=root.task_id)
        root.metadata["analyzed"] = True


class TinyCUATaskAssessorNode(ProcessNode):
    """Assess task readiness and progress."""

    def parse_loop_result(
        self,
        llm_result: LLMResult,
        node_input: NodeInputLike | None,
    ) -> None:
        """Mark the active task as assessed with model rationale."""
        del node_input
        if self.session is None:
            return
        active = self.session.task_store.get_active_task()
        if active is not None:
            active.metadata["assessor_rationale"] = llm_result.content


class TinyCUATaskExecutorNode(ProcessNode):
    """Execute or dispatch task work."""

    def parse_loop_result(
        self,
        llm_result: LLMResult,
        node_input: NodeInputLike | None,
    ) -> None:
        """Record the active task execution output."""
        del node_input
        if self.session is None:
            return
        store = self.session.task_store
        active = store.get_active_task()
        if active is None:
            return
        if active.status == TaskStatus.PENDING:
            store.transition(active.task_id, TaskStatus.IN_PROGRESS)
        tool_results = llm_result.metadata.get("tool_results", [])
        result_content = llm_result.content.strip() or str(tool_results)
        if result_content.strip():
            store.record_result(
                active.task_id,
                TaskResult(
                    content=result_content,
                    success=True,
                    artifacts=self._artifacts_from_tool_results(tool_results),
                    metadata={
                        "source_node_id": self.node_id,
                        "tool_results": tool_results,
                    },
                ),
            )
            for artifact in active.result.artifacts if active.result else []:
                active.artifacts.append(artifact)
            active.metadata["last_executed"] = True

    def _artifacts_from_tool_results(self, tool_results: list[dict]) -> list[dict]:
        """Extract artifact references from file-writing tool results."""
        artifacts = []
        for item in tool_results:
            output = item.get("output") if isinstance(item, dict) else None
            if item.get("name") != "write_file" or not isinstance(output, dict):
                continue
            if output.get("success") and output.get("path"):
                artifacts.append(
                    {
                        "path": output["path"],
                        "kind": "file",
                        "metadata": {"tool_name": "write_file"},
                    }
                )
        return artifacts


class TinyCUAResultReviewerNode(ProcessNode):
    """Review task execution results."""

    def _task_to_review(self):
        """Return the most recent completed task that needs review."""
        if self.session is None:
            return None
        for task in reversed(list(self.session.task_store.tasks.values())):
            if task.result is not None and not task.reviewer_decisions:
                return task
        return self.session.task_store.get_active_task()

    def parse_loop_result(
        self,
        llm_result: LLMResult,
        node_input: NodeInputLike | None,
    ) -> None:
        """Persist reviewer decision parsed from model output."""
        del node_input
        if self.session is None:
            return
        task = self._task_to_review()
        if task is None:
            return
        normalized = llm_result.content.lower()
        if "replan" in normalized:
            decision = ReviewerDecision.REPLAN
        elif "retry" in normalized or "revise" in normalized or "reject" in normalized:
            decision = ReviewerDecision.NEEDS_REVISION
        elif "question" in normalized or "clarif" in normalized:
            decision = ReviewerDecision.OPEN_QUESTION
        else:
            decision = ReviewerDecision.APPROVED
        self.session.task_store.record_reviewer_decision(
            task.task_id,
            decision,
            rationale=llm_result.content,
        )

    def on_complete(self, queue: NodeQueue, response: LLMResult) -> None:
        """Schedule retry, replan, next task, or aggregation from task state."""
        del response
        if self.session is None:
            return
        from tinycua.loops.worker_runtime import WorkerRuntimeController

        terminal_nodes = [node for node in queue.items[1:] if node.is_terminal]
        queue.clear_after_current()
        WorkerRuntimeController(self.session.task_store).schedule_after_review(queue)
        existing_terminal_ids = {node.node_id for node in queue.items if node.is_terminal}
        for terminal in terminal_nodes:
            if terminal.node_id not in existing_terminal_ids:
                queue.items.append(terminal)
                existing_terminal_ids.add(terminal.node_id)


class TinyCUAResultAggregationNode(ProcessNode):
    """Aggregate task results into worker output."""

    def parse_loop_result(
        self,
        llm_result: LLMResult,
        node_input: NodeInputLike | None,
    ) -> None:
        """Persist aggregation output on the root task."""
        del node_input
        if self.session is None or self.session.task_store.root_task_id is None:
            return
        root_id = self.session.task_store.root_task_id
        root = self.session.task_store.tasks[root_id]
        if root.status != TaskStatus.COMPLETED:
            root.status = TaskStatus.IN_PROGRESS
        root.result = TaskResult(
            content=llm_result.content or self._summarize_task_results(),
            success=True,
            metadata={"source_node_id": self.node_id},
        )
        root.status = TaskStatus.COMPLETED
        aggregated = self._build_aggregated_result(llm_result.content)
        root.metadata["aggregated_result"] = aggregated.__dict__
        from tinycua.models.session_context_entry import SessionContextEntry

        self.session.session_context.append(
            SessionContextEntry(
                content=aggregated,
                segment="output",
                source_node_id=self.node_id,
                source_session_id=self.session.session_id,
            )
        )

    def _summarize_task_results(self) -> str:
        """Summarize child task outputs for aggregation fallback content."""
        if self.session is None:
            return "Completed worker task tree."
        parts = []
        for task in self.session.task_store.tasks.values():
            if task.result is not None and task.parent_id is not None:
                parts.append(f"{task.title}: {task.result.content}")
        return "\n".join(parts) or "Completed worker task tree."

    def _build_aggregated_result(self, model_context: str) -> AggregatedResult:
        """Build a response-ready aggregation from task-tree state."""
        if self.session is None or self.session.task_store.root_task_id is None:
            return AggregatedResult(root_task_id="", final_context=model_context)
        store = self.session.task_store
        task_summaries: list[str] = []
        accepted_results: list[TaskResult] = []
        artifacts: list[dict] = []
        for task in store.tasks.values():
            if task.result is None:
                continue
            task_summaries.append(f"{task.title}: {task.result.summary}")
            accepted_results.append(task.result)
            artifacts.extend(task.artifacts)
        final_context = "\n".join(
            part for part in [model_context.strip(), *task_summaries] if part
        )
        return AggregatedResult(
            root_task_id=store.root_task_id,
            task_summaries=task_summaries,
            accepted_results=accepted_results,
            artifacts=artifacts,
            final_context=final_context,
            response_continuation="Use this aggregated result to answer the user.",
            metadata={"source_node_id": self.node_id},
        )


class TinyCUAAnalysisEffortNode(ProcessNode):
    """Determine analysis effort for worker-mode planning."""

    def parse_loop_result(
        self,
        llm_result: LLMResult,
        node_input: NodeInputLike | None,
    ) -> None:
        """Record analysis effort on the root task metadata."""
        del node_input
        if self.session is None or self.session.task_store.root_task_id is None:
            return
        root = self.session.task_store.tasks[self.session.task_store.root_task_id]
        root.metadata["analysis_effort"] = llm_result.content.strip() or "standard"
