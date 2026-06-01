# Agent State

> **File:** `docs/design/state/agent_state.md`
> **Package:** `tinycua.state.agent_state`
> **Last Updated:** 2026-06-01

---

## Role

`AgentState` is the base state object for every AgentNode. It tracks generic lifecycle
(type, status, failure count, config) and serves as the **serialization bridge** for
cross-node structured data — every agent-specific state class extends `AgentState` and
inherits YAML front-matter serialization.

When a caller needs to pass structured output from one AgentNode to another, it
serializes the state object via `to_yaml()` (which wraps the fields in a `---`
delimited YAML block with the `type` field as identifier). The receiver calls
`AgentState.from_string(s)` to auto-detect the type and reconstruct the correct
subclass instance. If the string has no YAML front-matter, it is treated as a plain
string — no reconstruction is attempted.

Stored directly on `Session.agent_state` — each session node holds its own agent's
state and config. To find which agent is currently active, walk the session tree to
the deepest leaf via `session.get_active_session()`.

---

## Class Contract

**File:** `tinycua/state/agent_state.py`

```text
AgentState <: StateObject   ── base for all agent-specific state classes

Fields:
  · type: str                                    # agent identity: "query_analyst", "task_executor", etc.
  · status: AgentStatus = "idle"                 # idle | running | blocked | terminated
  · failure: int = 0                             # accumulated failure count from child sessions
  · agent_config: AgentConfigBase | None = None  # source of truth for model, compaction_strategy, extra_tools
```

`AgentStatus = Literal["idle", "running", "blocked", "terminated"]`

---

## State Type Hierarchy

```
AgentState (base)
 ├── QueryAnalystState
 ├── InformationDigesterState
 ├── TaskAnalyzerState
 ├── TaskAssessorState
 ├── TaskExecutorState
 ├── ResultReviewerState
 └── PrimaryAgentState
```

Each subclass adds its own output fields (see [information.md](information.md)).
Every subclass inherits `type`, `status`, `failure`, `agent_config`, and
serialization methods from `AgentState`.

---

## Serialization — YAML Front-Matter Bridge

Every `AgentState` subclass can serialize itself to a YAML front-matter string
for structured pass-through between AgentNodes. The `type` field inside the YAML
block identifies which subclass the data belongs to.

### `to_yaml() → str`

```text
AgentState.to_yaml() → str
  · Serialize this state object to a YAML front-matter block
  · Output format:
      ---
      type: query_analyst
      status: terminated
      failure: 0
      classification: passthrough
      ...
      ---
  · Fields are YAML-serialized via StateObject.to_dict() → yaml.dump()
  · The caller prepends/appends plain text around the block as needed:
      query = state.to_yaml() + "\n" + user_query
```

### `from_string(s: str) → AgentState | None` (classmethod)

```text
AgentState.from_string(s: str) → AgentState | None
  · Scans input for "---\n" ... "\n---" YAML front-matter block
  · If NO front-matter found → returns None (caller treats as plain string)
  · If front-matter found:
      · Parse the YAML block into a dict
      · Read the "type" field from the parsed dict
      · Look up the corresponding AgentState subclass via registry:
          _AGENT_STATE_REGISTRY = {
              "query_analyst": QueryAnalystState,
              "information_digester": InformationDigesterState,
              ...
          }
      · Call Subclass.from_dict(parsed_dict) → instance
      · Return the reconstructed instance
  · If "type" is unknown → raise ValueError("Unknown AgentState type: {type}")
```

### `from_string_strict(s: str, expected_type: type[AgentState]) → AgentState` (classmethod)

```text
AgentState.from_string_strict(s: str, expected_type: type) → AgentState
  · Like from_string(s), but also validates that the reconstructed type matches expected_type
  · If type mismatch → raise ValueError(f"Expected {expected_type.__name__}, got {actual.type}")
```

### Registry

```text
_AGENT_STATE_REGISTRY: dict[str, type[AgentState]] = {
    "query_analyst": QueryAnalystState,
    "information_digester": InformationDigesterState,
    "task_analyzer": TaskAnalyzerState,
    "task_assessor": TaskAssessorState,
    "task_executor": TaskExecutorState,
    "result_reviewer": ResultReviewerState,
    "primary_agent": PrimaryAgentState,
}
```

