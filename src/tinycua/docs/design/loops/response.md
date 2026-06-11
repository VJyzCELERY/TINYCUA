# TinyCUAResponseNode

> **Package:** `tinycua.loops.response_node`
> **Status:** Implemented (Milestone 3.5)

## Role

`TinyCUAResponseNode` is a concrete `ProcessNode` and the terminal/suspendable response
node. It steers final synthesis from prior node response/continuation input and produces
the user-facing answer. It is not a generic `PrimaryNode`.

## Non-Responsibilities

- Does not own detailed task traversal or task-tree search (that belongs to
  ResultAggregation and task helpers).
- Does not execute tasks.
- Does not review results.

## Three-Phase Execution

ResponseNode processes in three phases on every `__call__`:

1. **Context Sufficiency Check**: Analyzes whether available context is sufficient.
2. **Optional Context Gathering**: If insufficient, either suspends for digester or uses tools directly.
3. **Final Response Synthesis**: Builds LLM input and produces the normalized terminal output.

```text
ResponseNode enters:
  1. Build ResponseContext from NodeInput.
  2. Analyze available context (_check_context_sufficiency).
     → If sufficient: skip to phase 3.
     → If insufficient:
        a. If digester enabled: set _needs_digestion flag, return early;
           actual suspension via on_complete() prepends InformationDigesterNode.
        b. If digester unavailable: use allowed tools directly (_gather_context_via_tools).
  3. Synthesize final response (_synthesize_response).
  4. Normalize output to string (terminal normalization).
```

## Inputs

- `AggregatedResult` from ResultAggregationNode.
- Accumulated root/session context.
- Latest propagated node output.
- Optional digested information from InformationDigesterNode.
- Optional continuation payload from MandatoryPassthrough.

## Outputs / State Produced

- Final user-facing response string (always normalized to `LLMResult` with string `content`).

## Data Model

```python
@dataclass
class ResponseContext:
    aggregated_result: AggregatedResult | None  # from ResultAggregationNode
    session_context: list[dict[str, Any]]        # propagated context
    latest_output: str | None                    # latest node output
    continuation_payload: dict | None            # user continuation data
```

## Context Sufficiency Check

Sufficiency is determined by checking if `aggregated_result` is not None and contains
at least one of `task_summaries` or `final_context`. This provides a clear, testable
criterion. Thresholds are configurable via `NodeConfig.metadata`.

## Tools

| Tool Scope | Description |
|------------|-------------|
| Information digestion request | May request InformationDigesterNode for additional context. |
| Direct tool access | May use allowed tools directly when context is insufficient. |

ResponseNode shares the same base toolset as TaskExecutor via `NodeToolPolicy(include_agent_tools="all")`.

## Queue Behavior / `on_complete()`

```text
ResponseNode completes normally:
  → Terminal node: queue processing ends.
  → Return final response string.

ResponseNode suspends for digestion:
  → on_complete() detects _needs_digestion flag
  → Calls queue.suspend_current_and_prepend([InformationDigesterNode(parent=ResponseNode)])
  → Digester completes → ResponseNode resumes.
```

### Suspension and Resume

When ResponseNode suspends for information digestion:

1. `__call__` sets `_needs_digestion = True` and returns early.
2. `on_complete()` calls `queue.suspend_current_and_prepend([InformationDigesterNode(parent=self)])`.
3. Digester uses selected-output propagation targeting its parent session.
4. Digest lands in suspended ResponseNode's `session_context`.
5. ResponseNode resumes and re-checks sufficiency before synthesizing.

A `max_digest_attempts` counter prevents infinite loops (digester → response → digester).

## Continuation Routing

ResponseNode supports consolidated continuation via `MandatoryPassthrough`:

- When `_continuation_payload` is set, the continuation is delivered directly without LLM rerouting.
- The loop's `_execute_node` handles routing continuation payloads to the active ResponseNode session.

## Failure / Retry Behavior

- Retries according to `NodeRetryPolicy`.
- On retry exhaustion, returns a configurable fallback message (via `NodeConfig.metadata["fallback_message"]`) instead of raising, maintaining graceful terminal behavior.

## Related Config

- `NodeConfigBase.metadata["digester_enabled"]` — enable/disable digester path (default: True).
- `NodeConfigBase.metadata["fallback_message"]` — configurable fallback on retry exhaustion.
- `NodeToolPolicy(include_agent_tools="all")` — shares same toolset as TaskExecutor.
- `NodeRetryPolicy` — retry behavior.

## Related

- [`node.md`](node.md)
- [`node_queue.md`](node_queue.md)
- [`result_aggregation.md`](result_aggregation.md)
- [`information_digester.md`](information_digester.md)
