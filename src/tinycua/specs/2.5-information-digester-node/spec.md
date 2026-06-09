# Feature Specification: TinyCUAInformationDigesterNode

**Status**: Draft
**Created**: 2026-06-09
**Last Updated**: 2026-06-09
**Subproject(s) Affected**: tinycua (core)
**Milestone**: 2.5 — InformationDigesterNode and Enhanced Context Retrieval
**Design**: ./design.md

---

## Problem Statement _(mandatory)_

- **Goals**: Provide a context-gathering node that produces structured digested information from selected session context, enabling downstream nodes (especially ResponseNode) to receive summarized context when direct accumulated context or tool access is insufficient.
- **Gaps**: Milestone 2.4 established AnalysisEffortNode for configurable planning depth. However, there is no mechanism for downstream nodes to request additional context gathering when their direct accumulated context is insufficient. ResponseNode and TaskExecutor currently have no way to delegate context retrieval to a specialized node that creates a fresh session, lazily accesses parent context through `enhanced_context_retrieval`, and produces structured digest output.
- **Non-Goals**: ResponseNode suspension path for requesting InformationDigester (Milestone 3.6), TaskExecutor direct tool access (Milestone 3.2), full architecture verification (Milestone 4.5), and WildClawBench integration.
- **Constraints**: Must not modify tinycua-sdk public APIs. Must reuse existing ProcessNode infrastructure. InformationDigesterNode is an LLM-calling ProcessNode. Must create a fresh node session (not inherit parent/root session). Must use selected-output propagation targeting its suspended parent.

---

## User Scenarios & Testing _(mandatory)_

### Primary Scenario

