# Mode Decision

> **File:** `docs/design/state/mode_decision.md`
> **Package:** `tinycua.state.mode_decision`
> **Last Updated:** 2026-05-31

---

## Role

`ContextEnhancedQuery` and `ModeDecision` are produced by the Query Analyst.
`ContextEnhancedQuery` enriches the user query with session context.
`ModeDecision` is the routing verdict with confidence scoring.

---

## Class Contract

**File:** `tinycua/state/mode_decision.py`

```python
@dataclass
class ContextEnhancedQuery(StateObject):
    enhanced_query: str        # enhanced query text with session context

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
| Context injected separately | `ContextEnhancedQuery` distinct from `ModeDecision` | Query enrichment and routing are separate concerns |


---


---


---

## See also

Prev : [`Task` Tree + `TaskResult`](task.md) | Next : [`DigestedInformation`](digested_information.md)


## Related

- [Produced by QueryAnalyst](../agents/query_analyst.md)
- [Stored in QueryAnalystState](information.md)
