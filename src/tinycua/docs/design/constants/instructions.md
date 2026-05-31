# Agent Instructions

> **File:** `docs/design/instructions.md`
> **Package:** `tinycua.constants.instructions`
> **Last Updated:** 2026-05-31
> **Status:** Draft

---

## Overview

Base instruction strings for all seven internal agents plus the TinyCUA main instruction.
Each instruction defines the agent's role, input contract, output schema, constraints, and guardrails.
Instructions are module-level string constants, NOT embedded in orchestrator or loop code.

The constants are the **static base** — the orchestrator's `build_instruction(context)` injects
dynamic session and project context on top before passing to `Agent(instructions=...)`.

---

## Instruction Constants

The `Agent(...)` constructor accepts `instructions=` which defaults to these constants via each agent's config dataclass.

| Constant | Agent | Loop | Key Elements |
|----------|-------|------|-------------|
| `QUERY_ANALYST_INSTRUCTION` | QueryAnalyst | QueryAnalystLoop | Role: fast classification + context analysis. Input: `user_query`, assembled session context. Output: markdown context (keywords, relevant snippets) + `ModeDecision`. Tools: `classify`, uncertainty tools, conditional read-only task tools. Scoring: task complexity, context dependency, safety/risk. Guardrails: anti-laziness rationales. |
| `INFORMATION_DIGESTER_INSTRUCTION` | InformationDigester | InformationDigestionLoop | Role: precision retrieval from cached context. Tools: `enhanced_context_retrieval` (search cache via internal agent) + `digest_information` (MUST call at least once for structured output). Input: `ContextEnhancedQuery` (analysis + user_query). Output: `DigestedInformation` (via tool call, not final text). Strategy: search cache → evaluate gaps → repeat or digest. Guardrails: mandatory digest call; record `known_gaps` on empty results. |
| `TASK_ANALYZER_INSTRUCTION` | TaskAnalyzer | ReActAgentLoop | Role: task decomposition + modification. Input: `DigestedInformation` or plain query. Tools: all read + write task tools (except TaskInit by default). Output: markdown analysis summary (what was created/modified/deleted). Strategy: inspect current tree → plan changes → execute via tool calls → document result. |
| `TASK_ASSESSOR_INSTRUCTION` | TaskAssessor | ReActAgentLoop | Role: decomposition selection. Input: `Task` tree + `WorkerConfig`. Output: `list[task_id]`. Guardrails: only select tasks too complex for direct execution. |
| `TASK_EXECUTOR_INSTRUCTION` | TaskExecutor | ReActAgentLoop | Role: task execution. Input: `Task`. Output: `TaskResult`. Tools: native benchmarks as available. Guardrails: execute as specified, report issues. |
| `RESULT_REVIEWER_INSTRUCTION` | ResultReviewer | ResultReviewLoop | Role: result review. Input: `task`, `task_result`, `execution_log`. Output: `ReviewerDecision`. Statuses: accepted/retry/replan/escalate_user. Guardrails: LLM handles semantics; deterministic phase handles schema. |
| `PRIMARY_AGENT_INSTRUCTION` | PrimaryAgent | ReActAgentLoop | Role: final synthesis. Input: `ContextEnhancedQuery` or `WorkerResult`. Output: final response + optional citations. Guardrails: self-contained response. |
| `TINYCUA_MAIN_INSTRUCTION` | TinyCUA | MainLoop | Role: orchestration. Input: user query. Flow: classify → route to primary/worker/uncertain → delegate via agent-calling tools → synthesize response. |

---

## Instruction Governance

- Instructions live in `tinycua/constants/instructions.py` — not embedded in orchestrator `__init__` or loop `run()`
- To change the base instruction, edit the constant. No code changes needed in orchestrator or loop classes
- Dynamic context (session state, project files) is injected by `build_instruction(context)`, not by modifying constants
- Instructions are derived from architecture docs (`src/tinycua/docs/architecture/`)

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Instructions as constants | `tinycua/constants/instructions.py` | Single place to find/edit instructions; not scattered across orchestrator classes |
| Own package | `tinycua.constants` | Separates instructions from tools and config; each constant type has its own module |


---


---


---

## See also

Prev : [Pre-Configured Tool Sets (`*_BASE_TOOLS`)](tools.md) | Next : [`LoopError` Hierarchy](../exceptions/loops.md)


## Related

- [Each config references its instruction constant](../config/agents.md)
