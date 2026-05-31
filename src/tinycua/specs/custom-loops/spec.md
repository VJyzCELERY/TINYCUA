# Feature Specification: Agent + Loop Integration (M2)

**Status**: Draft
**Created**: 2026-05-31
**Last Updated**: 2026-05-31
**Associated Docs**: `src/tinycua/docs/design/` (design documentation synced during implementation)
**Subproject(s) Affected**: tinycua

---

## Problem Statement

- **Goals**: Implement M2 as an integrated Agent + Loop milestone: custom loop strategies, agent wrapper classes, system prompts, and agent-to-agent calling tools are specified and tested together. In `tinycua_sdk`, loops are passed into agents as `Agent(loop=CustomLoop(), ...)`; loops do **not** wrap agents. Internal TinyCUA agents are implemented as wrapper classes (e.g., `class QueryAnalyst`, `class TaskExecutor`) that compose SDK `Agent` internally — each class owns its configured SDK `Agent`, manages its own context/session state, and exposes domain-specific methods (`run()`, `save_state()`, `restore_state()`). This keeps loops focused on low-level execution (iteration, tool calling, validation) while the wrapper handles higher-level concerns (logging, verbosity, context management, persistence). Custom loop strategies are used only where the default SDK loop is insufficient — Classification, Exploration, and Hybrid Review — while using `tinycua_sdk.agent.loop.BaseLoop` directly for standard single-input/single-output agents. All agent definitions use `tinycua_sdk` (`Agent`, `BaseLoop`, `LanguageModel`, `Tool`, `AgentPolicy`) for LLM orchestration, tool execution, streaming, cancellation, and retry. This M2 work also defines the target external TINYCUA agent shape: `tinycua = TinyCUA(...)` which wraps an SDK `Agent` with `MainLoop` and coordinates all internal agents, resuming by session state.
- **Gaps**: The architecture defines agents, prompts, tools, and loop types conceptually in `src/tinycua/docs/architecture/`, but the implementation plan previously split custom loops (M2), agent factory (M3), agents (M4), prompts (M5), and agent-to-agent calling (M7). That split does not match SDK usage because the loop is an `Agent` configuration attribute. This feature must define the integrated mapping from each architecture agent to: an agent wrapper class that composes an SDK `Agent`, loop selection, prompt, tool set, output schema, domain-specific `run()` method, and an agent-calling tool wrapper. Wrapper classes give each agent authority over its own behavior (context management, state persistence, logging) without polluting the SDK `Agent` metadata or loop internals.
- **Non-Goals**: This spec does NOT implement the full session system (future M4), worker orchestration (future M5), or executable `MainLoop` top-level orchestrator (future M6). It **does** define the MainLoop target contract and the `TinyCUA` external wrapper class shape so M2 agent wrapper classes are compatible with the eventual single external TINYCUA agent. This spec does NOT define new LLM backend abstractions, tool-calling protocols, or event streaming infrastructure — those are provided by `tinycua_sdk`. Full native tool implementation beyond the agent-facing SDK `Tool` contracts remains in the Tools milestone; M2 wires required tools and may use stubs/mocks for tests. The Iterative Decomposition Loop (Task Creation) is a process-level orchestration concern, not an agent-internal loop, and is deferred to Worker Orchestration.
- **Constraints**:
  - Agents and loops must consume and produce the state objects defined in M1 (`tinycua.state`).
  - Custom loops must be passed to SDK agents via `Agent(loop=CustomLoop(), ...)`; the design MUST NOT introduce loop wrappers that own or wrap `Agent` instances.
  - Internal TinyCUA agents MUST be implemented as wrapper classes that compose (not extend) an SDK `Agent` internally. The wrapper class owns the configured SDK `Agent`, a `StateInformation` instance (`self.state`), and domain-specific methods (`run()`, `save_state()`, `restore_state()`). Each agent's `_build_agent()` merges three tool sources: (1) agent-initialized tools built from config (e.g., `ClassificationTool(labels=...)`), (2) a module-level `*_BASE_TOOLS` constant defining the agent's inherent tools, and (3) `config.extra_tools` for externally injected tools (empty list by default). Loops stay focused on low-level execution (iteration, tool calling, validation); the wrapper class manages higher-level concerns (logging, verbosity, context management, persistence hooks). SDK `Agent.metadata` MUST NOT be used as the primary store for session context, state identifiers, or runtime data — the wrapper's `StateInformation` instance is the canonical location.
  - Agent factory/configuration must create SDK `Agent` objects with the correct `LanguageModel`, `Tool` objects, `AgentPolicy`, prompt/instructions, output validation, and loop; the factory then wraps each SDK `Agent` in its typed TinyCUA wrapper class.
  - TinyCUA's default model configuration MUST use SDK provider `openai-chat-completions`, model `qwen/qwen3.5-4b`, and base URL `http://localhost:1234/v1`. Do not use provider alias `openai` in TinyCUA specs/design examples.
  - M2 agent wrapper classes MUST preserve enough metadata to support the future `MainLoop` external agent, including internal agent registry, state-store hook, default session options, and orchestration settings stored on the wrapper class rather than inside SDK `Agent.metadata`.
  - Loop types and agents MUST use `tinycua_sdk` for LLM orchestration and tool integration. Specifically: extend or compose with `tinycua_sdk.agent.loop.BaseLoop`; use `tinycua_sdk.agent.Agent` for LLM interaction; use `tinycua_sdk.agent.llm_client.LLMClient` for provider communication; use `tinycua_sdk.agent.llm_model.LanguageModel` for model configuration; use `tinycua_sdk.tools.decorators.Tool` for tool definitions.
  - Loop types and agents MUST NOT define custom LLM backend protocols, tool-calling loops, or streaming infrastructure — the SDK provides these.
  - Each loop type must expose a uniform interface by conforming to `BaseLoop.run()`.
  - Must target Python 3.12+.
  - No orchestration-level concerns (session management, inter-agent routing) inside loops — loops operate within a single agent invocation. Orchestration lives in the wrapper class or MainLoop.

