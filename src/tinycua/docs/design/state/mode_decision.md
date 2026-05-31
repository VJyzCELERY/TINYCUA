# Mode Decision

> **File:** `docs/design/state/mode_decision.md`
> **Package:** `tinycua.state.mode_decision`
> **Last Updated:** 2026-05-31

---

## Role

`ContextEnhancedQuery` and `ModeDecision` are produced by the Query Analyst.
`ContextEnhancedQuery` wraps the agent's context-analysis output with the original
user query for downstream consumption by InformationDigester.
`ModeDecision` is the routing verdict with confidence scoring.

---

## Class Contract

**File:** `tinycua/state/mode_decision.py`

```python
@dataclass
class ContextEnhancedQuery(StateObject):
    context: str       # agent output: markdown with relevant context, keywords, etc.
    query: str         # original user query (passed through unchanged)


@dataclass
class ModeDecision(StateObject):
    mode: ModeType                          # passthrough | worker | uncertain
    score: float                            # confidence score for mode choice
    confidence: float                       # overall confidence
    reasons: list[str]                      # reasons for chosen mode
    uncertain_next_action: UncertainNextAction | None = None  # required when uncertain
```

**Type aliases:**
```python
ModeType = Literal["passthrough", "worker", "uncertain"]
UncertainNextAction = Literal["ask_user", "explore"]
```

---

## Validation

- `mode` must be one of `passthrough`, `worker`, `uncertain`
- `uncertain_next_action` (if set) must be `ask_user` or `explore`
- Cross-field: if `mode == "uncertain"`, `uncertain_next_action` is **required**

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Mode + next action separate | `mode` + `uncertain_next_action` | `uncertain_next_action` only meaningful for uncertain mode |
| Cross-field validation | `__post_init__` check | Catch missing next_action at construction time |
| Context + query separate | `ContextEnhancedQuery.context` + `.query` | QueryAnalyst output (context) and original query are orthogonal; downstream agents receive both |


---


---


---

## See also

Prev : [`Task` Tree + `TaskResult`](task.md) | Next : [`DigestedInformation`](digested_information.md)


## Related

- [Produced by QueryAnalyst](../agents/query_analyst.md)
- [Stored in QueryAnalystState](information.md)
