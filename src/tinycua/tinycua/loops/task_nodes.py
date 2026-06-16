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
    "request. Do not repeatedly decompose a task that already has children; "
    "for local replan, refine only the active task or its local children. If no "
    "further decomposition is useful, call task_update to record that assessment "
    "on the relevant task."
)
_TASK_ANALYZER_LOCAL_REPLAN_CONTINUATION = (
    "Based on the active task region above, refine only that local region if "
    "the reviewer/runtime evidence shows the task is too broad, ambiguous, or "
    "blocked. Do not decompose the root roadmap from a local replan. If the "
    "active task already has adequate children or can continue execution, call "
    "task_update to record that local assessment."
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
    "task_result_update with a concise evidence-backed result. If inspection "
    "shows the task cannot be completed as written, call task_result_update "
    "with success=false and the concrete blocker/evidence so ResultReviewer can "
    "retry or replan; do not keep repeating read/list inspection."
)

_RESULT_REVIEWER_INSTRUCTION = (
    "You are the ResultReviewer. Review the latest task result against the "
    "requested outcome, tool evidence, and unified task-tree context. Read the "
    "whole task context before deciding so useful completed-work information can "
    "inform unfinished future tasks. When artifacts or paths are involved, use "
    "read-only inspection tools such as task_inspect, list_files, or read_file "
    "before approving. Treat duplicate scripts, misplaced files, nested accidental "
    "workspace paths, unsupported claims, or incomplete implementation as quality "
    "gate failures that require needs_revision, rejected, or replan. You MUST call "
    "task_review_decision with approved, needs_revision, rejected, replan, or "
    "open_question plus a brief rationale. Do not infer review state from "
    "prose-only output and do not repeat upstream context. Never rewrite completed "
    "tasks."
)
_RESULT_REVIEWER_CONTINUATION = (
    "Based on the latest task result, execution evidence, and unified task "
    "context above, inspect relevant artifacts/paths when present, then call "
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
        mode = str(config.metadata.get("task_analyzer_mode", "task_creation"))
        continuation = (
            _TASK_ANALYZER_LOCAL_REPLAN_CONTINUATION
            if mode == "local_replan"
            else _TASK_ANALYZER_CONTINUATION
        )
        super().__init__(
            node_id,
            config,
            instruction=instruction,
            continuation=continuation,
            is_terminal=is_terminal,
        )

    def build_continuation(self, session: Session | None = None) -> str:
        """Build analyzer continuation with current task snapshot."""
        base = super().build_continuation(session)
        if session is None:
            return base
        mode = str(self.config.metadata.get("task_analyzer_mode", "task_creation"))
        if mode == "local_replan":
            region = _local_task_region(session)
            return f"Local task region for replan: {region}\n\n{base}"
        return f"Task snapshot: {_task_context_snapshot(session)}\n\n{base}"


def _local_task_region(session: Session) -> dict:
    """Return a compact active-task region for local replan prompts."""
    store = session.task_store
    active = store.get_active_task()
    if active is None:
        return {"active_task": None, "children": [], "siblings": []}
    children = [store.tasks[child_id] for child_id in active.children]
    siblings = []
    if active.parent_id and active.parent_id in store.tasks:
        parent = store.tasks[active.parent_id]
        siblings = [
            store.tasks[child_id]
            for child_id in parent.children
            if child_id != active.task_id and child_id in store.tasks
        ]
    return {
        "active_task": {
            "task_id": active.task_id,
            "title": active.title,
            "status": active.status.value,
            "description": active.description,
            "metadata": active.metadata,
            "result": active.result.summary if active.result else None,
            "reviewer_decisions": active.reviewer_decisions,
        },
        "children": [
            {
                "task_id": task.task_id,
                "title": task.title,
                "status": task.status.value,
            }
            for task in children
        ],
        "siblings": [
            {
                "task_id": task.task_id,
                "title": task.title,
                "status": task.status.value,
            }
            for task in siblings
        ],
    }


def _task_context_snapshot(session: Session) -> dict:
    """Return unified task context without stale unfinished parent aggregates."""
    snapshot = session.task_store.snapshot()
    tasks = snapshot.get("tasks", {})
    if not isinstance(tasks, dict):
        return snapshot
    for task_data in tasks.values():
        if not isinstance(task_data, dict):
            continue
        if task_data.get("children") and task_data.get("status") != "completed":
            task_data["result"] = None
    return snapshot


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
        snapshot = _task_context_snapshot(session)
        mode = str(self.config.metadata.get("task_assessor_mode", "upfront_decomposition"))
        if mode == "local_replan":
            return (
                "Local task-tree region for reviewer-requested replan:\n"
                f"{_local_task_region(session)}\n\n{base}"
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
        """Build executor continuation with active task and unified context."""
        base = super().build_continuation(session)
        if session is None:
            return base
        active = session.task_store.get_active_task()
        if active is None:
            return base
        workspace_dir = None
        if session.session_config is not None and session.session_config.workspace_dir:
            workspace_dir = str(session.session_config.workspace_dir)
        return (
            f"Active task: {active.task_id} — {active.title}\n"
            f"Task description: {active.description}\n"
            f"Workspace root: {workspace_dir or 'not configured'}\n"
            "Path discipline: use paths inside the workspace root. Prefer "
            "relative paths such as 'templates/index.html' or "
            "'static/css/style.css'; do not use filesystem-root absolute paths "
            "like '/templates/index.html'. Shell discipline: commands run under "
            "/bin/sh; do not rely on shell-specific brace expansion such as "
            "'mkdir -p {a,b}', because it may create a literal brace-named "
            "directory. Use explicit POSIX-safe paths/commands instead.\n"
            f"Unified task context: {_task_context_snapshot(session)}\n\n{base}"
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
        """Build reviewer continuation with latest result and unified context."""
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
            f"Artifacts: {task.artifacts}\n"
            f"Unified task context: {_task_context_snapshot(session)}\n\n{base}"
        )

    def _task_to_review(self):
        """Return the most recent completed task that needs review."""
        if self.session is None:
            return None
        active = self.session.task_store.get_active_task()
        if active is not None and active.result is not None:
            return active
        for task in reversed(list(self.session.task_store.tasks.values())):
            if task.children:
                continue
            if task.result is not None and not task.reviewer_decisions:
                return task
        return active

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
        """Clear transient runtime recovery context after accepted successful work."""
        del node_input
        if self.session is None:
            return
        task = self._reviewed_task_from_result(llm_result)
        if task is None or task.result is None or not task.reviewer_decisions:
            return
        if task.result.success:
            task.metadata.pop("runtime_validation_failure", None)

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