---

## User Scenarios & Testing

### Primary Scenario

A developer implementing M2 creates each architecture agent as a TinyCUA wrapper class (e.g., `QueryAnalyst(config=QueryAnalystConfig(...))`) that composes an internal SDK `Agent` with the correct loop, system prompt, model, tools, policy, and output schema validation. The wrapper class exposes a domain-specific `run()` method that prepares input, delegates to the SDK `Agent`, and parses/validates the output. Integration tests instantiate the wrapper class and call `run()` directly.

### Acceptance Scenarios

1. **Given** a Query Analyst wrapper class configured with QueryAnalystLoop and ClassificationTool, **When** its `run()` is called with a user query, chat history, and session context, **Then** it produces a `ContextEnhancedQuery` and `ModeDecision` with valid fields (mode, score, confidence, reasons).
2. **Given** an Information Digester wrapper class configured with InformationDigestionLoop and an Enhanced Context Retrieval `Tool`, **When** its `run()` is called with a `ContextEnhancedQuery`, **Then** it produces a `DigestedInformation` with at minimum `context_summary` and `key_points`.
3. **Given** Task Analyzer wrapper class using `ReActAgentLoop`, **When** its `run()` receives `DigestedInformation`, **Then** it produces a `Task` tree (root with child_tasks) where each leaf node has required fields.
4. **Given** Task Assessor wrapper class using `ReActAgentLoop`, **When** its `run()` receives a `Task` tree and `WorkerConfig`, **Then** it returns a selection of task IDs marked for decomposition.
5. **Given** a Result Reviewer wrapper class configured with ResultReviewLoop and pluggable deterministic rules, **When** its `run()` receives a `TaskResult`, **Then** it produces a `ReviewerDecision` with `status` (accepted/retry/replan/escalate_user) and optional `context_updates`.
6. **Given** any of the seven architecture agents are instantiated as wrapper classes, **When** each is constructed from its config dataclass, **Then** the wrapper composes an SDK `Agent` with the expected prompt, tool set, output schema validation, and `loop` attribute. The wrapper class stores context state as instance attributes, not inside SDK `Agent.metadata`.
7. **Given** an agent-to-agent calling tool such as `call_task_analyzer`, **When** another agent invokes it, **Then** it delegates to the configured target wrapper class's `run()` method and returns a schema-valid target output.
8. **Given** the future external TINYCUA agent is created as `TinyCUA(...)`, **When** `tinycua.run(...)` is called, **Then** its `MainLoop` can use the M2 internal agent registry/configuration to route from Query Analyst through Primary Agent, Worker Mode, or Uncertain Mode without exposing internal agents to the user.

### Edge Cases

- What happens when the LLM returns malformed output that doesn't match the expected schema? The loop must retry via the SDK's retry infrastructure or fail with a clear error.
- What happens when tool calls fail (e.g., Enhanced Context Retrieval returns empty)? The loop must handle gracefully without crashing.
- What happens when the Exploration loop finds no relevant context? It must produce a `DigestedInformation` that explicitly notes the gap via `known_gaps`.
- What happens with empty input strings? The loop should reject with a validation error before making an LLM call.
- What happens when the Classification loop's scores are all low (high uncertainty)? It must set `mode=uncertain` with a non-null `uncertain_next_action`.
- What happens when the Hybrid Review loop cannot decide (contradictory signals between deterministic and LLM checks)? The deterministic check should take precedence for schema-level validation; the LLM check handles semantic evaluation.