---

## Usage — Cross-Node Structured Data Pass-Through

```text
# Sender (TinyCUA graph):
qa_state = query_analyst.session.agent_state  # QueryAnalystState instance
query = qa_state.to_yaml() + "\n" + user_query
# to_yaml() outputs:
#   ---
#   type: query_analyst
#   status: terminated
#   failure: 0
#   classification: passthrough
#   context: <analysis markdown>
#   ---
#
# <user query text>

# Receiver (PrimaryAgentNode):
parsed = AgentState.from_string(query)
if parsed is not None:
    # parsed is a QueryAnalystState instance with all fields populated
    ceq = ContextEnhancedQuery(context=parsed.context, query=parsed.user_query)
    self.session.append_agent_context(ceq.context)
else:
    # Plain string — no structured data
    pass

# During execution:
session.agent_state.type → "task_executor"
session.agent_state.status → "running"
session.agent_state.failure → 0

# Loop-owned final output:
task_executor_state = TaskExecutorState(
    type="task_executor",
    status="terminated",
    task_result=TaskResult(status="completed", result="...")
)
session.agent_state = task_executor_state
```

---

## Failure Propagation

`failure: int` replaces the old `consecutive_failures`. Instead of counting consecutive
failures within one agent, it accumulates failures from child sessions. Each node
decides its own behavior based on the accumulated `failure` value.

```text
# Child terminates with failure=2:
parent.session.terminate_child(child.session)
  → parent.session.agent_state.failure += child.session.agent_state.failure
  → parent.failure becomes 0 + 2 = 2

# Another child terminates with failure=3:
parent.session.terminate_child(another_child.session)
  → parent.session.agent_state.failure += another_child.session.agent_state.failure
  → parent.failure becomes 2 + 3 = 5
```

Each AgentNode defines its own policy for handling `failure`:

| AgentNode | Behavior at failure >= N |
|-----------|-------------------------|
| `QueryAnalyst` | No special behavior — transient; always terminates |
| `InformationDigester` | Max retries; if exceeded, produce partial digest |
| `TaskAnalyzer` | May trigger task tree pruning or fallback decomposition |
| `TaskAssessor` | May trigger early stop verdict |
| `TaskExecutor` | Loop may terminate early (blocked/failed) |
| `ResultReviewer` | At failure >= 5: may trigger special review behavior (e.g., force accept with context annotation) |
| `PrimaryAgent` | No special behavior |

`failure` is **never reset** by the base class. Subclasses may reset it on specific
lifecycle transitions (e.g., new task execution resets TaskExecutor's failure).

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Flat lifecycle tracking | `type` + `status` + `failure` | Simple state machine; no complex resume logic |
| `type` as discriminator | String matching agent name | Serves dual purpose: identity + front-matter type detection |
| YAML front-matter | `to_yaml()` / `from_string()` with `type` field | Structured cross-node pass-through without coupling graph to internal formats |
| Auto-detect via registry | `_AGENT_STATE_REGISTRY` maps `type` → subclass | Caller doesn't need to specify target type; `from_string()` handles it |
| No front-matter = plain string | `from_string()` returns `None` | Graceful fallback — receivers always check for structured data |
| Failure as aggregate | `failure: int` accumulated from children | Each node defines its own escalation behavior; no single global threshold |
| Task tracked on Session | `task` on `Session`, not `active_task_id` on AgentState | Single source of truth; all agents share the same task tree |
| Config on AgentState | `agent_config: AgentConfigBase` | Config source of truth for AgentNode, loop, and Session compaction |
| Stored per session node | `Session.agent_state` on each session | Walk the tree to find who's active; no central dict needed |
| Resume via tree walk | `get_active_session()` → `agent_state` | Deepest leaf IS the active agent; no explicit routing key |

---

## See also

Prev : [Per-Agent State Classes](information.md) | Next : [`Task` Tree + `TaskResult`](task.md)

## Related

- [Stored on Session.agent_state per node](session.md)
- [Per-agent state subclasses with specific output fields](information.md)
- [agent_config provides context window](../config/agents.md)
- [YAML front-matter cross-node pattern](../orchestration/overview.md#agentnode-input-contract)
