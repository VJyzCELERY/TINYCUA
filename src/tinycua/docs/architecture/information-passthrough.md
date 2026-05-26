# Information Passthrough

> **Category:** Process Spec

> **File:** `architecture/information-passthrough.md`
> **See also:** [Overview.md](overview.md), [Query_Analyst.md](query-analyst.md), [Primary_Agent.md](primary-agent.md)

---

## Role

This is **not an agent**. It is a deterministic non-agent process that receives the **Context Enhanced Query** from the Query Analyst and forwards it directly to the Primary Agent without any transformation.

Used in **Passthrough Mode** when the Query Analyst determines the task is small.

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
- Exists purely as a routing node to keep the architecture diagram symmetric
- The Primary Agent cannot distinguish between Passthrough and Worker mode from the input format alone — it just receives data