---

## Requirements

### Functional Requirements

- **FR-001**: System MUST provide a **Classification Loop** that implements the Query Analyst's flow: high-level context scan → produce `ContextEnhancedQuery` → score-based mode classification → produce `ModeDecision`. The loop must accept `user_query`, `chat_history`, and `session_context` as input. Implemented with SDK `Agent.run()` using a structured system prompt and no tools. The loop MUST NOT enforce a true one-iteration/single-pass execution limit such as `max_iterations=1`; it should use the SDK `BaseLoop` default iteration behavior and rely on prompt/schema validation to produce one structured classification result.
- **FR-002**: The Classification Loop MUST support multi-dimensional scoring with at least three dimensions: task complexity, context dependency, and safety/risk. The loop MUST include anti-laziness safeguards: a rationale for `primary_agent` must explain why Worker decomposition is not needed; a rationale for `worker` must explain the decomposition benefit; `uncertain` mode must set `uncertain_next_action`.
- **FR-003**: System MUST provide an **Exploration Loop** that implements the Information Digester's flow: identify information gaps → invoke Enhanced Context Retrieval → extract relevant context → remove distractions → preserve task-critical details → structure into `DigestedInformation`. The loop must accept a `ContextEnhancedQuery` and have access to an Enhanced Context Retrieval SDK `Tool`.
- **FR-004**: The Exploration Loop MUST support iterative refinement by extending SDK's `BaseLoop`: the agent can identify gaps, retrieve via SDK tool calls, evaluate relevance, and decide to retrieve again or stop. The primary stop condition is LLM-judged sufficiency: each iteration evaluates whether identified gaps are sufficiently addressed or the retrieval tool returned no new information. The SDK's `BaseLoop.max_iterations` provides a hard count-based safety cap to prevent infinite loops. The SDK's `BaseLoop` handles the tool-calling iteration; the loop adds gap-evaluation logic.
- **FR-005**: The system MUST provide a `ReActAgentLoop` — a shared loop class extending SDK `BaseLoop` that provides the default ReAct behavior for simple single-input/single-output agents. Task Analyzer, Task Assessor, Task Executor, and Primary Agent all use `ReActAgentLoop` directly (no per-agent subclassing). Agents needing custom control flow (Query Analyst, Information Digester, Result Reviewer) define their own loop that extends `ReActAgentLoop`. This ensures loops are agent-specific only when behavior actually differs; the wrapper class provides identity separation. No custom `LinearAgentLoop`, `SimpleLoop`, or equivalent wrapper should be introduced.
- **FR-006**: `ReActAgentLoop` (extending SDK `BaseLoop`) serves as the base for single-input/single-output agents. It MUST support optional SDK `Tool` objects through the SDK's built-in tool-calling loop. Agents configured with tools use the internal ReAct iteration (think→act→observe→repeat); agents without tools perform pure reasoning via the LLM.
- **FR-007**: System MUST provide a **Hybrid Review Loop** that combines deterministic validation with LLM-based semantic review via SDK's `BaseLoop`. The loop must:
  - First perform deterministic checks as pluggable rules registered at construction time (schema validity, missing fields, required structure).
  - Then perform LLM-based semantic review using SDK's `Agent.run()` (correctness against success criteria, sufficiency, context propagation needs).
  - Produce a `ReviewerDecision` with one of four statuses: `accepted`, `retry`, `replan`, `escalate_user`.
  - When `accepted`, compute `context_updates` for unfinished/upcoming tasks.
  - When `retry`, include `retry_instructions` for the next executor attempt.
  - When `replan`, record the rationale for roadmap revision.
  - When `escalate_user`, include a clear explanation for the user.
- **FR-008**: All loop types MUST integrate with `tinycua_sdk` as their execution infrastructure:
  - Extend or compose with `tinycua_sdk.agent.loop.BaseLoop` for the `run()` interface.
  - Use `tinycua_sdk.agent.Agent` for LLM interaction (configured with `LanguageModel`, `Tool` objects, `AgentPolicy`).
  - Use `tinycua_sdk.agent.llm_client.LLMClient` for provider communication — NO custom LLM backend protocols.
  - Use `tinycua_sdk.tools.decorators.Tool` for tool definitions — NO custom tool dataclasses.
  - The input and output types MUST be M1 state objects or plain dicts with documented schemas.