A developer creates a TinyCUA agent using `create_tinycua_agent(...)` and calls `.run("Help me write a script"). QueryAnalyst classifies the input as `worker` and spawns a WorkerNode. Eventually, ResponseNode determines that available context is insufficient and suspends itself, prepending InformationDigesterNode with selected context from its session. InformationDigesterNode creates a fresh session, receives the selected input messages, optionally uses `enhanced_context_retrieval` to lazily access broader context, produces structured digested information via `digest_information`, and propagates the digest back to the suspended ResponseNode. ResponseNode resumes with the enriched context and produces the final response.

### Acceptance Scenarios

1. **Given** InformationDigesterNode receives `NodeInput` with selected parent session_context messages, **When** it creates a fresh session, **Then** it does not inherit or reuse the parent session_id or root session.
2. **Given** InformationDigesterNode has a fresh session, **When** it processes input messages, **Then** it stores only its own new local output (the digest) and does not re-store copied input messages in its reusable context.
3. **Given** InformationDigesterNode receives selected input from a parent node, **When** it completes, **Then** it propagates digested output to the parent node's session via selected-output propagation rule.
4. **Given** InformationDigesterNode is spawned with `enhanced_context_retrieval` tool enabled, **When** it needs broader context, **Then** it lazily creates a scoped context cache file and runs a limited ReAct-style search over that cache.
5. **Given** InformationDigesterNode is spawned with `enhanced_context_retrieval` tool enabled, **When** the cache is created, **Then** search and read operations are limited to the cache (grep/search within cache and paginated cache reads).
6. **Given** InformationDigesterNode finds no useful context during retrieval, **When** it completes, **Then** it returns a fallback continuation: "The user asked `<user_query>`. No useful extra information was found. Downstream should proceed with the user request and plan carefully before action."
7. **Given** InformationDigesterNode finds useful context, **When** it calls `digest_information`, **Then** it produces structured `DigestedInformation` with fields: `context_summary`, `key_points`, `advisory_instructions`, `constraints`, `known_gaps`.
8. **Given** InformationDigesterNode completes and propagates output to its parent, **When** the parent resumes, **Then** the digest output lands in the parent's `session_context`.
9. **Given** InformationDigesterNode is spawned by ResponseNode, **When** it receives input, **Then** the input contains a copied, selected subset of the response node's `session_context` messages plus an optional digest request payload.
10. **Given** InformationDigesterNode tool scope, **When** it executes, **Then** it has access only to `enhanced_context_retrieval` and `digest_information` tools — no outer Agent tools.
11. **Given** InformationDigesterNode retry behavior, **When** a digest attempt fails, **Then** it retries according to `NodeRetryPolicy` before falling back.
12. **Given** InformationDigesterNode completes with digest output, **When** propagation occurs, **Then** `chat_history` remains available for audit but is not passed wholesale to the digester unless explicitly selected.
13. **Given** a user query is included in the fallback continuation, **When** the fallback reaches downstream nodes, **Then** the original user query is preserved in the fallback message.

### Edge Cases

- What happens when `enhanced_context_retrieval` is disabled? → **Design**: InformationDigesterNode proceeds with only the selected input messages it received, producing a digest from that context alone. [§Error Handling](./design.md#error-handling)
- How does the system handle empty or null input messages? → **Design**: InformationDigesterNode returns the no-useful-context fallback. [§Error Handling](./design.md#error-handling)
- What happens when `digest_information` tool call fails? → **Design**: InformationDigesterNode retries per `NodeRetryPolicy`, then falls back to returning the no-useful-context continuation. [§Error Handling](./design.md#error-handling)
- What is the behavior when `enhanced_context_retrieval` cache creation fails? → **Design**: InformationDigesterNode logs the error and proceeds with available input context, producing a partial digest. [§Error Handling](./design.md#error-handling)
- What happens when `max_digest_sources` is configured and exceeded? → **Design**: InformationDigesterNode limits the number of context sources it processes, producing a digest from the allowed sources only. [§Error Handling](./design.md#error-handling)

---

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: System MUST provide `TinyCUAInformationDigesterNode` as a concrete `ProcessNode`.
- **FR-002**: InformationDigesterNode MUST create a fresh node session — it MUST NOT inherit or reuse the parent or root session.
- **FR-003**: InformationDigesterNode MUST receive only selected `NodeInput` messages from the parent, not the full parent `session_context`.
- **FR-004**: InformationDigesterNode MUST store only its own new local output (the digest) in its session; it MUST NOT re-store copied input messages.
- **FR-005**: InformationDigesterNode MUST propagate digested output to the parent node's session via selected-output propagation rule.
- **FR-006**: InformationDigesterNode MUST support `enhanced_context_retrieval` tool for lazy scoped context access.
- **FR-007**: When `enhanced_context_retrieval` is called, InformationDigesterNode MUST lazily create a scoped context cache file and run a limited ReAct-style search over that cache.
- **FR-008**: Search and read operations within `enhanced_context_retrieval` MUST be limited to the cache (grep/search within cache and paginated cache reads).
- **FR-009**: InformationDigesterNode MUST support `digest_information` tool for producing structured digest output.
- **FR-010**: InformationDigesterNode MUST produce `DigestedInformation` with fields: `context_summary`, `key_points`, `advisory_instructions`, `constraints`, `known_gaps`.
- **FR-011**: When no useful context is found, InformationDigesterNode MUST return a fallback continuation preserving the original user query: "The user asked `<user_query>`. No useful extra information was found. Downstream should proceed with the user request and plan carefully before action."
- **FR-012**: InformationDigesterNode MUST use selected-output propagation profile targeting its suspended parent.
- **FR-013**: InformationDigesterNode MUST NOT have access to outer Agent tools — only `enhanced_context_retrieval` and `digest_information`.
- **FR-014**: InformationDigesterNode MUST retry according to `NodeRetryPolicy` on failure.
- **FR-015**: `chat_history` MUST remain available for audit but MUST NOT be passed wholesale to the digester unless explicitly selected.
- **FR-016**: InformationDigesterNode MUST NOT modify tinycua-sdk public APIs.
- **FR-017**: InformationDigesterNode MUST accept `NodeConfigBase | None` configuration and create defaults when None.
- **FR-018**: InformationDigesterNode MUST support `parent` node parameter for suspension/resume with ResponseNode.
- **FR-019**: InformationDigesterNode MUST NOT execute tasks, create or mutate tasks, or synthesize final user responses.

### Key Entities _(include if feature involves data)_

- **TinyCUAInformationDigesterNode**: Concrete ProcessNode that gathers and digests context for downstream nodes. Creates a fresh session, receives selected input, uses enhanced context retrieval for lazy access, and produces structured digest output. Optional — invoked only when direct accumulated context/tool access is insufficient.
- **DigestedInformation**: Data model capturing the useful output from InformationDigesterNode. Fields: `context_summary` (str), `key_points` (list[str]), `advisory_instructions` (list[str]), `constraints` (list[str]), `known_gaps` (list[str]).
- **NodeInput**: Transport object carrying selected parent session_context messages and optional digest request payload to InformationDigesterNode.
- **EnhancedContextRetrieval**: Shared tool contract for scoped, lazy context access with cache creation and ReAct-style search. Available to InformationDigesterNode, TaskExecutor, and ResponseNode.
- **TinyCUAInformationDigesterNodeConfig**: Configuration extending NodeConfigBase with `retrieval_enabled: bool`, `max_digest_sources: int | None`, and `digest_schema: dict | None`.

---

## Success Criteria _(mandatory)_ — use `[ ]` checkboxes

- [ ] **SC-001** — **Acceptance Scenario 1** (Fresh Session): InformationDigesterNode creates a fresh session with its own session_id, not inheriting parent/root.
- [ ] **SC-002** — **Acceptance Scenario 2** (Own Output Only): InformationDigesterNode stores only its own digest output, not copied input messages.
- [ ] **SC-003** — **Acceptance Scenario 3** (Propagation): Digest output propagates to parent node's session via selected-output propagation.
- [ ] **SC-004** — **Acceptance Scenario 4** (Enhanced Retrieval): `enhanced_context_retrieval` lazily creates scoped cache and runs ReAct-style search.
- [ ] **SC-005** — **Acceptance Scenario 5** (Cache Isolation): Search/read operations are limited to the cache.
- [ ] **SC-006** — **Acceptance Scenario 6** (No-Useful-Context Fallback): Fallback continuation preserves original user query and signals downstream to proceed.
- [ ] **SC-007** — **Acceptance Scenario 7** (Structured Digest): `digest_information` produces `DigestedInformation` with all required fields.
- [ ] **SC-008** — **Acceptance Scenario 8** (Digest in Parent Context): Digest output lands in parent's `session_context` after propagation.
- [ ] **SC-009** — **Acceptance Scenario 9** (ResponseNode Input): When spawned by ResponseNode, input contains copied selected subset plus optional payload.
- [ ] **SC-010** — **Acceptance Scenario 10** (Tool Scope): InformationDigesterNode has access only to `enhanced_context_retrieval` and `digest_information`.
- [ ] **SC-011** — **Acceptance Scenario 11** (Retry): InformationDigesterNode retries per `NodeRetryPolicy` on failure.
- [ ] **SC-012** — **Acceptance Scenario 12** (Chat History Audit): `chat_history` remains available but not passed wholesale unless selected.
- [ ] **SC-013** — **Acceptance Scenario 13** (Fallback Query Preservation): Original user query preserved in fallback continuation.
- [ ] **SC-014** — **FR-016** (SDK API Stability): InformationDigesterNode does not modify tinycua-sdk public API surface.
- [ ] **SC-015** — **FR-019** (Non-Responsibilities): InformationDigesterNode does not execute tasks, mutate tasks, or synthesize final responses.

---

## Testing Plan _(mandatory)_

### Unit Tests

- `test_fresh_session_created`: InformationDigesterNode creates a fresh session with its own session_id.
- `test_does_not_inherit_parent_session`: InformationDigesterNode does not inherit parent or root session.
- `test_stores_only_own_output`: InformationDigesterNode stores only its digest output, not copied input.
- `test_propagates_to_parent`: Digest output propagates to parent session via selected-output rule.
- `test_enhanced_retrieval_creates_cache`: `enhanced_context_retrieval` lazily creates scoped cache.
- `test_enhanced_retrieval_search_limited_to_cache`: Search/read operations limited to cache.
- `test_no_useful_context_fallback`: Fallback continuation preserves user query.
- `test_digest_information_produces_structured_output`: `digest_information` produces `DigestedInformation`.
- `test_tool_scope_restricted`: Only `enhanced_context_retrieval` and `digest_information` available.
- `test_retry_on_failure`: Retries per `NodeRetryPolicy` before fallback.
- `test_chat_history_not_passed_wholesale`: `chat_history` available but not passed unless selected.
- `test_fallback_preserves_user_query`: Original user query in fallback message.
- `test_config_defaults_when_none`: Creates default config when none provided.
- `test_parent_parameter_accepted`: Accepts parent node for suspension/resume.
- `test_does_not_execute_tasks`: Does not create or mutate tasks.
- `test_does_not_synthesize_response`: Does not produce final user response.

### Integration Tests

- `test_information_digester_with_response_node_suspension`: End-to-end: ResponseNode suspends → InformationDigesterNode gathers context → ResponseNode resumes with digest.
- `test_information_digester_no_useful_context_path`: End-to-end: InformationDigesterNode finds no context → fallback reaches downstream.
- `test_information_digester_enhanced_retrieval_end_to_end`: End-to-end: InformationDigesterNode uses `enhanced_context_retrieval` → produces digest from cache.
- `test_information_digester_propagation_to_parent_session`: End-to-end: Digest output propagates and is visible in parent's session_context.

### Manual Tests _(if applicable)_

- Verify InformationDigesterNode queue shape when prepended by ResponseNode.
- Verify fallback continuation message format with debug logging enabled.
- Verify enhanced context retrieval cache file creation and contents.

---

## Status Tracker _(optional)_

| Item | Status | Notes |
|------|--------|-------|
| Planning documents | TODO | spec.md, design.md |
| TinyCUAInformationDigesterNode class | TODO | information_digester.py |
| TinyCUAInformationDigesterNodeConfig | TODO | node_config.py extension |
| DigestedInformation model | TODO | digested_information.py |
| enhanced_context_retrieval tool | TODO | Shared tool contract |
| digest_information tool | TODO | Tool for structured output |
| Node __init__.py export | TODO | Add to loops __all__ |
| Unit tests | TODO | All acceptance scenarios |
| Integration tests | TODO | ResponseNode suspension flow |

---

## Open Questions _(optional)_

1. **Should `enhanced_context_retrieval` be implemented in this milestone or deferred to Tool Scoping (Milestone 4.2)?**
   - **Owner**: @VJyzCELERY
   - **Target**: 2026-06-10
   - **Status**: Discussion
   - **Proposed Answer**: The shared contract and interface should be defined in this milestone. Full implementation may be deferred to 4.2, but InformationDigesterNode should be coded against the contract.

2. **Should `digest_information` tool call be implemented as a deterministic function or an LLM-assisted tool?**
   - **Owner**: @VJyzCELERY
   - **Target**: 2026-06-10
   - **Status**: Discussion
   - **Proposed Answer**: `digest_information` should be an LLM-assisted tool call where the LLM produces the structured digest from the gathered context.

---

## Review Checklist

- [x] No implementation details (no code, framework, or architecture choices) — domain entity names (e.g., DigestedInformation, enhanced_context_retrieval) are allowed
- [x] All mandatory sections completed
- [x] No `[NEEDS CLARIFICATION]` markers remain
- [x] Requirements are testable and unambiguous
- [x] Scope is clearly bounded with explicit non-goals
- [x] Success criteria are measurable
