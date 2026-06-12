# Plan-and-Solve Prompting: Improving Zero-Shot Chain-of-Thought Reasoning

**Authors:** Lei Wang, Wanyu Xu, Yihuai Lan, Zhiqiang Hu, Yunshi Lan, Roy Ka-Wei Lee, Ee-Peng Lim
**Year:** 2023
**Venue:** ACL 2023
**Link:** https://arxiv.org/abs/2305.04091

## Key Contribution

Proposes **Plan-and-Solve (PS) Prompting** that addresses missing-step errors in Zero-shot-CoT. Two-stage process: first devise a plan dividing the task into smaller subtasks, then execute subtasks according to the plan. Extends to **PS+** with more detailed instructions to reduce calculation errors.

## Core Method

Two components:
1. **Plan** — divide the entire task into smaller subtasks
2. **Solve** — carry out the subtasks according to the plan

PS+ adds more detailed instructions to improve reasoning step quality.

## Key Results

- Consistently outperforms Zero-shot-CoT across all 10 datasets by a large margin
- Comparable to or exceeds Zero-shot-Program-of-Thought
- Comparable to 8-shot CoT on math reasoning problems
- Tested on GPT-3 only

## Limitations

| Limitation | Description |
|-----------|-------------|
| **Plan quality dependence** | If the initial plan is flawed, each sub-task inherits the error. There is no mechanism to validate the plan before execution or to detect structural problems mid-execution. |
| **No execution verification** | The plan is generated upfront; errors in sub-task execution (calculation, reasoning) are not caught. PS+ adds more detailed instructions but still no review loop. |
| **Rigid sequential structure** | The plan is fixed at generation time. Adapting to new information or correcting course mid-execution requires replanning from scratch — no dynamic adjustment. |
| **No context isolation** | Each sub-task still operates over the **full problem context**. All tokens participate in attention (Vaswani 2017), including irrelevant information from other sub-tasks. The decomposition is at the plan level, not the context level. |
| **Tested only on GPT-3** | Results do not generalize to smaller models. Effectiveness on SLMs (1B-8B) is unestablished — the planning step itself may fail in lower-capacity models. |
| **Three error types persist** | PS addresses missing-step errors but calculation errors and semantic misunderstanding errors are only partially reduced by PS+, not eliminated. |

## Relevance to TINYCUA

Plan-and-Solve is the closest architectural predecessor to TINYCUA's Worker mode. Both decompose tasks into sub-tasks. However, TINYCUA's critical extension is **context decomposition**:

| Aspect | Plan-and-Solve | TINYCUA |
|--------|---------------|---------|
| Decomposition | Plan-level only | Plan-level + context-level |
| Context exposure | Full context per sub-task | Task-specific context only |
| Execution validation | None | Task Reviewer validates each result |
| Plan adjustment | Requires full replan | Reviewer can trigger targeted replanning |
| Agent model | GPT-3 (large) | SLMs (1B-8B) |

TINYCUA addresses Plan-and-Solve's core weakness: decomposing work without decomposing context still exposes SLMs to irrelevant information that triggers hallucination.

## How to Cite

```
@inproceedings{wang2023plan,
  title={Plan-and-Solve Prompting: Improving Zero-Shot Chain-of-Thought Reasoning by Large Language Models},
  author={Wang, Lei and Xu, Wanyu and Lan, Yihuai and Hu, Zhiqiang and Lan, Yunshi and Lee, Roy Ka-Wei and Lim, Ee-Peng},
  booktitle={Proceedings of the 61st Annual Meeting of the Association for Computational Linguistics (ACL)},
  year={2023}
}
```

## Connection in Lit Review

Position as the direct precursor to TINYCUA's Worker mode. Plan-and-Solve shows that plan-then-execute decomposition improves accuracy, but it misses a crucial dimension: **context isolation**. TINYCUA extends the decomposition principle from the plan layer to the context layer, which is necessary for SLM viability.