- **FR-009**: All loop types MUST handle LLM invocation errors via the SDK's built-in retry infrastructure. The SDK's `BaseLoop` and `LLMClient` handle transient retries; loop types propagate permanent failures as typed exceptions.
- **FR-010**: All loop types MUST validate their output against the expected schema before returning. If validation fails, the loop should retry via the SDK's infrastructure with the validation error in context, then fail with a clear error if all retries are exhausted.
- **FR-011**: The Hybrid Review Loop MUST distinguish between deterministic validation failures (which should fail closed — escalate) and semantic concerns (which allow retry/replan). Deterministic checks MUST be pluggable rules rather than hardcoded loop internals, so different reviewer configurations can add or replace checks without subclassing the loop.
- **FR-012**: System MUST provide agent wrapper classes for all seven TinyCUA architecture agents. Each wrapper class composes (does not extend) an SDK `Agent` internally with the correct `name`, `instructions`, `LanguageModel`, `Tool` list, `AgentPolicy`, output schema validation, and `loop` value. The wrapper class exposes a domain-specific `run()` method that prepares the input, delegates to the composed SDK `Agent`, and parses/validates the output. Wrapper class attributes (not SDK `Agent.metadata`) are the canonical location for context state, session identifiers, configuration references, and persistence hooks. Unless an agent config explicitly overrides it, the wrapper MUST use TinyCUA's default `LanguageModel(provider="openai-chat-completions", model_name="qwen/qwen3.5-4b", base_url="http://localhost:1234/v1")`.
- **FR-013**: System MUST implement the system prompt/instructions for Query Analyst, Information Digester, Task Analyzer, Task Assessor, Task Executor, Result Reviewer, and Primary Agent from their architecture docs, including each agent's output contract and guardrails.
- **FR-014**: System MUST provide concrete agent wrapper classes for all seven architecture agents:
  - `QueryAnalyst` — composes SDK `Agent` with Classification loop, ClassificationTool (configurable labels), produces `ContextEnhancedQuery` + `ModeDecision` from `run(user_query, chat_history, session_context)`.
  - `InformationDigester` — composes SDK `Agent` with Exploration loop, Enhanced Context Retrieval SDK `Tool` contract, produces `DigestedInformation` from `run(context_enhanced_query)`.
  - `TaskAnalyzer` — composes SDK `Agent` with `ReActAgentLoop`, optional information tools, produces `Task` tree from `run(digested_information)`.
  - `TaskAssessor` — composes SDK `Agent` with `ReActAgentLoop`, no tools by default, produces task-selection output from `run(task_tree, worker_config)`.
  - `TaskExecutor` — composes SDK `Agent` with `ReActAgentLoop`, native benchmark tools, produces `TaskResult` from `run(task)`.
  - `ResultReviewer` — composes SDK `Agent` with Hybrid Review loop, pluggable deterministic rules, produces `ReviewerDecision` from `run(task, task_result, execution_log)`.
  - `PrimaryAgent` — composes SDK `Agent` with `ReActAgentLoop`, formatting/verification tools, produces final response from `run(context_enhanced_query_or_worker_result)`.
  Each wrapper class MUST store its current context, session state, and configuration as instance attributes (NOT in SDK `Agent.metadata`). Each wrapper class MUST define `save_state(store) -> None` and `restore_state(store) -> None` hooks for future persistence, with default no-op implementations in M2. Each wrapper's `_build_agent()` MUST merge tools from three sources: `[agent_init_tools] + BASE_TOOLS + config.extra_tools`, where `config.extra_tools` defaults to an empty list and is the sole channel for external tool injection (e.g., from MainLoop).
- **FR-015**: System MUST provide agent-to-agent calling tools (`call_query_analyst`, `call_information_digester`, `call_task_analyzer`, `call_task_assessor`, `call_task_executor`, `call_result_reviewer`, `call_primary_agent`) as SDK `Tool` objects. Each tool receives the target wrapper class instance (not a raw SDK `Agent`) and delegates through the wrapper's `run()` method, preserving the wrapper's context state and validation logic.
- **FR-016**: Integration tests MUST instantiate each agent wrapper class and call its `run()` method, verifying prompt wiring, tool wiring, loop selection, config overrides, and schema validation together. Tests MUST prove that state is stored as wrapper instance attributes, not buried in SDK `Agent.metadata`. Tests MUST prove that custom loops are configured as `Agent(loop=CustomLoop(), ...)` inside the wrapper, not as wrappers around agents.
- **FR-017**: SDK cookbook documentation for custom execution loops MUST be corrected during implementation so examples show custom loop instances being passed into `Agent(loop=...)`. In particular, `src/tinycua-sdk/docs/cookbook/execution-and-reference/custom-execution-loops.md` MUST NOT imply that `loop = CustomLoop()` affects `agent.run()` unless the loop is attached to the `Agent`.
- **FR-018**: System MUST define the target **MainLoop** contract for the single external `TinyCUA` wrapper class. `TinyCUA` will compose an SDK `Agent` with `MainLoop`, store the internal agent registry and state hooks as wrapper attributes (not inside SDK `Agent.metadata`), and orchestrate all internal agents by calling their wrapper `run()` methods. The wrapper class shape (`save_state()`, `restore_state()`, config attribute) is defined by M2; MainLoop execution is deferred to the top-level orchestration milestone.
- **FR-019**: MainLoop state requirements MUST be documented for future implementation: per-session state must track `session_id`, current orchestration phase, active internal agent, active sub-session/worker state, last completed step, pending user action, `ContextEnhancedQuery`, `ModeDecision`, `DigestedInformation`, active `Task`/current task id, `WorkerResult`, and final response status. M2 does not implement persistence, but each wrapper class's `save_state(store)` and `restore_state(store)` hooks must accept a storage backend parameter and leave a clear contract for SQLite-first persistent session store with optional filesystem-backed storage for artifacts/snapshots/logs/attachments and in-memory storage for tests/cache.

