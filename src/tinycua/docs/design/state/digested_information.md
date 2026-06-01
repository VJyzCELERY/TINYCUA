# Digested Information

> **File:** `docs/design/state/digested_information.md`
> **Package:** `tinycua.state.digested_information`
> **Last Updated:** 2026-05-31

---

## Role

`DigestedInformation` is produced by the Information Digester — a precision-oriented
summary for downstream agents (Task Analyzer, Primary Agent).

---

## Class Contract

**File:** `tinycua/state/digested_information.py`

```text
DigestedInformation extends StateObject
    · context_summary: str — compressed relevant context (markdown)
    · key_points: list[str] | None = None — key takeaway points
    · advisory_instructions: str | None = None — action-oriented guidance
    · constraints: list[str] | None = None — guardrails
    · known_gaps: list[str] | None = None — missing information
```

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Known gaps explicit | `known_gaps: list[str]` | Empty results documented rather than silently omitted |
| Advisory instructions separate | `advisory_instructions` | Guidance for downstream agents without polluting context_summary |

---

## See also

Prev : [Classification + `ContextEnhancedQuery`](classification.md) | Next : [`ReviewerDecision` + `ContextUpdate`](reviewer_decision.md)


## Related

- [Produced by InformationDigester](../agent_node/information_digester.md)
- [Stored in InformationDigesterState](information.md)
