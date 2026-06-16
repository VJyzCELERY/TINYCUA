"""Concrete worker-mode task nodes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tinycua.config.node_config import create_node_config
from tinycua.config.types import LLMResult
from tinycua.loops.node import ProcessNode
from tinycua.models.task import (
    AggregatedResult,
    TaskResult,
    TaskStatus,
)

if TYPE_CHECKING:
    from tinycua.config.node_config import NodeConfigBase
    from tinycua.loops.node_queue import NodeQueue
    from tinycua.models.node_input import NodeInputLike
    from tinycua.models.session import Session


_TASK_ANALYZER_INSTRUCTION = (
    "You are the TaskAnalyzer. Convert the request into concrete, actionable "
    "tasks. Prefer tasks that can be verified by files, commands, tests, or "
    "search results. Inspect the task tree, then use task_decompose or "
    "task_update to mutate task structure/metadata when analysis changes the "
    "tree. Do not repeat upstream context verbatim and do not return opaque "
    "mutation instructions as prose."
)
_TASK_ANALYZER_CONTINUATION = (
    "Based on the current digested information or focused task context above, "
    "call task_inspect first. If the active/root task needs decomposition, "
    "call task_decompose with concrete sequential subtasks chosen from the "
    "request. If no further decomposition is useful, call task_update to record "
    "that assessment on the relevant task."
)

_TASK_ASSESSOR_UPFRONT_INSTRUCTION = (
    "You are the TaskAssessor for the upfront analysis-effort decomposition loop. "
    "Inspect the whole task tree and select unfinished tasks that are complex "
    "enough to warrant further decomposition. Do not execute tasks and do not "
    "discuss execution tools. Use task_inspect and "
    "task_update only for assessment metadata or selected decomposition targets. "
    "Be concise and do not repeat upstream context."
)
_TASK_ASSESSOR_UPFRONT_CONTINUATION = (
    "Based on the whole task tree above, assess decomposition readiness across "
    "the tree. Use task_update to record assessment metadata such as selected "
    "task IDs for further decomposition, indivisible tasks, blocked planning "
    "gaps, or that no further upfront decomposition is useful."
)
_TASK_ASSESSOR_LOCAL_REPLAN_INSTRUCTION = (
    "You are the TaskAssessor for a ResultReviewer-requested local replan. "
    "Inspect the active task and nearby task-tree context to decide whether "
    "that local region needs refinement before execution continues. Do not "
    "reassess the whole roadmap, do not execute tasks, and do not discuss "
    "execution tools. Use task_inspect and task_update only for local assessment "
    "metadata or selected decomposition targets."
)
_TASK_ASSESSOR_LOCAL_REPLAN_CONTINUATION = (
    "Based on the active task and local task-tree region above, assess whether "
    "the reviewed task needs local decomposition or planning metadata updates. "
    "Use task_update to record the local assessment, selected decomposition "
    "target, blocked planning gap, or that no local replan is useful."
)

_TASK_EXECUTOR_INSTRUCTION = (
    "You are the TaskExecutor. You MUST use tools when the active task requires "
    "workspace action, research, file creation, command execution, or testing. "
    "Use write_file/read_file/list_files/run_shell/run_python/web_search as "
    "needed. Start by marking execution with task_execute when an active task "
    "exists. After observing action/research/tool evidence, you MUST call "
    "task_result_update to record the actual result. Do not only provide a "
    "plan for actionable tasks."
)
_TASK_EXECUTOR_CONTINUATION = (
    "Based on the active task above, perform the required workspace or research "
    "actions with tools. Do not only provide a plan; create, inspect, run, or "
    "verify artifacts when the task requires action. Then call "
    "task_result_update with a concise evidence-backed result."
)

_RESULT_REVIEWER_INSTRUCTION = (
    "You are the ResultReviewer. Review the latest task result against the "
    "requested outcome and tool evidence. You MUST call task_review_decision "
    "with approved, needs_revision, rejected, replan, or open_question plus a "
    "brief rationale. Do not infer review state from prose-only output and do "
    "not repeat upstream context."
)
_RESULT_REVIEWER_CONTINUATION = (
    "Based on the latest task result and execution evidence above, call "
    "task_review_decision with approved, needs_revision, rejected, replan, or "
    "open_question and a brief reason."
)

_RESULT_AGGREGATION_INSTRUCTION = (
    "You are the ResultAggregation node. Summarize completed task results, "
    "artifacts, and verification evidence concisely. Do not include Python reprs "
    "or duplicate upstream context."
)
_RESULT_AGGREGATION_CONTINUATION = (
    "Based on accepted task results above, aggregate the Worker result into "
    "concise response-ready context with artifacts and verification evidence."
)

_ANALYSIS_EFFORT_INSTRUCTION = "Deterministic effort controller. No LLM call required."
_ANALYSIS_EFFORT_CONTINUATION = ""


class TinyCUATaskAnalyzerNode(ProcessNode):
    """Analyze or refine task structure."""

    def __init__(
        self,
        node_id: str,
        config: NodeConfigBase,
        *,
        instruction: str = _TASK_ANALYZER_INSTRUCTION,
        is_terminal: bool = False,
    ) -> None:
        """Initialize the task analyzer node."""
        super().__init__(
            node_id,
            config,
            instruction=instruction,
            continuation=_TASK_ANALYZER_CONTINUATION,
            is_terminal=is_terminal,
        )

    def build_continuation(self, session: Session | None = None) -> str:
        """Build analyzer continuation with current task snapshot."""
        base = super().build_continuation(session)
        if session is None:
            return base
        return f"Task snapshot: {session.task_store.snapshot()}\n\n{base}"


class TinyCUATaskAssessorNode(ProcessNode):
    """Assess the task tree for decomposition readiness."""

    def __init__(
        self,
        node_id: str,
        config: NodeConfigBase,
        *,
        instruction: str | None = None,
        is_terminal: bool = False,
    ) -> None:
        """Initialize the task assessor node."""
        mode = str(config.metadata.get("task_assessor_mode", "upfront_decomposition"))
        if instruction is None:
            instruction = (
                _TASK_ASSESSOR_LOCAL_REPLAN_INSTRUCTION
                if mode == "local_replan"
                else _TASK_ASSESSOR_UPFRONT_INSTRUCTION
            )
        continuation = (
            _TASK_ASSESSOR_LOCAL_REPLAN_CONTINUATION
            if mode == "local_replan"
            else _TASK_ASSESSOR_UPFRONT_CONTINUATION
        )
        super().__init__(
            node_id,
            config,
            instruction=instruction,
            continuation=continuation,
            is_terminal=is_terminal,
        )

    def build_continuation(self, session: Session | None = None) -> str:
        """Build assessor continuation with the full task-tree snapshot."""
        base = super().build_continuation(session)
        if session is None:
            return base
        snapshot = session.task_store.snapshot()
        mode = str(self.config.metadata.get("task_assessor_mode", "upfront_decomposition"))
        if mode == "local_replan":
            active = session.task_store.get_active_task()
            return (
                "Local task-tree region for reviewer-requested replan:\n"
                f"Active task: {getattr(active, 'task_id', None)} — "
                f"{getattr(active, 'title', 'None')}\n"
                f"Task tree snapshot: {snapshot}\n\n{base}"
            )
        return (
            f"Whole task tree snapshot for decomposition assessment: {snapshot}\n\n"
            f"{base}"
        )

class TinyCUATaskExecutorNode(ProcessNode):
    """Execute or dispatch task work."""

    def __init__(
        self,
        node_id: str,
        config: NodeConfigBase,
        *,
        instruction: str = _TASK_EXECUTOR_INSTRUCTION,
        is_terminal: bool = False,
    ) -> None:
        """Initialize the task executor node."""
        super().__init__(
            node_id,
            config,
            instruction=instruction,
            continuation=_TASK_EXECUTOR_CONTINUATION,
            is_terminal=is_terminal,
        )

    def build_continuation(self, session: Session | None = None) -> str:
        """Build executor continuation with active task and shallow roadmap."""
        base = super().build_continuation(session)
        if session is None:
            return base
        active = session.task_store.get_active_task()
        if active is None:
            return base
        shallow = [
            {
                "task_id": task.task_id,
                "title": task.title,
                "status": task.status.value,
                "artifacts": task.artifacts,
            }
            for task in session.task_store.tasks.values()
        ]
        completed_context = []
        for task in session.task_store.tasks.values():
            if task.result is None or task.task_id == active.task_id:
                continue
            completed_context.append(
                {
                    "task_id": task.task_id,
                    "title": task.title,
                    "status": task.status.value,
                    "result": task.result.summary,
                    "success": task.result.success,
                    "artifacts": task.artifacts or task.result.artifacts,
                    "reviewer_decisions": task.reviewer_decisions,
                }
            )
        return (
            f"Active task: {active.task_id} — {active.title}\n"
            f"Task description: {active.description}\n"
            f"Prior completed/reviewed task context: {completed_context}\n"
            f"Shallow roadmap: {shallow}\n\n{base}"
        )

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

    def __init__(
        self,
        node_id: str,
        config: NodeConfigBase,
        *,
        instruction: str = _RESULT_REVIEWER_INSTRUCTION,
        is_terminal: bool = False,
    ) -> None:
        """Initialize the result reviewer node."""
        super().__init__(
            node_id,
            config,
            instruction=instruction,
            continuation=_RESULT_REVIEWER_CONTINUATION,
            is_terminal=is_terminal,
        )

    def build_continuation(self, session: Session | None = None) -> str:
        """Build reviewer continuation with latest task result evidence."""
        base = super().build_continuation(session)
        if session is None:
            return base
        task = self._task_to_review()
        if task is None:
            return base
        result = task.result.content if task.result is not None else "No result yet."
        return (
            f"Task under review: {task.task_id} — {task.title}\n"
            f"Task status: {task.status.value}\n"
            f"Task result: {result}\n"
            f"Artifacts: {task.artifacts}\n\n{base}"
        )

    def _task_to_review(self):
        """Return the most recent completed task that needs review."""
        if self.session is None:
            return None
        for task in reversed(list(self.session.task_store.tasks.values())):
            if task.result is not None and not task.reviewer_decisions:
                return task
        return self.session.task_store.get_active_task()

    def on_complete(self, queue: NodeQueue, response: LLMResult) -> None:
        """Schedule retry, replan, next task, or aggregation from task state."""
        del response
        if self.session is None:
            return
        from tinycua.loops.worker_runtime import WorkerRuntimeController

        terminal_nodes = [node for node in queue.items[1:] if node.is_terminal]
        queue.clear_after_current()
        WorkerRuntimeController(self.session.task_store).schedule_after_review(queue)
        existing_terminal_ids = {
            node.node_id for node in queue.items if node.is_terminal
        }
        for terminal in terminal_nodes:
            if terminal.node_id not in existing_terminal_ids:
                queue.items.append(terminal)
                existing_terminal_ids.add(terminal.node_id)

    def parse_loop_result(
        self,
        llm_result: LLMResult,
        node_input: NodeInputLike | None,
    ) -> None:
        """Publish reviewer-approved context for subsequent worker nodes."""
        del node_input
        if self.session is None:
            return
        task = self._reviewed_task_from_result(llm_result)
        if task is None or task.result is None or not task.reviewer_decisions:
            return
        latest = task.reviewer_decisions[-1]
        task.metadata["latest_review_context"] = {
            "decision": latest.get("decision"),
            "rationale": latest.get("rationale"),
            "result_summary": task.result.summary,
            "success": task.result.success,
            "artifacts": task.artifacts or task.result.artifacts,
        }
        from tinycua.models.session_context_entry import SessionContextEntry

        self.session.session_context.append(
            SessionContextEntry(
                content={
                    "type": "reviewed_task_context",
                    "task_id": task.task_id,
                    "title": task.title,
                    "status": task.status.value,
                    "decision": latest.get("decision"),
                    "rationale": latest.get("rationale"),
                    "result": task.result.summary,
                    "success": task.result.success,
                    "artifacts": task.artifacts or task.result.artifacts,
                },
                segment="output",
                source_node_id=self.node_id,
                source_session_id=self.session.session_id,
            )
        )

    def _reviewed_task_from_result(self, llm_result: LLMResult):
        """Return the task referenced by task_review_decision tool output."""
        if self.session is None:
            return None
        for item in reversed(llm_result.metadata.get("tool_results", [])):
            if item.get("name") != "task_review_decision":
                continue
            output = item.get("output")
            if not isinstance(output, dict):
                continue
            task_id = output.get("task_id")
            if isinstance(task_id, str) and task_id in self.session.task_store.tasks:
                return self.session.task_store.tasks[task_id]
        return self._task_to_review()


class TinyCUAResultAggregationNode(ProcessNode):
    """Aggregate task results into worker output."""

    def __init__(
        self,
        node_id: str,
        config: NodeConfigBase,
        *,
        instruction: str = _RESULT_AGGREGATION_INSTRUCTION,
        is_terminal: bool = False,
    ) -> None:
        """Initialize the result aggregation node."""
        super().__init__(
            node_id,
            config,
            instruction=instruction,
            continuation=_RESULT_AGGREGATION_CONTINUATION,
            is_terminal=is_terminal,
        )

    def build_continuation(self, session: Session | None = None) -> str:
        """Build aggregation continuation with completed task evidence."""
        base = super().build_continuation(session)
        if session is None:
            return base
        task_summaries = []
        for task in session.task_store.tasks.values():
            if task.result is None:
                continue
            task_summaries.append(
                {
                    "task_id": task.task_id,
                    "title": task.title,
                    "status": task.status.value,
                    "result": task.result.content,
                    "artifacts": task.artifacts,
                    "reviewer_decisions": task.reviewer_decisions,
                }
            )
        return f"Completed task evidence: {task_summaries}\n\n{base}"

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
        store = self.session.task_store
        if not store.all_done():
            return
        root = store.tasks[root_id]
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
        """Summarize child task outputs for aggregation content."""
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

    def __init__(
        self,
        node_id: str,
        config: NodeConfigBase,
        *,
        instruction: str = _ANALYSIS_EFFORT_INSTRUCTION,
        is_terminal: bool = False,
        pass_count: int = 0,
        pass_limit: int | None = None,
    ) -> None:
        """Initialize the analysis effort node."""
        super().__init__(
            node_id,
            config,
            instruction=instruction,
            continuation=_ANALYSIS_EFFORT_CONTINUATION,
            is_terminal=is_terminal,
        )
        self.pass_count = pass_count
        self.pass_limit = pass_limit

    def _configured_pass_limit(self) -> int:
        """Return pass limit from explicit value or session worker effort."""
        if self.pass_limit is not None:
            return self.pass_limit
        effort = "medium"
        if self.session is not None and self.session.session_config is not None:
            effort = getattr(self.session.session_config, "worker_effort", "medium")
        return {"none": 0, "low": 1, "medium": 2, "high": 3}.get(
            str(effort),
            2,
        )

    def run_deterministic(self, queue: NodeQueue) -> LLMResult:
        """Schedule documented effort passes without an LLM call."""
        pass_limit = self._configured_pass_limit()
        if self.session is not None and self.session.task_store.root_task_id is not None:
            root = self.session.task_store.tasks[self.session.task_store.root_task_id]
            root.metadata["analysis_effort_pass_limit"] = pass_limit
            root.metadata["analysis_effort_pass_count"] = self.pass_count

        if self.pass_count < pass_limit:
            next_effort = TinyCUAAnalysisEffortNode(
                node_id="analysis_effort",
                config=create_node_config("analysis_effort", self.config),
                pass_count=self.pass_count + 1,
                pass_limit=pass_limit,
            )
            queue.spawn_after_current(
                [
                    TinyCUATaskAssessorNode(
                        node_id="task_assessor",
                        config=create_node_config("task_assessor", self.config),
                    ),
                    TinyCUATaskAnalyzerNode(
                        node_id="task_analyzer",
                        config=create_node_config(
                            "task_analyzer",
                            self.config,
                            mode="effort_loop_decomposition",
                        ),
                    ),
                    next_effort,
                ]
            )
            content = (
                "Scheduled analysis effort pass "
                f"{self.pass_count + 1} of {pass_limit}."
            )
        else:
            content = f"Analysis effort complete after {pass_limit} pass(es)."

        return LLMResult(content=content, role="assistant")
