# Agent Instructions

> **File:** `docs/design/instructions.md`
> **Package:** `tinycua.constants.instructions`
> **Last Updated:** 2026-06-01
> **Status:** Draft

---

## Overview

Base instruction strings for all seven internal agents plus the TinyCUA main instruction.
Each instruction defines the agent's role, input contract, output schema, constraints, and guardrails.
Instructions are module-level string constants, NOT embedded in AgentNode or loop code.

The constants are the **static base** — the AgentNode's `build_instruction(context)` injects
dynamic session and project context on top before passing to `Agent(instructions=...)`.

---

## Instruction Constants

The `Agent(...)` constructor accepts `instructions=` which defaults to these constants via each agent's config dataclass.

| Constant | Agent | Loop | Key Elements |
|----------|-------|------|-------------|
| `QUERY_ANALYST_INSTRUCTION` | QueryAnalyst | QueryAnalystLoop | Role: fast classification + context analysis. Must call configurable `ClassificationTool` (MANDATORY — loop retries if missed). Input: `query`, assembled session context. Output: markdown context + classification label from `QueryAnalystConfig.classification_labels`. Root labels: `"passthrough"`, `"worker"`; no `"uncertain"` label. Conditional read-only task tools when active task exists. |
| `INFORMATION_DIGESTER_INSTRUCTION` | InformationDigester | InformationDigestionLoop | Role: precision retrieval from cached context. Tools: `enhanced_context_retrieval` (search cache via internal agent) + `digest_information` (MUST call at least once for structured output). Input: `ContextEnhancedQuery` (analysis + user_query). Output: `DigestedInformation` (via tool call, not final text). Strategy: search cache → evaluate gaps → repeat or digest. Guardrails: mandatory digest call; record `known_gaps` on empty results. |
| `TASK_ANALYZER_INSTRUCTION` | TaskAnalyzer | ReActAgentLoop | Role: task decomposition + modification. Input: `DigestedInformation` or plain query. Tools: read tools + task-management writes + `UpdateTaskResult` (except `TaskInit` by default; excludes `UpdateActiveTaskResult`). Output: markdown analysis summary (what was created/modified/deleted). Strategy: inspect current tree → plan changes → execute via tool calls → document result. |
| `TASK_ASSESSOR_INSTRUCTION` | TaskAssessor | TaskAssessorLoop | Role: assess task tree completeness. Tools: `AssessorVerdict` (MUST call — `"analyze"` or `"stop"`). Input: task tree + analysis query. Output: verdict + response text (→ TaskAnalyzer query). Enforcement: loop retries up to 3x if verdict not called. |
| `TASK_EXECUTOR_INSTRUCTION` | TaskExecutor | ReActAgentLoop | Role: active task execution. Input: plain `query: str`. Tools: `ReadActiveTask`, `ListTask`, `UpdateActiveTaskResult`. Output: writes `TaskResult` onto the current active task via tool call. Guardrails: dynamically load task state; terminate only after `completed`, `failed`, or `blocked`. |
| `RESULT_REVIEWER_INSTRUCTION` | ResultReviewer | ResultReviewLoop | Role: result review. Input: `TaskExecutorState` or plain review query. Output: `ResultReviewerState`. Classifications: accept/retry/replan. No `escalate_user`; indecision keeps reviewer active with open question. |
| `PRIMARY_AGENT_INSTRUCTION` | PrimaryAgent | PrimaryAgentLoop | Role: passthrough/final synthesis. Input: `QueryAnalystState` YAML or plain query. Output: `PrimaryAgentState` final response + citations. |
| `TINYCUA_MAIN_INSTRUCTION` | TinyCUA AgentGraph | MainLoop/AgentGraph | Role: graph orchestration. Input: user query. Flow: InputGate(QueryAnalyst) → route to PrimaryAgent/current active/TinyCUAWorker via classification. No `uncertain` route. |

---

## Instruction Governance

- Instructions live in `tinycua/constants/instructions.py` — not embedded in AgentNode `__init__` or loop `run()`
- To change the base instruction, edit the constant. No code changes needed in AgentNode or loop classes
- Dynamic context (session state, project files) is injected by `build_instruction(context)`, not by modifying constants
- Instructions are derived from architecture docs (`src/tinycua/docs/architecture/`)

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Instructions as constants | `tinycua/constants/instructions.py` | Single place to find/edit instructions; not scattered across AgentNode classes |
| Own package | `tinycua.constants` | Separates instructions from tools and config; each constant type has its own module |


---


---


---

## See also

Prev : [Pre-Configured Tool Sets (`*_BASE_TOOLS`)](tools.md) | Next : [`LoopError` Hierarchy](../exceptions/loops.md)


## Related

- [Each config references its instruction constant](../config/agents.md)
