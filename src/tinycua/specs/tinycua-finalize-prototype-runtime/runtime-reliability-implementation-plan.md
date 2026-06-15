# Implementation: TinyCUA Runtime Reliability and Tool-Calling Hardening

This implementation plan records the remaining reliability work for PR #141 after
the prototype runtime was converted from a scaffold into a stateful TinyCUA loop.
It focuses on the issues observed during live local LLM validation: inconsistent
function-calling, hallucinated “no tool access” responses, noisy internal context,
and overly creative model settings.

## Context

- **Spec Reference**: `./spec.md`
- **Design Reference**: `./design.md` and `../../docs/design/`
- **Priority**: P0
- **Estimated Effort**: M

## Environment Pre-requisites

### Configuration

- Local OpenAI-compatible server variables for live acceptance:
  ```bash
  TINYCUA_LIVE_LLM=1
  OPENAI_CHAT_COMPLETIONS_BASE_URL=http://localhost:1234/v1
  OPENAI_CHAT_COMPLETIONS_MODEL=qwen/qwen3.5-4b
  OPENAI_CHAT_COMPLETIONS_API_KEY=tinycua-local-test
  TINYCUA_BASE_URL=http://localhost:1234/v1
  TINYCUA_MODEL=qwen/qwen3.5-4b
  TINYCUA_API_KEY=tinycua-local-test
  ```

### Running Services

| Service | Required | How to Start | Health Check |
|---------|----------|--------------|--------------|
| Local OpenAI-compatible LLM server | Yes for live acceptance | Start server externally | `curl -sS http://localhost:1234/v1/models` |

### Data / Fixtures

- **None** — deterministic tests use in-repo fixtures and mocks.

### Access / Permissions

- **None** — live tests use local endpoint credentials only.

### Developer Tooling

- **Runtime**: Python via `uv`
- **Package manager**: `uv`
- **Additional CLI tools**: `curl` for local server health checks

---

## Current Implemented Progress

The current branch already implements and verifies a large portion of the final
prototype runtime:

- Session-bound task and todo stores.
- Typed task tree, active traversal, transitions, artifacts, reviewer decisions,
  snapshots, and transition logs.
- Provider-compatible tool result feedback messages.
- Workspace-bound native file/shell/python tools and optional native tool factory API.
- Concrete task analyzer, assessor, executor, reviewer, aggregation, and effort nodes.
- State-driven worker runtime controller with retry/replan/open-question paths.
- Final-response event capture and synthetic terminal fallback disabled by default.
- Retry exhaustion moved out of reusable `session_context` into diagnostics and
  internal audit records.
- ResponseNode opt-in digester suspension/resumption hook.
- Cache-backed enhanced context retrieval with scoped workspace cache files.
- AggregatedResult publication for ResponseNode consumption.
- CLI exports for execution trace, state snapshot, task tree, and final response events.
- TinyCUA factory default model temperature lowered to `0.1` unless explicitly set.
- QueryAnalyst and Worker route nodes now force route tool choice from TinyCUA
  without modifying `src/tinycua-sdk/`.
- Local OpenAI-compatible Chat Completions endpoints use `tool_choice="required"`
  with the LLM-visible tool list restricted to the single required route tool;
  remote Chat Completions providers use the OpenAI function object form.
- Required-route failures are single-attempt failovers so local models do not
  receive retry continuations and generate retry-spam text when function calling
  is ignored.
- Required-route prompts no longer include “If tools are unavailable” fallback
  language.
- LLM-bound internal context now renders known TinyCUA model payloads as compact
  bounded JSON and excludes retry/tool-only audit records from final prompts.

Recent deterministic verification:

