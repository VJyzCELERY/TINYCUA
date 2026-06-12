# Large Language Models are Zero-Shot Reasoners

**Authors:** Takeshi Kojima, Shixiang Shane Gu, Machel Reid, Yutaka Matsuo, Yusuke Iwasawa
**Year:** 2022
**Venue:** NeurIPS 2022
**Link:** https://arxiv.org/abs/2205.11916

## Key Contribution

Shows that LLMs are **zero-shot reasoners** — simply adding `"Let's think step by step"` before each answer elicits multi-step reasoning without any few-shot examples. This is the minimal prompt that activates chain-of-thought behavior.

## Core Method

Two-stage prompt:

1. **Reasoning extraction:** Append `"Let's think step by step."` to the query → model generates a reasoning trace
2. **Answer extraction:** Append `"Therefore, the answer is"` → model extracts the final answer

No task-specific examples needed. One prompt template works across arithmetic, symbolic, commonsense, and logical reasoning tasks.

## Key Results

| Task | Zero-shot | Zero-shot-CoT | Improvement |
|------|-----------|---------------|-------------|
| MultiArith | 17.7% | 78.7% | +61pp |
| GSM8K | 10.4% | 40.7% | +30.3pp |
| SVAMP | 33.5% | 58.4% | +24.9pp |

Works reliably on models ≥100B parameters. Smaller models show less consistent gains.

## Limitations

| Limitation | Description |
|-----------|-------------|
| **Emergent at scale only** | Gains are consistent only for models ≥100B parameters. The paper explicitly notes "smaller models show less consistent gains" — making this approach unreliable for SLMs. |
| **Shallow reasoning** | The single prompt "Let's think step by step" produces reasoning traces that can be superficial or repetitive. The model may generate plausible-sounding chains that are factually wrong — fluency masks errors. |
| **No error detection or correction** | Like CoT, once the reasoning trace is generated, there is no mechanism to verify correctness. Errors in early steps propagate to the final answer. |
| **Context noise sensitivity** | The prompt operates over the full input context. If irrelevant or misleading information is present, the "think step by step" instruction does not help the model filter it out — attention still computes over all tokens. |
| **Lower accuracy than few-shot CoT** | Zero-shot-CoT is consistently less accurate than few-shot CoT across benchmarks. The gap is substantial on harder tasks like GSM8K (40.7% vs 58.1% for few-shot 540B PaLM). |
| **Single generic prompt** | "Let's think step by step" is task-agnostic and cannot encode domain-specific reasoning strategies. Different tasks benefit from different reasoning structures (e.g., temporal reasoning vs. arithmetic). |

## Relevance to TINYCUA

This paper is important for the **reasoning vs. clean context** trade-off (Section 6 of the architecture discussion):

- Zero-shot-CoT shows that models **can** reason internally when prompted
- TINYCUA's hypothesis: providing **clean context externally** is more reliable than relying on the model to self-filter irrelevant context while reasoning
- If model capacity is limited (SLMs), reasoning alone may not compensate for noisy context
- Zero-shot-CoT works best for large models (≥100B); TINYCUA targets smaller models where this approach is less effective

## How to Cite

```
@inproceedings{kojima2022large,
  title={Large Language Models are Zero-Shot Reasoners},
  author={Kojima, Takeshi and Gu, Shixiang Shane and Reid, Machel and Matsuo, Yutaka and Iwasawa, Yusuke},
  booktitle={Advances in Neural Information Processing Systems (NeurIPS)},
  year={2022}
}
```

## Connection in Lit Review

This paper represents the "reasoning in one session" extreme — the model does everything in a single context window. TINYCUA challenges this for SLMs: rather than asking a small model to reason through noisy context, give it clean context and let it execute.
