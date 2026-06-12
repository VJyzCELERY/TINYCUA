# CAMEL: Communicative Agents for "Mind" Exploration of Large Language Model Society

**Authors:** Guohao Li, Hasan Abed Al Kader Hammoud, Hani Itani, Dmitrii Khizbullin, Bernard Ghanem
**Year:** 2023
**Venue:** NeurIPS 2023
**Link:** https://arxiv.org/abs/2303.17760

## Key Contribution

Proposes **CAMEL** — a role-playing framework for autonomous cooperation among communicative agents. Uses **inception prompting** to guide agents toward task completion while maintaining consistency with human intentions. First multi-agent LLM system after ReAct (Oct 2022 → Mar 2023).

## Core Method

Two key mechanisms:
1. **Role-Playing** — agents are assigned complementary roles (e.g., AI Prompter + AI Assistant) and collaborate through multi-turn dialogue
2. **Inception Prompting** — carefully crafted prompts that maintain role consistency and task alignment across agent conversations

Agents communicate via natural language, with each agent contributing its role-specific expertise to solve tasks collaboratively.

## Key Results

- First to demonstrate autonomous cooperation among LLM agents without human intervention
- Shows that role-playing enables agents to stay on-task and produce coherent outputs
- Open-sourced library for multi-agent research
- Accepted at NeurIPS 2023 (high-venue validation)

## Limitations

| Limitation | Description |
|-----------|-------------|
| **No task decomposition** | Agents collaborate on the whole task — no mechanism to break complex tasks into subtasks with isolated context. |
| **No context isolation** | Full conversation history is shared between agents — all tokens participate in attention, increasing hallucination risk for SLMs. |
| **Role inconsistency** | Despite inception prompting, agents can drift from their assigned roles over long conversations. |
| **Two-agent limitation** | Primarily demonstrated with two agents (AI Prompter + AI Assistant) — scaling to more agents is not well-explored. |
| **Large model dependency** | Tested on ChatGPT/GPT-4. SLM performance unestablished — role-playing and inception prompting may require high-capacity models. |
| **No verification mechanism** | No external reviewer — relies on agents self-correcting via conversation. |

## Relevance to TINYCUA

CAMEL is the historical starting point for multi-agent LLM systems — it proved that autonomous cooperation is possible. However, TINYCUA addresses all of CAMEL's limitations:

| Aspect | CAMEL | TINYCUA |
|--------|-------|---------|
| Task decomposition | None (whole-task collaboration) | Explicit Task Creation loop |
| Context access | Full conversation history | Isolated context per agent |
| Agent roles | Two roles (Prompter + Assistant) | Fixed specialized agents (6+ roles) |
| Verification | None (self-correction) | Automated Result Reviewer |
| Model size | GPT-4 | SLMs (1B-8B) |

TINYCUA's key innovation over CAMEL: **context decomposition**. CAMEL agents share everything; TINYCUA agents get only what they need. This is the fundamental difference that enables SLM viability.

## How to Cite

```
@inproceedings{li2023camel,
  title={CAMEL: Communicative Agents for "Mind" Exploration of Large Language Model Society},
  author={Li, Guohao and Hammoud, Hasan Abed Al Kader and Itani, Hani and Khizbullin, Dmitrii and Ghanem, Bernard},
  booktitle={Advances in Neural Information Processing Systems (NeurIPS)},
  year={2023}
}
```

## Connection in Lit Review

Position as the historical starting point — CAMEL proved multi-agent cooperation works. But it lacks task decomposition, context isolation, and verification. TINYCUA builds on CAMEL's insight (agents can cooperate) by adding all three: structured decomposition, isolated context, and automated review. Use CAMEL → MetaGPT → AutoGen → TDAG → TINYCUA as the chronological arc in the literature review.