```bash
cd src/tinycua && uv run pytest \
  tests/unit/test_design_gap_contracts.py \
  tests/unit/test_native_tools_workspace.py \
  tests/unit/test_factory_native_tools.py \
  tests/unit/test_final_response_contract.py \
  tests/unit/test_worker_runtime_controller.py \
  tests/unit/test_no_runtime_stubs.py \
  tests/unit/test_native_tools_files.py \
  tests/unit/test_native_tools_shell.py \
  tests/unit/test_native_tools_python.py \
  tests/unit/test_factory.py \
  tests/unit/test_tinycua_loop.py \
  tests/unit/test_retry_validation.py \
  tests/unit/test_decision_node_retry.py \
  tests/unit/test_tool_result_feedback.py \
  tests/unit/test_message_contract.py \
  tests/integration/test_final_prototype_runtime.py \
  tests/integration/test_notebook_contract.py \
  tests/integration/test_native_tools_files.py \
  tests/integration/test_native_tools_shell.py \
  tests/integration/test_native_tools_python.py \
  tests/integration/test_retry_integration.py \
  tests/integration/test_cli_run.py -q
```

Result: `164 passed, 2 warnings in 6.44s`.

---

## Success Criteria — Integration Tests (TDD First)

The next reliability pass should add tests before implementation for the
remaining failure modes observed in live logs.

### Key Test Scenarios

- [x] **Forced decision tool choice**: QueryAnalyst and Worker route calls send
  provider payloads with `tool_choice` forcing the required route-selection tool,
  not only `tool_choice="auto"`.
- [x] **No “tools unavailable” fallback prompt**: Required-tool decision node
  prompts do not instruct the model to answer with text if tools are unavailable.
- [x] **Clean final prompts**: ResponseNode input excludes retry diagnostics,
  raw object dumps, duplicate digests, and internal route retries.
- [x] **Structured internal context**: DigestedInformation, AggregatedResult,
  task snapshots, and tool results are rendered as compact JSON or concise
  summaries, not Python repr strings.
- [ ] **Live worker acceptance**: Local model completes passthrough and worker
  lifecycle without final-response retry spam or “I do not have tool access” text.
- [ ] **Notebook acceptance**: Notebook completes live, displays final response,
  task tree, tool results, state snapshot, and no synthetic-success markers.

## Verification Plan

### Automated Tests

- [x] Deterministic provider payload tests for `tool_choice` forcing.
- [x] Unit tests for prompt text of QueryAnalyst and Worker required-tool nodes.
- [x] Unit tests for compact internal context serialization.
- [ ] Integration tests for full worker lifecycle and final response cleanliness.
- [ ] Existing targeted suite:
  `cd src/tinycua && uv run pytest tests/unit/test_design_gap_contracts.py tests/integration/test_final_prototype_runtime.py -q`
- [ ] Broader deterministic suite from Current Implemented Progress.
- [ ] Live LLM suite:
  ```bash
  cd src/tinycua && TINYCUA_LIVE_LLM=1 \
    OPENAI_CHAT_COMPLETIONS_BASE_URL=http://localhost:1234/v1 \
    OPENAI_CHAT_COMPLETIONS_MODEL=qwen/qwen3.5-4b \
    OPENAI_CHAT_COMPLETIONS_API_KEY=tinycua-local-test \
    TINYCUA_BASE_URL=http://localhost:1234/v1 \
    TINYCUA_MODEL=qwen/qwen3.5-4b \
    TINYCUA_API_KEY=tinycua-local-test \
    uv run pytest tests/integration/test_default_agent_flow_live.py tests/integration/test_final_prototype_live.py -q
  ```
- [ ] Live notebook contract:
  ```bash
  cd src/tinycua && TINYCUA_LIVE_LLM=1 \
    OPENAI_CHAT_COMPLETIONS_BASE_URL=http://localhost:1234/v1 \
    OPENAI_CHAT_COMPLETIONS_MODEL=qwen/qwen3.5-4b \
    OPENAI_CHAT_COMPLETIONS_API_KEY=tinycua-local-test \
    TINYCUA_BASE_URL=http://localhost:1234/v1 \
    TINYCUA_MODEL=qwen/qwen3.5-4b \
    TINYCUA_API_KEY=tinycua-local-test \
    uv run pytest tests/integration/test_notebook_contract_live.py -q
  ```

