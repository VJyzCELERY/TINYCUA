# ReAct: Synergizing Reasoning and Acting in Language Models

**Authors:** Shunyu Yao, Jeffrey Zhao, Dian Yu, Nan Du, Izhak Shafran, Karthik Narasimhan, Yuan Cao
**Year:** 2022 (published 2023)
**Venue:** ICLR 2023
**Link:** https://arxiv.org/abs/2210.03629

## Key Contribution

Proposes **ReAct** — a paradigm that interleaves reasoning traces (verbalized thinking) with task-specific actions (tool calls, environment interactions). Instead of treating reasoning and acting as separate phases, ReAct alternates them: **Thought → Action → Observation → Thought → ...**

## Core Pattern

```
Thought: I need to find X...
Action: search("X")
Observation: X is located at Y
Thought: Now that I know Y, I can...
Action: finish("answer")
```

Each cycle:
- **Thought** (reasoning): what to do next, what was learned
- **Action** (acting): a tool call or environment step
- **Observation** (feedback): the result of the action
- **Repeat** until task is complete

## Key Results

- Outperforms both CoT-only (reasoning without tools) and Act-only (acting without reasoning) on:
  - Multi-hop QA (HotpotQA)
  - Fact verification (FEVER)
  - Interactive decision making (ALFWorld, WebShop)
- Reasoning traces make action choices interpretable
- Acting provides grounding to correct reasoning errors

## Limitations

| Limitation | Description |
|-----------|-------------|
| **External tool dependency** | ReAct's accuracy is bounded by the quality and coverage of external tools/APIs. When tools return incomplete or noisy results, the model compensates with hallucination rather than abstaining. |
| **No structured context isolation** | Reasoning traces, action outputs, and observations are interleaved in a single session — all tokens participate in every attention computation (Vaswani 2017). Irrelevant observations pollute subsequent reasoning. |
| **Verbose reasoning traces** | Interleaved Thought → Action → Observation cycles produce long trajectories. For SLMs, longer context increases the lost-in-the-middle effect (Liu 2024) and hallucination risk. |
| **Latency overhead** | Each action requires an external round trip. Serial tool calls per reasoning step add significant latency, especially for multi-step tasks. |
| **SLM performance unestablished** | ReAct was tested on PaLM-540B and GPT-3. Effectiveness on 1B-8B SLMs is not demonstrated — smaller models may struggle with the combined load of reasoning + tool use + context tracking. |
| **No external verification** | ReAct corrects errors via tool observations, but has no reviewer mechanism to validate final outputs. The model decides when to stop, which can lead to premature or over-confident termination. |

## Relevance to TINYCUA

ReAct is **the operational pattern for TINYCUA's Task Execution agent**. The Thought → Action → Observation loop is the standard agent loop that TINYCUA's sub-agents run internally.

However, TINYCUA extends ReAct in two critical ways:

| Aspect | ReAct | TINYCUA |
|--------|-------|---------|
| Context | Full context available to one agent | Each sub-agent gets only its task's context |
| Scope | One agent handles everything | Multiple agents, each with isolated context |
| Loop control | Agent decides when to stop | External Reviewer validates before proceeding |

ReAct is the "inside" of TINYCUA's execution agent; TINYCUA adds the "outside" orchestration that limits context exposure.

## How to Cite

```
@inproceedings{yao2023react,
  title={ReAct: Synergizing Reasoning and Acting in Language Models},
  author={Yao, Shunyu and Zhao, Jeffrey and Yu, Dian and Du, Nan and Shafran, Izhak and Narasimhan, Karthik and Cao, Yuan},
  booktitle={International Conference on Learning Representations (ICLR)},
  year={2023}
}
```

## Connection in Lit Review

Use after CoT (Wei 2022) — CoT shows models can reason step-by-step; ReAct shows they can interleave reasoning with tool use. Together they form the foundation for agentic systems. TINYCUA builds on both by adding context isolation.
