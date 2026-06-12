# Chain-of-Thought Prompting Elicits Reasoning in Large Language Models

**Authors:** Jason Wei, Xuezhi Wang, Dale Schuurmans, Maarten Bosma, Brian Ichter, Fei Xia, Ed Chi, Quoc Le, Denny Zhou
**Year:** 2022
**Venue:** NeurIPS 2022
**Link:** https://arxiv.org/abs/2201.11903

## Key Contribution

Shows that generating a **chain of thought** — a series of intermediate reasoning steps — significantly improves the ability of large language models to perform complex reasoning. With just 8 CoT exemplars, a 540B model achieves state-of-the-art on GSM8K, surpassing even fine-tuned GPT-3 with a verifier.

## Core Method

Augment each few-shot prompt exemplar with step-by-step reasoning before the final answer:

```
Q: Roger has 5 tennis balls. He buys 2 more cans...
A: Roger started with 5 balls. 2 cans of 3 = 6. 5 + 6 = 11. The answer is 11.
```

## Key Results

- CoT improves performance across arithmetic, commonsense, and symbolic reasoning tasks
- Gains are **emergent** — negligible for models under ~100B parameters
- 540B PaLM + 8-shot CoT achieves 58.1% on GSM8K (previous SOTA was 55% with fine-tuned GPT-3 + verifier)

## Limitations (as stated by the authors)

The paper explicitly acknowledges four limitations:

1. **Whether the model is actually "reasoning"** — although CoT emulates human thought processes, "this does not answer whether the neural network is actually 'reasoning,' which we leave as an open question."

2. **Fine-tuning annotation cost** — while manual annotation for few-shot exemplars is minimal, "such annotation costs could be prohibitive for finetuning."

3. **No guarantee of correct reasoning paths** — the generated chain "can lead to both correct and incorrect answers." The model can produce plausible-sounding but wrong reasoning.

4. **Emergence only at large scale** — CoT reasoning emerges only at large model scales, which "makes it costly to serve in real-world applications." The authors suggest further research on "how to induce reasoning in smaller models."

## Relevance to TINYCUA

CoT establishes that step-by-step reasoning improves LLM accuracy. TINYCUA's argument is that **clean context upfront** may be even more effective than reasoning through noisy context step-by-step, especially for SLMs where CoT does not emerge reliably.

TINYCUA addresses CoT's key limitations:
- **Scale requirement** → SLMs with context isolation instead of relying on emergent reasoning
- **Error propagation** → Reviewer validates each sub-task result before proceeding
- **Context noise** → Each sub-agent receives only task-relevant context

## How to Cite

```
@inproceedings{wei2022chain,
  title={Chain-of-Thought Prompting Elicits Reasoning in Large Language Models},
  author={Wei, Jason and Wang, Xuezhi and Schuurmans, Dale and Bosma, Maarten and Ichter, Brian and Xia, Fei and Chi, Ed and Le, Quoc and Zhou, Denny},
  booktitle={Advances in Neural Information Processing Systems (NeurIPS)},
  year={2022}
}
```

## Connection in Lit Review

Position as the baseline reasoning method. CoT shows models *can* reason step-by-step, but this is:
- Only reliable at large scale (≥100B)
- Vulnerable to error propagation and context noise

TINYCUA's hypothesis: structured sub-agent decomposition with context isolation provides more reliable reasoning for SLMs than monolithic CoT.
