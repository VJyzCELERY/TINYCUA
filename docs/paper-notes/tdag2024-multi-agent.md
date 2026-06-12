# TDAG: A Multi-Agent Framework based on Dynamic Task Decomposition and Agent Generation

**Authors:** Yaoxiang Wang, Zhiyong Wu, Junfeng Yao, Jinsong Su
**Year:** 2024
**Venue:** Neural Networks
**Link:** https://arxiv.org/abs/2402.10178

## Key Contribution

Proposes **TDAG** — a multi-agent framework that dynamically decomposes complex tasks into smaller subtasks and assigns each to a specifically generated subagent. Unlike static multi-agent systems, TDAG adapts agent generation to task requirements at runtime.

## Core Method

Two key mechanisms:
1. **Dynamic Task Decomposition** — breaks complex tasks into subtasks based on task structure, not predefined roles
2. **Agent Generation** — creates specialized subagents for each subtask, each with only the context relevant to its subtask

Each sub-agent operates with isolated context — only the information needed for its specific subtask.

## Key Results

- Significantly outperforms established baselines on ItineraryBench (travel planning benchmark)
- Demonstrates superior adaptability and context awareness in complex task scenarios
- Shows improved memory, planning, and tool usage across tasks of varying complexity

## Limitations

| Limitation | Description |
|-----------|-------------|
| **Agent generation overhead** | Dynamically generating agents for each subtask adds computational cost — not suitable for latency-sensitive applications. |
| **No fixed agent hierarchy** | Dynamic generation means agent roles are not predictable or reusable across tasks — harder to debug and verify. |
| **Context isolation scope** | While each sub-agent gets only its subtask's context, the decomposition is subtask-level, not context-engineering-level. The system does not actively compress or compact context before assignment. |
| **Large model dependency** | Tested on GPT-4 class models. Effectiveness on SLMs (1B-8B) is unestablished — the decomposition and generation steps themselves may require high-capacity models. |
| **No external verification** | Subtask results are aggregated without a formal review mechanism — errors in individual subtasks can propagate to the final output. |

## Relevance to TINYCUA

TDAG is the closest architectural predecessor to TINYCUA's dynamic task decomposition. Both systems decompose tasks and assign each to a specialized agent with isolated context.

However, TINYCUA extends TDAG in critical ways:

| Aspect | TDAG | TINYCUA |
|--------|------|---------|
| Decomposition | Dynamic, runtime-generated | Upfront Task Creation (assessor + analyzer loop) |
| Agent generation | New agent per subtask | Fixed specialized agents (reusable, predictable) |
| Context isolation | Subtask-level only | Subtask-level + context compaction |
| Verification | None (aggregation only) | Result Reviewer validates each subtask result |
| Model size | GPT-4 class | SLMs (1B-8B) |
| Cost | High (agent generation per task) | Low (fixed agent pool, reusable) |

TINYCUA's key innovation over TDAG: **fixed specialized agents** with **context compaction** instead of dynamic agent generation. This makes the system predictable, debuggable, and SLM-compatible.

## How to Cite

```
@article{wang2024tdag,
  title={TDAG: A Multi-Agent Framework based on Dynamic Task Decomposition and Agent Generation},
  author={Wang, Yaoxiang and Wu, Zhiyong and Yao, Junfeng and Su, Jinsong},
  journal={Neural Networks},
  year={2024}
}
```

## Connection in Lit Review

Position as the state-of-the-art in dynamic multi-agent decomposition. TDAG shows that decomposing tasks + assigning isolated sub-agents improves performance. TINYCUA builds on this by: (1) replacing dynamic agent generation with fixed specialized agents, (2) adding context compaction before assignment, and (3) adding external verification via Result Reviewer. These changes make multi-agent orchestration viable for SLMs.