### Key Entities

All entities build on `tinycua_sdk` infrastructure:

- **SDK Integration Point**: All custom loop types extend `tinycua_sdk.agent.loop.BaseLoop` and integrate with `tinycua_sdk.agent.Agent`. The SDK provides: tool-calling execution loop (`BaseLoop`), LLM provider abstraction (`LLMClient`), model configuration (`LanguageModel`), tool infrastructure (`Tool`, `ToolExecutor`), streaming, cancellation, and usage tracking. Loop types are domain-specific strategies that add prompt structure, output schemas, and control flow variants (iterative retrieval, two-phase review) on top of this infrastructure.
- **Agent Wrapper Classes**: Each TinyCUA architecture agent is implemented as its own class (`QueryAnalyst`, `InformationDigester`, `TaskAnalyzer`, `TaskAssessor`, `TaskExecutor`, `ResultReviewer`, `PrimaryAgent`) that composes an SDK `Agent` internally. The wrapper class owns the configured SDK `Agent`, a `StateInformation` instance (`self.state`), and domain-specific methods (`run()`, `save_state()`, `restore_state()`). The composed SDK `Agent` is not publicly exposed — caller interaction goes through the wrapper's `run()` method. Wrappers keep loops focused on low-level execution; wrapper-level concerns include logging, verbosity, context management, and persistence hooks.
- **StateInformation** (in `tinycua.state.information`): An abstract base dataclass for per-agent structured runtime state. Each agent wrapper defines a concrete subclass storing M1 typed state objects (e.g., `QueryAnalystState` holds `ModeDecision` and `ContextEnhancedQuery`; `TaskAnalyzerState` holds `Task`; `TaskExecutorState` holds `TaskResult`; `ResultReviewerState` holds `ReviewerDecision` and `ReviewStatus`). Shared base fields include `session_id`, `chat_history`, `last_query`, `last_result`, and `metadata`. `save_state(store)` serializes the subclass instance; `restore_state(store)` hydrates it from a storage backend.
- **AgentConfig Dataclasses**: Per-agent configuration dataclasses (`QueryAnalystConfig`, `InformationDigesterConfig`, etc.) that hold all overridable parameters (classification labels, deterministic rules, extra tools, model overrides, metadata). Each wrapper class constructor accepts its config and builds the composed SDK `Agent` from it. Configs enable MainLoop to customize internal agent behavior without code changes.
- **TinyCUA (future external wrapper)**: The single external TinyCUA wrapper class that will compose an SDK `Agent` with `MainLoop`, hold the internal agent registry, and orchestrate agents by calling their wrapper `run()` methods. M2 defines its contract and wrapper shape; implementation is deferred to the top-level orchestration milestone.
- **System Prompt Definitions**: Prompt/instruction text derived from architecture docs and attached to each composed SDK `Agent.instructions` field.
- **Agent Calling Tools**: SDK `Tool` objects that receive target wrapper class instances and delegate through the wrapper's `run()` method, returning schema-valid outputs.
- **ReActAgentLoop**: Extends SDK's `BaseLoop`. Shared loop providing default ReAct behavior for simple single-input/single-output agents. Used directly by TaskAnalyzer, TaskAssessor, TaskExecutor, and PrimaryAgent wrappers. No per-agent subclassing needed — the wrapper class provides identity separation; the loop provides execution strategy.
- **QueryAnalystLoop**: Extends SDK's `BaseLoop`. Custom classification control flow. No tools at loop level (ClassificationTool is wired at wrapper level).
- **InformationDigestionLoop**: Extends SDK's `BaseLoop`. Custom iterative retrieval with gap-identification and sufficiency-evaluation logic.
- **ResultReviewLoop**: Extends SDK's `BaseLoop`. Custom two-phase execution: pluggable deterministic rules then SDK `Agent.run()` for semantic review.
- **SchemaValidator**: Shared component that validates LLM output against type schemas, leveraging the SDK's event/model infrastructure for structured parsing and retry.

