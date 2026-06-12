# AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversation

**Authors:** Qingyun Wu, Gagan Bansal, Jieyu Zhang, Yiran Wu, Beibin Li, Erkang Zhu, Li Jiang, Xiaoyun Zhang, Shaokun Zhang, Jiale Liu, Ahmed Hassan Awadallah, Ryen W White, Doug Burger, Chi Wang
**Year:** 2023
**Venue:** arXiv (Microsoft Research)
**Link:** https://arxiv.org/abs/2308.08155

## Key Contribution

Proposes **AutoGen** — an open-source framework for building LLM applications via multiple agents that converse with each other to accomplish tasks. Agents are customizable, conversable, and can operate in various modes combining LLMs, human inputs, and tools.

## Core Method

Key design principles:
1. **Conversable Agents** — each agent can send/receive messages from other agents
2. **Flexible Interaction Patterns** — developers define conversation patterns (sequential, parallel, group chat)
3. **Human-in-the-Loop** — humans can participate as agents, providing feedback or approval at any point
4. **Tool Integration** — agents can use external tools (code execution, web search, etc.)

The framework is generic infrastructure — not tied to a specific task domain.

## Key Results

- Demonstrates effectiveness across diverse domains: mathematics, coding, Q&A, operations research, decision-making, entertainment
- Shows that flexible conversation patterns enable complex multi-agent workflows
- Open-source framework with active community adoption
- Enables both simple (two-agent) and complex (group chat) configurations

## Limitations

| Limitation | Description |
|-----------|-------------|
| **No context isolation** | Agents in group chat share full conversation history — all tokens participate in attention, increasing hallucination risk for SLMs. |
| **Unstructured communication** | Agents converse freely without enforced structure — can lead to off-topic drift, redundancy, and cascading errors. |
| **No task decomposition** | Framework provides infrastructure but no built-in mechanism for decomposing complex tasks into subtasks. |
| **Large model dependency** | Demonstrated primarily on GPT-4/GPT-3.5. SLM performance unestablished — free-form conversation may overwhelm smaller models. |
| **No verification mechanism** | No built-in reviewer or validator — relies on human-in-the-loop for quality control. |

## Relevance to TINYCUA

AutoGen is the infrastructure layer that TINYCUA builds on conceptually — both enable multi-agent conversation. However, TINYCUA adds structure that AutoGen lacks:

| Aspect | AutoGen | TINYCUA |
|--------|---------|---------|
| Communication | Free-form conversation | Structured agent pipeline (fixed roles) |
| Task decomposition | None (developer manually structures) | Automatic Task Creation loop |
| Context access | Shared conversation history | Isolated context per agent |
| Verification | Human-in-the-loop only | Automated Result Reviewer |
| Orchestration | Developer-defined patterns | Built-in Worker orchestration |

TINYCUA's key innovation over AutoGen: **structured orchestration with context isolation**. AutoGen is a generic framework; TINYCUA is a purpose-built system for decomposing context to reduce hallucination.

## How to Cite

```
@article{wu2023autogen,
  title={AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversation},
  author={Wu, Qingyun and Bansal, Gagan and Zhang, Jieyu and Wu, Yiran and Li, Beibin and Zhu, Erkang and Jiang, Li and Zhang, Xiaoyun and Zhang, Shaokun and Liu, Jiale and Awadallah, Ahmed Hassan and White, Ryen W and Burger, Doug and Wang, Chi},
  journal={arXiv preprint arXiv:2308.08155},
  year={2023}
}
```

## Connection in Lit Review

Position as the generic infrastructure for multi-agent LLM systems. AutoGen shows that conversable agents + flexible interaction patterns enable diverse applications. TINYCUA builds on this by adding: (1) structured orchestration, (2) automatic task decomposition, (3) context isolation, and (4) automated verification. AutoGen is the "plumbing"; TINYCUA is the "architecture."
