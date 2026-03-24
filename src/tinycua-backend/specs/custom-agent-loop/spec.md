# Feature Specification: Custom Agent Loop

**Status**: Draft
**Created**: 2026-03-24
**Subproject(s) Affected**: tinycua-backend, tinycua-sdk, tinycua-runner

---

## Problem Statement

**Goals**:
- Allow users to define custom agent execution strategies (e.g., hierarchical, ReAct, plan-execute)
- Support Plan mode (read-only) vs Execute mode as runtime parameter
- Store custom loop code in agent config
- Provide DefaultLoop base class that users can extend

**Gaps**:
- Current agent loop is hardcoded in runner (direct vs plan mode only)
- No way for users to define custom execution strategies
- Cannot define complex loops like hierarchical decomposition

**Non-Goals**:
- Sandboxing custom loop code (runs in same environment as runner)
- Runtime loop switching (loop is defined at agent creation)
- Loop "name" property (class name serves as identifier)

---

## User Scenarios & Testing

### Primary Scenario

A developer wants to create an agent with a custom execution loop:

1. Define a custom `DefaultLoop` subclass in Python
2. Upload the loop code when creating an agent
3. Agent runs using the custom loop

### Secondary Scenario

A developer wants to preview agent actions without executing:

1. Create agent with tools (tools have `allowed_in_plan_mode` metadata)
2. Run agent with `plan_mode=True`
3. Agent returns plan without executing non-plan-mode tools

### Acceptance Scenarios

#### Custom Loop Definition
1. **Given** a custom DefaultLoop subclass, **when** stored in agent config, **then** runner loads and executes it.

2. **Given** an agent with custom loop, **when** `agent.run()` is called, **then** the custom loop's `run()` method is executed.

3. **Given** no custom loop defined, **when** agent runs, **then** built-in DefaultLoop is used.

#### Plan Mode Runtime Parameter
4. **Given** a tool with `allowed_in_plan_mode=False`, **when** agent runs with `plan_mode=True`, **then** the tool cannot be called.

5. **Given** a tool with `allowed_in_plan_mode=True`, **when** agent runs with `plan_mode=True`, **then** the tool can be called.

6. **Given** a tool without `allowed_in_plan_mode` set, **when** agent runs with `plan_mode=True`, **then** the tool can be called (defaults to True).

7. **Given** an agent run with `plan_mode=True`, **when** agent executes, **then** only plan-mode-allowed tools can be called.

8. **Given** an agent run with `plan_mode=False`, **when** agent executes, **then** all tools can be called.

#### Subagent Loops
9. **Given** an agent with subagents, **when** each subagent runs, **then** each uses its own loop (from its own config).

#### Trace/Verbose/SSE
10. **Given** any loop (default or custom), **when** `trace=True`, **then** RunResult is returned with trace data.

11. **Given** any loop, **when** `stream_sse=True`, **then** AsyncIterator[StreamEvent] is returned.

---

## Requirements

### Core Requirements

1. **DefaultLoop Base Class**
   - Single base class users extend
   - Provides helper methods for custom loops
   - Wraps Runner for execution

2. **Runner Minimal Interface**
   - `run()` - basic execution with trace support
   - `run_sse()` - streaming with SSE events
   - `execute_tool()` - execute single tool
   - `call_llm()` - call LLM directly

3. **Tool Metadata**
   - Add `allowed_in_plan_mode: bool = True` to tool definition

4. **Agent Config Storage**
   - Store `loop_code: str` - Python code defining custom loop class
   - Store `loop_class: str` - name of class to instantiate

5. **Plan Mode Runtime**
   - `plan_mode` passed in `.run()` call
   - Not stored in agent config
   - Passed to loop via kwargs

---

## API Changes

### Agent Creation (POST /v1/agents)

```json
{
  "name": "my-agent",
  "config": {
    "instructions": "You are helpful.",
    "provider": "openai",
    "model": "gpt-4",
    "tools": ["tool_id_1", "tool_id_2"],
    "loop_code": "class MyLoop(DefaultLoop):\n    ...",
    "loop_class": "MyLoop"
  }
}
```

### Run Request (POST /v1/agents/{id}/run)

```json
{
  "user_input": "Do something",
  "plan_mode": false,
  "trace": false,
  "verbose": false,
  "stream_sse": false
}
```

---

## Acceptance Criteria

| ID | Criterion | Test Method |
|----|-----------|--------------|
| AC1 | Custom loop code can be stored in agent config | Create agent with loop_code, verify stored |
| AC2 | Custom loop is executed when agent runs | Agent with custom loop runs custom logic |
| AC3 | DefaultLoop used when no custom loop | Agent without loop_code uses default |
| AC4 | Tool with allowed_in_plan_mode=False blocked in plan mode | Run with plan_mode=True, tool call fails |
| AC5 | Tool with allowed_in_plan_mode=True works in plan mode | Run with plan_mode=True, tool call succeeds |
| AC6 | All tools work in execute mode (plan_mode=False) | Run with plan_mode=False, all tools work |
| AC7 | Subagents use their own loop | Each subagent runs with its own config/loop |
| AC8 | trace=True returns RunResult with trace | Custom loop with trace=True returns RunResult |
| AC9 | stream_sse=True returns StreamEvents | Custom loop with stream_sse=True yields events |