---

## Success Criteria

- [ ] **Classification Loop**: A QueryAnalystLoop extending SDK's `BaseLoop` and using an SDK `Agent` produces `ContextEnhancedQuery` + `ModeDecision` from valid inputs. All three modes (primary_agent, worker, uncertain) are reachable depending on input characteristics. The loop does not force `max_iterations=1` or any equivalent one-pass stop condition.
- [ ] **Exploration Loop**: An InformationDigestionLoop extending SDK's `BaseLoop` with an Enhanced Context Retrieval SDK `Tool` produces `DigestedInformation` with context_summary and key_points. Iterative retrieval works: the agent can make multiple tool-calling iterations via the SDK's `BaseLoop`, stop when the LLM judges sufficiency, and still enforce `BaseLoop.max_iterations` as a hard cap.
- [ ] **Direct SDK BaseLoop Usage**: Task Analyzer and Task Assessor use `ReActAgentLoop` (via SDK `Agent.run()`) and produce schema-valid outputs. No custom `LinearAgentLoop`, `SimpleLoop`, or equivalent wrapper exists for these agents.
- [ ] **Hybrid Review Loop**: A ResultReviewLoop composing SDK's `BaseLoop` with pluggable deterministic checks produces all four `ReviewerDecision` statuses. Deterministic validation failures result in `escalate_user` or `replan` rather than `retry`.
- [ ] **SDK Integration**: All custom loop strategies integrate with `tinycua_sdk` — they extend or compose with `BaseLoop`, use `Agent` for LLM interaction, use SDK `Tool` objects for tool definitions, and use SDK `LanguageModel`/`LLMClient` for provider communication. Standard single-output agents use `ReActAgentLoop`. No custom LLM backend protocols, no custom tool dataclasses, no standalone retry or streaming logic.
- [ ] **Agent Wrapper Classes**: All seven architecture agents are instantiated as typed wrapper classes (`QueryAnalyst(config)`, `InformationDigester(config)`, etc.) each composing an SDK `Agent` internally. Wrapper `run()` methods prepare input, delegate to the composed agent, and parse/validate output. Wrapper instance attributes hold context state; SDK `Agent.metadata` is NOT used as the primary state store.
- [ ] **Agent Config Dataclasses**: Each agent has its own config dataclass accepting overrides for labels, tools, rules, model, and metadata without modifying defaults. Configs enable MainLoop customization without code changes.
- [ ] **Agent Factory + Prompts**: All seven architecture agents can be constructed as wrapper classes from their config dataclasses with correct prompts, model configuration, tools, policies, output validators, and loop attributes.
- [ ] **Agent-to-Agent Tools**: All seven `call_*` tools exist as SDK `Tool` objects and delegate through configured SDK `Agent.run()` calls.
- [ ] **Loop/Agent Coupling Verified**: Tests demonstrate custom loops are passed into the composed SDK `Agent` with `Agent(loop=...)`; no loop implementation wraps or owns an `Agent` as the execution boundary. State lives on the wrapper class, not in SDK metadata.
- [ ] **MainLoop Contract Preserved**: Spec/design define the future single external TINYCUA wrapper as `TinyCUA(...)` composing an SDK `Agent` with `MainLoop`, with internal agent registry and continuation-state hooks as wrapper attributes (not SDK metadata).
- [ ] **Error Handling**: Transient LLM failures trigger retry via SDK's built-in infrastructure. Permanent failures and exhausted retries raise typed exceptions. Output validation failures trigger LLM retry with error context, then raise on exhaustion.
- [ ] **Test Coverage**: Unit test coverage exceeds 85% for the loop module, using SDK mock patterns (mock `Agent`, mock `BaseLoop`, mock `LLMClient`).
- [ ] **Design Documentation Sync**: `src/tinycua/docs/design/` is created/synchronized during implementation, documenting each agent wrapper class, loop strategy, config schema, and agent-to-agent calling contract. Design docs serve as the canonical reference for how TinyCUA agents are structured, mirroring the role `src/tinycua/docs/architecture/` plays for the conceptual architecture.

---

## Testing Plan

### Unit Tests