### Manual Verification

- [ ] Inspect local LLM server request payloads and confirm `tools` is present.
- [ ] Inspect local LLM server request payloads and confirm route nodes use forced
  `tool_choice` when route tool calls are required.
- [ ] Confirm `temperature` is `0.1` by default for TinyCUA-created agents unless
  explicitly overridden.
- [ ] Confirm final responses do not include retry diagnostics or Python object reprs.

### Latest Deterministic Verification

```bash
cd src/tinycua && uv run pytest \
  tests/unit/test_design_gap_contracts.py \
  tests/unit/test_native_tools_workspace.py \
  tests/unit/test_factory_native_tools.py \
  tests/unit/test_final_response_contract.py \
  tests/unit/test_worker_runtime_controller.py \
  tests/unit/test_no_runtime_stubs.py \
  tests/unit/test_native_tools_files.py \
  tests/unit/test_native_tools_shell.py \
  tests/unit/test_native_tools_python.py \
  tests/unit/test_factory.py \
  tests/unit/test_tinycua_loop.py \
  tests/unit/test_retry_validation.py \
  tests/unit/test_decision_node_retry.py \
  tests/unit/test_tool_result_feedback.py \
  tests/unit/test_message_contract.py \
  tests/unit/test_route_contracts.py \
  tests/unit/test_route_tool_choice.py \
  tests/integration/test_final_prototype_runtime.py \
  tests/integration/test_notebook_contract.py \
  tests/integration/test_native_tools_files.py \
  tests/integration/test_native_tools_shell.py \
  tests/integration/test_native_tools_python.py \
  tests/integration/test_retry_integration.py \
  tests/integration/test_cli_run.py \
  tests/integration/test_streaming.py -q
```

Result: `179 passed, 2 warnings in 9.94s`.

### Latest Live Verification

```bash
cd src/tinycua && TINYCUA_LIVE_LLM=1 \
  OPENAI_CHAT_COMPLETIONS_BASE_URL=http://localhost:1234/v1 \
  OPENAI_CHAT_COMPLETIONS_MODEL=qwen/qwen3.5-4b \
  OPENAI_CHAT_COMPLETIONS_API_KEY=tinycua-local-test \
  TINYCUA_BASE_URL=http://localhost:1234/v1 \
  TINYCUA_MODEL=qwen/qwen3.5-4b \
  TINYCUA_API_KEY=tinycua-local-test \
  uv run pytest tests/integration/test_default_agent_flow_live.py \
    tests/integration/test_final_prototype_live.py -q
```

Result: `6 passed in 543.76s (0:09:03)`.

```bash
cd src/tinycua && TINYCUA_LIVE_LLM=1 \
  OPENAI_CHAT_COMPLETIONS_BASE_URL=http://localhost:1234/v1 \
  OPENAI_CHAT_COMPLETIONS_MODEL=qwen/qwen3.5-4b \
  OPENAI_CHAT_COMPLETIONS_API_KEY=tinycua-local-test \
  TINYCUA_BASE_URL=http://localhost:1234/v1 \
  TINYCUA_MODEL=qwen/qwen3.5-4b \
  TINYCUA_API_KEY=tinycua-local-test \
  uv run pytest tests/integration/test_notebook_contract_live.py -q
```

Result: `1 passed, 1 warning in 160.08s (0:02:40)`.

### Performance Considerations

- [ ] Ensure context-cache files are bounded to selected context only.
- [ ] Ensure task-tree snapshots and trace exports remain bounded in notebook/CLI demos.

## Proposed Changes

### Provider Payload and Tool-Choice Reliability

#### MODIFY `tinycua.loops.tinycua_loop.TinyCUALoop`

