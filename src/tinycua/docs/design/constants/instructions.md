# Agent Instructions

> **File:** `docs/design/constants/instructions.md`
> **Package:** `tinycua.constants.instructions`
> **Last Updated:** 2026-06-01
> **Status:** Draft

---

## Overview

Base instruction strings for internal AgentNodes.
Each instruction defines the agent's role, input contract, output schema, constraints, and guardrails.
Instructions are module-level string constants, NOT embedded in AgentNode or loop code.

The constants are the **static base** — the AgentNode's `__init__` assembles
them into a final instruction string once and caches it as `self._instruction`.
Per-call dynamic context (task tree, session state) is passed in messages, not by
rebuilding the instruction.

---

## Instruction Constants

The `Agent(...)` constructor accepts `instructions=` which defaults to these constants via each agent's config dataclass.

> All loops below are application-layer constructs in `tinycua.loops.*`. They extend
> `ReActLoop`, which extends the SDK's `BaseLoop`.

| Constant | Agent | TinyCUA Loop | Key Elements |
|----------|-------|------|-------------|
| `QUERY_ANALYST_INSTRUCTION` | QueryAnalyst | QueryAnalystLoop | Role: fast classification + context analysis. Must call configurable `ClassificationTool` (MANDATORY — loop retries if missed). Input: `query`, assembled session context. Output: markdown context + classification label from `QueryAnalystConfig.classification_labels`. Root labels: `"passthrough"`, `"worker"`; no `"uncertain"` label. Conditional read-only task tools when active task exists. |
| `INFORMATION_DIGESTER_INSTRUCTION` | InformationDigester | InformationDigestionLoop | Role: precision retrieval from cached context. Tools: `enhanced_context_retrieval` (search cache via internal agent) + `digest_information` (MUST call at least once for structured output). Input: `ContextEnhancedQuery` (analysis + user_query). Output: `DigestedInformation` (via tool call, not final text). Strategy: search cache → evaluate gaps → repeat or digest. Guardrails: mandatory digest call; record `known_gaps` on empty results. |
| `TASK_ANALYZER_INSTRUCTION` | TaskAnalyzer | TaskAnalyzerLoop | Role: task decomposition + modification. Input: `DigestedInformation` or plain query. Tools: read tools + task-management writes + `UpdateTaskResult` (except `TaskInit` by default; excludes `UpdateActiveTaskResult`). Output: markdown analysis summary (what was created/modified/deleted). Strategy: inspect current tree → plan changes → execute via tool calls → document result. |
| `TASK_ASSESSOR_INSTRUCTION` | TaskAssessor | TaskAssessorLoop | Role: assess task tree completeness. Tools: `AssessorVerdict` (MUST call — `"analyze"` or `"stop"`). Input: task tree + analysis query. Output: verdict + response text (→ TaskAnalyzer query). Enforcement: loop retries up to 3x if verdict not called. |
| `TASK_EXECUTOR_INSTRUCTION` | TaskExecutor | TaskExecutorLoop | Role: active task execution. Input: plain `query: str`. Tools: `ReadActiveTask`, `ListTask`, `UpdateActiveTaskResult`. Output: writes `TaskResult` onto the current active task via tool call. Guardrails: dynamically load task state; terminate only after `completed`, `failed`, or `blocked`. |
| `RESULT_REVIEWER_INSTRUCTION` | ResultReviewer | ResultReviewLoop | Role: result review. Input: `TaskExecutorState` or plain review query. Output: `ResultReviewerState`. Classifications: accept/retry/replan. No `escalate_user`; indecision keeps reviewer active with open question. |
| `PRIMARY_AGENT_INSTRUCTION` | PrimaryAgent | PrimaryAgentLoop | Role: passthrough/final synthesis. Input: `QueryAnalystState` YAML or plain query. Output: `PrimaryAgentState` final response + citations. |

TinyCUA itself has no instruction constant because it is not an SDK `Agent`. It is a
deterministic AgentGraph runtime that routes to `QueryAnalyst`, `PrimaryAgent`, active
AgentNodes, or `TinyCUAWorker`.

---

## Instruction Governance

- Instructions live in `tinycua/constants/instructions.py` — not embedded in AgentNode `__init__` or loop `run()`
- To change the base instruction, edit the constant. No code changes needed in AgentNode or loop classes
- The base constant is assembled into a final instruction once at AgentNode `__init__` time and cached as `self._instruction`. It is NOT rebuilt on every `run()` call — this enables provider-level prompt caching (e.g., Anthropic prefix caching, OpenAI prompt caching) to hit the stable system-message prefix.
- Dynamic context (current task tree, session metadata, project files) should be passed in per-call messages, not by rebuilding the instruction string. Keep the instruction prefix stable across calls.
- Instructions are derived from architecture docs (`src/tinycua/docs/architecture/`)

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Instructions as constants | `tinycua/constants/instructions.py` | Single place to find/edit instructions; not scattered across AgentNode classes |
| Cached at init time | Built once → `self._instruction`, never rebuilt per-call | Enables provider prompt caching; keeps system-message prefix stable |
| Minimize dynamic content | Dynamic context goes in messages, not instruction string | Avoids cache misses from small string changes between calls |
| Own package | `tinycua.constants` | Separates instructions from tools and config; each constant type has its own module |


---


---


---

## See also

Prev : [Pre-Configured Tool Sets (`*_BASE_TOOLS`)](tools.md) | Next : [`LoopError` Hierarchy](../exceptions/loops.md)


## Related

- [Each config references its instruction constant](../config/agents.md)