- Each loop type: construction with SDK `Agent` configuration, construction with invalid config (expected error).
- QueryAnalystLoop: output matches ModeDecision schema for all three modes. Anti-laziness safeguards produce correct rationales. Edge: all scores low → `uncertain` with non-null `uncertain_next_action`. Verify that no custom LLM backend is created — only SDK `Agent` is used. Verify classification does not configure `BaseLoop` with `max_iterations=1` or an equivalent forced one-pass limit.
- InformationDigestionLoop: produces DigestedInformation structure. Handles empty retrieval results (fills known_gaps). Makes multiple retrieval iterations via SDK's `BaseLoop` tool-calling. Stops when the LLM judges gaps are addressed and enforces `BaseLoop.max_iterations` as a hard cap. Verifies integration with SDK `Tool` objects.
- Direct SDK BaseLoop usage: Task Analyzer and Task Assessor configurations use SDK `Agent.run()` with SDK `BaseLoop`, produce correct output schemas, and reject invalid input types. With SDK `Tool` objects: use tools via the SDK's tool-calling loop. Without tools: pure reasoning output. Verify that no custom loop class is introduced for this pattern.
- ResultReviewLoop: produces all four status values. Pluggable deterministic checks fire before LLM phase. Deterministic failure on schema invalidity cannot be overridden by LLM semantic review. Different rule sets can be registered without subclassing the loop. Context updates computed on `accepted`. Retry instructions included on `retry`. LLM review uses SDK's `Agent.run()`.
- SchemaValidator: accepts valid output, rejects invalid output with descriptive error. Validates nested structures (Task tree with child_tasks).
- SDK integration: verify that custom loops do NOT define their own `LLMBackend` protocol, `ToolDef` dataclass, or standalone LLM-calling/rety/streaming logic.
- Agent wrapper classes: verify each wrapper class is instantiated from its config, composes an SDK `Agent` with correct loop/prompt/tools/model, and exposes a domain-specific `run()` method. Verify wrapper instance attributes hold state (not SDK `Agent.metadata`). Verify `save_state(store)` and `restore_state(store)` hooks exist and accept a storage backend parameter (no-op default acceptable).
- Agent config dataclasses: verify each config accepts overrides, defaults unchanged, factory produces correct wrapper from config.
- Model configuration: verify default TinyCUA wrappers use provider `openai-chat-completions`, model `qwen/qwen3.5-4b`, and base URL `http://localhost:1234/v1`; verify no design/example code uses provider alias `openai`.
- System prompts: verify prompt definitions include role, input contract, output schema, constraints, and guardrails from the architecture docs.
- Agent-to-agent tools: verify each `call_*` SDK `Tool` invokes the target wrapper's `run()` method and validates/normalizes the returned output.
- MainLoop contract: verify the config registry exposes internal agent mappings and metadata keys as attributes on wrapper classes, not hidden inside SDK `Agent.metadata`.

### Integration Tests

- Loop with real (mock-compatible) SDK `Agent` produces correctly structured output for each type.
- InformationDigestionLoop with an SDK `Tool` for Enhanced Context Retrieval performs multi-step iteration via `BaseLoop`.
- Each configured agent wrapper class runs through its `run()` method with mock-compatible LLM responses; validates prompt wiring, tool wiring, loop selection, and schema parsing together.
- State is verified as living on wrapper instance attributes, not SDK `Agent.metadata`.
- Agent-to-agent tools can call target wrapper classes through the same `run()` interface used in production.
- Documentation verification confirms the SDK custom execution loops cookbook demonstrates `Agent(loop=CustomLoop(...))` for custom loop usage and documents that unattached loop instances are not used by `agent.run()`. `src/tinycua/docs/design/` is created and documents all wrapper classes, configs, and loop strategies.

### Manual Tests

- None in scope — fully covered by unit and integration tests with mocked SDK `Agent` and `BaseLoop`.

---

## Future Architecture Documentation Sync

Do **not** update `src/tinycua/docs/architecture/` as part of this spec/design PR. During the implementation phase, update architecture documentation to align terminology and mappings with this spec:

- `src/tinycua/docs/architecture/overview.md` → Agent Loop Types table should map Task Analyzer and Task Assessor to direct SDK `BaseLoop` usage rather than a separate Linear/Simple/custom loop type.
- `src/tinycua/docs/architecture/task-analysis.md` → clarify that Task Analyzer uses an SDK `Agent` with the `ReActAgentLoop`; any single-output guarantee comes from prompt/schema validation, not a custom loop class.
- `src/tinycua/docs/architecture/task-assessor.md` → clarify that Task Assessor uses an SDK `Agent` with the `ReActAgentLoop`; decomposition-selection output is schema-validated outside the loop.
- Any architecture references to "input→output loop", "linear loop", or "simple loop" should be reviewed and normalized to "ReActAgentLoop usage" where no custom control flow is required.