- **Description of change**: Add a node-aware LLM call path that can request
  forced `tool_choice` for required route tools when the provider supports it.
- **Rationale**: SDK currently exposes tools correctly, but Chat Completions
  sends `tool_choice="auto"`. Weak local function-calling models often ignore
  auto tools and respond with text such as “I do not have access to tools.”

#### MODIFY `tinycua_sdk` interaction boundary indirectly from TinyCUA

- **Description of change**: Do not modify SDK source in this PR. If SDK does
  not expose per-call model settings, TinyCUA should pass tool-choice intent via
  a minimal, local wrapper or a carefully scoped provider payload hook in TinyCUA.
- **Rationale**: This PR's constraint is to avoid SDK changes while improving
  TinyCUA orchestration reliability.

### Prompt Hardening

#### MODIFY `tinycua.loops.query_analyst` and `tinycua.loops.worker`

- **Description of change**: Remove “If tools are unavailable” language from
  required-tool route nodes. Replace with explicit function-calling instructions
  and concise failure behavior.
- **Rationale**: The current wording can teach local models to bypass tool calls
  and answer directly.

### Structured Internal Context

#### NEW `tinycua.loops.context_rendering` or equivalent helper

- **Description**: Centralize compact serialization of internal objects before
  they become LLM-bound messages.
- **Dependencies**: `DigestedInformation`, `AggregatedResult`, task snapshots,
  diagnostics, and tool results.

#### MODIFY `tinycua.loops.node.build_messages_with_dedupe`

- **Description of change**: Render known internal payloads as bounded JSON or
  concise summaries and exclude internal diagnostics from LLM-bound context.
- **Rationale**: Python repr strings and repeated internal objects contribute to
  hallucination and local-model instability.

### Live Acceptance and Observability

#### MODIFY live tests under `tests/integration/`

- **Description of change**: Add assertions that route-node payloads expose
  tools, force route tool choice, and final responses are free from internal
  diagnostics.
- **Rationale**: Live logs revealed failures that deterministic tests did not
  previously catch.

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| TinyCUALoop | Modify | Node-aware provider options for route-tool enforcement and cleaner trace/audit separation. |
| QueryAnalyst / Worker | Modify | Remove tool-unavailable fallback wording and require actual function calls. |
| Context rendering | New | Bounded serialization path for internal LLM-bound context. |
| Tests | Modify/New | Payload-level and live cleanliness assertions. |

## Data Model Changes

```python
NodeExecutionOptions:
    required_tool_choice: str | None
    temperature: float | None
    max_tokens: int | None

ContextRenderPolicy:
    max_chars_per_entry: int
    include_diagnostics: bool = False
    known_type_renderers: dict[type, Callable]
```

## API Changes

No public API changes are required for this reliability pass. The existing public
factory behavior should remain:

```python
create_tinycua_agent(
    session=None,
    session_config=None,
    enable_native_tools=False,
    native_tool_policy=None,
    **agent_kwargs,
)
```

## Dependencies

### External Dependencies

No new external packages are planned.

### Internal Dependencies

- Depends on existing `TinyCUALoop`, node configs, and routing tool schemas.
- Blocks final live LLM acceptance and notebook acceptance sign-off.

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Local model still ignores forced tool choice | High | Add deterministic payload tests and live acceptance tests; consider model-specific fallback only after explicit invalid-route trace. |
| TinyCUA wrapper around SDK call becomes brittle | Medium | Keep SDK boundary minimal and isolated to TinyCUA runtime until SDK API can formally support per-call options. |
| Context rendering loses useful information | Medium | Use bounded structured summaries and keep full details in trace/state exports. |
| Live tests remain nondeterministic | Medium | Keep deterministic tests primary; live tests document exact env/model and assert broad but meaningful invariants. |

---

*Generated from spec.md, design.md, and live validation findings.*
*Last updated: 2026-06-15*
