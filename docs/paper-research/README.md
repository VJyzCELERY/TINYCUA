# Literature Review — Related Work Sections

This directory contains draft literature review sections for the TinyCUA thesis.

## Sections

| File | Topic | Status |
|------|-------|--------|
| [rag.md](rag.md) | RAG (Naive → Advanced → Modular) | Draft |
| [react.md](react.md) | ReAct (Reasoning + Acting) | Draft |
| [mas-tdag.md](mas-tdag.md) | Multi-Agent Systems + TDAG | Draft |

## Flow

```
RAG (knowledge access, context bloat)
  → ReAct (reasoning + tools, but single-session context growth)
    → MAS/TDAG (multi-agent decomposition, but shared context / dynamic generation overhead)
      → TinyCUA (fixed staged nodes, context isolation, SLM-compatible)
```

## Key Citations

| Paper | Reference |
|-------|-----------|
| Lewis et al. (2020) | Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks |
| Gao et al. (2024) | Retrieval-Augmented Generation for Large Language Models: A Survey |
| Yao et al. (2023) | ReAct: Synergizing Reasoning and Acting in Language Models |
| Liu et al. (2023) | Lost in the Middle: How Language Models Use Long Contexts |
| Li et al. (2023) | CAMEL: Communicative Agents for "Mind" Exploration |
| Hong et al. (2023) | MetaGPT: Meta Programming for A Multi-Agent Collaborative Framework |
| Wu et al. (2023) | AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversation |
| Wang et al. (2024) | TDAG: A Multi-Agent Framework based on Dynamic Task Decomposition |