Also update SDK cookbook documentation during implementation:

- `src/tinycua-sdk/docs/cookbook/execution-and-reference/custom-execution-loops.md` → custom loop examples should pass the loop instance to `Agent(loop=...)`; creating `loop = CustomLoop()` without attaching it to the agent should not be presented as affecting `agent.run()`.

---

## Future Design Documentation Sync

Do **not** create or update `src/tinycua/docs/design/` as part of this spec/design PR. During the implementation phase, create and maintain `src/tinycua/docs/design/` as the canonical reference for TinyCUA's concrete agent design:

- `src/tinycua/docs/design/overview.md` → Overview of all agent wrapper classes, their config dataclasses, how wrappers compose SDK `Agent` internally, and the layer separation (wrapper = high-level context/logging/persistence; loop = low-level execution).
- `src/tinycua/docs/design/query-analyst.md` → `QueryAnalyst` wrapper class, `QueryAnalystConfig`, `QueryAnalystLoop`, `ClassificationTool` contract.
- `src/tinycua/docs/design/information-digester.md` → `InformationDigester` wrapper class, `InformationDigesterConfig`, `InformationDigestionLoop`, Enhanced Context Retrieval tool contract.
- `src/tinycua/docs/design/task-analyzer.md` → `TaskAnalyzer` wrapper class, `TaskAnalyzerConfig`, direct SDK `BaseLoop` usage.
- `src/tinycua/docs/design/task-assessor.md` → `TaskAssessor` wrapper class, `TaskAssessorConfig`, direct SDK `BaseLoop` usage.
- `src/tinycua/docs/design/task-executor.md` → `TaskExecutor` wrapper class, `TaskExecutorConfig`, native tool contract, direct SDK `BaseLoop` usage.
- `src/tinycua/docs/design/result-reviewer.md` → `ResultReviewer` wrapper class, `ResultReviewerConfig`, `ResultReviewLoop`, deterministic rules contract.
- `src/tinycua/docs/design/primary-agent.md` → `PrimaryAgent` wrapper class, `PrimaryAgentConfig`, direct SDK `BaseLoop` usage.
- `src/tinycua/docs/design/agent-calls.md` → Agent-to-agent calling tools, how they receive wrapper instances and delegate through `run()`.
- `src/tinycua/docs/design/tinycua-agent.md` → `TinyCUA` external wrapper class contract, `MainLoop` integration point, internal agent registry.

Design docs serve as the implementation-level counterpart to architecture docs: architecture describes the conceptual agent responsibility and flow; design documents the concrete class structure, API, and composition model.

---

## Status Tracker

| Item | Status | Notes |
|------|--------|-------|
| Classification Loop | TODO | Extends SDK `BaseLoop`; used by `QueryAnalyst` wrapper |
| Exploration Loop | TODO | Extends SDK `BaseLoop`; used by `InformationDigester` wrapper |
| Direct SDK BaseLoop mapping | TODO | Standard single-output agents use SDK `BaseLoop`; no custom loop class |
| Hybrid Review Loop | TODO | Extends SDK `BaseLoop`; used by `ResultReviewer` wrapper |
| Agent Wrapper Classes | TODO | Seven typed classes composing SDK `Agent` internally |
| Agent Config Dataclasses | TODO | Per-agent configs enabling MainLoop customization |
| System Prompts | TODO | Prompt instructions from architecture docs |
| Concrete Agent Configurations | TODO | QueryAnalyst, InformationDigester, TaskAnalyzer, TaskAssessor, TaskExecutor, ResultReviewer, PrimaryAgent |
| Agent-to-Agent SDK Tools | TODO | `call_*` tools delegate through wrapper `run()` methods |
| MainLoop contract | TODO | `TinyCUA` wrapper class contract; MainLoop execution deferred |
| Uniform BaseLoop integration | TODO | |
| SchemaValidator with SDK retry | TODO | |
| Architecture docs sync (future implementation phase) | TODO | Do not update architecture docs in this PR |
| Design docs sync (future implementation phase) | TODO | Create `src/tinycua/docs/design/` during implementation |
| SDK Cookbook custom loop correction | TODO | Fix `Agent(loop=...)` examples in cookbook during implementation |
| Unit tests | TODO | |

---

## Open Questions

None. Resolved decisions are incorporated into the functional requirements, success criteria, testing plan, and design document.

---

## Review Checklist

- [ ] No implementation details (no code, framework, or architecture choices)
- [ ] All mandatory sections completed
- [ ] No `[NEEDS CLARIFICATION]` markers remain
- [ ] Requirements are testable and unambiguous
- [ ] Scope is clearly bounded with explicit non-goals
- [ ] Success criteria are measurable
