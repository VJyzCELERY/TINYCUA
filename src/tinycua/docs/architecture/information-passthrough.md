# Information Passthrough

> **Category:** Process Spec

> **File:** `architecture/information-passthrough.md`
> **See also:** [overview.md](overview.md), [query-analyst.md](query-analyst.md), [primary-agent.md](primary-agent.md)

---

## Role

This is **not an agent**. It is a deterministic non-agent process that receives the **Context Enhanced Query** from the Query Analyst and forwards it directly to the Primary Agent without any transformation.

This is a historical/simple forwarding node. In the current routing model, the Query Analyst can route directly to the Primary Agent with a `primary_agent` decision. The Primary Agent then decides whether it needs Information Digestion.

---

## Inputs / Outputs

**Input:** `context_enhanced_query` — from Query Analyst
**Output:** `context_enhanced_query` — forwarded unchanged to Primary Agent

---

## Internal Flow

```mermaid
flowchart TD
    subgraph IP_FLOW["Information Passthrough — Internal Flow"]
        RECEIVE["Receive:\n- context_enhanced_query\n(from Query Analyst)"]
        FORWARD["Forward to Primary Agent"]
    end

    RECEIVE --> FORWARD
```

---

## Design Notes

- No LLM call
- No transformation
- No looping
- Exists as a historical/simple routing node for direct Primary Agent routing
- The Primary Agent may receive mode metadata from the router, but the Context Enhanced Query itself is forwarded unchanged
