# MetaGPT: Meta Programming for A Multi-Agent Collaborative Framework

**Authors:** Sirui Hong, Mingchen Zhuge, Jiaqi Chen, Xiawu Zheng, Yuheng Cheng, Ceyao Zhang, Jinlin Wang, Zili Wang, Steven Ka Shing Yau, Zijuan Lin, Liyang Zhou, Chenyu Ran, Lingfeng Xiao, Chenglin Wu, Jürgen Schmidhuber
**Year:** 2023
**Venue:** ICLR 2024
**Link:** https://arxiv.org/abs/2308.00352

## Key Contribution

Proposes **MetaGPT** — a meta-programming framework that encodes Standardized Operating Procedures (SOPs) into prompt sequences for multi-agent collaboration. Uses an **assembly line paradigm** to assign diverse roles to agents, breaking complex tasks into subtasks with intermediate result verification.

## Core Method

Two key mechanisms:
1. **SOP Encoding** — human workflows (e.g., software development lifecycle) are encoded into prompt sequences that agents follow
2. **Assembly Line Paradigm** — agents are assigned specialized roles (Product Manager → Architect → Engineer → QA) and work sequentially, each verifying intermediate results before passing to the next

Each agent has a defined role, access to shared documentation artifacts, and produces structured outputs that downstream agents consume.

## Key Results

- Generates more coherent solutions than previous chat-based multi-agent systems (CAMEL, AutoGen)
- Outperforms on collaborative software engineering benchmarks (MetaGPT vs. ChatDev, AgentVerse)
- Reduces cascading hallucinations through intermediate verification
- Produces structured artifacts (design docs, code, tests) instead of unstructured chat

## Limitations

| Limitation | Description |
|-----------|-------------|
| **Fixed role structure** | Roles are predefined (PM → Architect → Engineer → QA). Cannot adapt to tasks that don't fit this structure. |
| **No context isolation** | Agents share a workspace with full access to all artifacts — each agent can see everything, not just what it needs. |
| **Sequential bottleneck** | Assembly line is strictly sequential — parallel independent tasks are not exploited. |
| **Large model dependency** | Tested on GPT-4. Effectiveness on SLMs unestablished — SOP encoding and role-playing may require high-capacity models. |
| **Domain specificity** | Optimized for software engineering. Generalization to other domains (travel planning, research) is not demonstrated. |

## Relevance to TINYCUA

MetaGPT is the closest architectural predecessor to TINYCUA's Worker mode in terms of structured multi-agent collaboration. Both use specialized agents with defined roles working sequentially.

However, TINYCUA extends MetaGPT in critical ways:

| Aspect | MetaGPT | TINYCUA |
|--------|---------|---------|
| Role structure | Fixed roles (PM → Architect → Engineer → QA) | Fixed specialized agents (Query Analyst → Task Creator → Executor → Reviewer) |
| Context access | Shared workspace (full visibility) | Isolated context per agent (minimal exposure) |
| Task decomposition | Implicit in role structure | Explicit Task Creation loop (Assessor + Analyzer) |
| Verification | Intermediate artifact review | Result Reviewer with accept/retry/replan/escalate |
| Parallelism | Strictly sequential | Sequential with potential for parallel subtasks |
| Model size | GPT-4 | SLMs (1B-8B) |

TINYCUA's key innovation over MetaGPT: **context isolation**. MetaGPT agents share everything; TINYCUA agents get only what they need. This is critical for SLM viability.

## How to Cite

```
@inproceedings{hong2024metagpt,
  title={MetaGPT: Meta Programming for A Multi-Agent Collaborative Framework},
  author={Hong, Sirui and Zhuge, Mingchen and Chen, Jiaqi and Zheng, Xiawu and Cheng, Yuheng and Zhang, Ceyao and Wang, Jinlin and Wang, Zili and Yau, Steven Ka Shing and Lin, Zijuan and Zhou, Liyang and Ran, Chenyu and Xiao, Lingfeng and Wu, Chenglin and Schmidhuber, J{\"u}rgen},
  booktitle={International Conference on Learning Representations (ICLR)},
  year={2024}
}
```

## Connection in Lit Review

Position as the state-of-the-art in structured multi-agent collaboration. MetaGPT shows that SOP-based workflows + assembly line paradigm outperform chat-based multi-agent systems. TINYCUA builds on this by adding context isolation — MetaGPT agents share everything, TINYCUA agents get only what they need. This is the key difference that enables SLM viability.
