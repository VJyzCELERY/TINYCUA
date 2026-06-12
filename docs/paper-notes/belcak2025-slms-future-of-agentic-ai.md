# Small Language Models are the Future of Agentic AI

**Authors:** Peter Belcak, Greg Heinrich, Shizhe Diao, Yonggan Fu, Xin Dong, Saurav Muralidharan, Yingyan Celine Lin, Pavlo Molchanov (NVIDIA Research & Georgia Tech)
**Year:** 2025
**Venue:** arXiv
**Link:** https://arxiv.org/abs/2506.02153

## Key Contribution

Position paper arguing that SLMs are **sufficiently powerful, inherently more suitable, and economically necessary** for agentic AI systems. Proposes an LLM-to-SLM agent conversion algorithm.

## Key Arguments

1. **Sufficiently powerful:** Current SLMs can handle most agentic tasks (tool calling, planning, code generation)
2. **Inherently more suitable:** Agentic tasks are narrow and repetitive — LLM generality is wasted
3. **Necessarily more economical:** SLMs reduce inference cost by orders of magnitude

## Supporting Claims

- Most agent calls are simple (tool selection, parameter filling, output parsing)
- SLMs match LLMs on these narrow tasks when properly fine-tuned
- **Heterogeneous systems** (multiple SLMs per agent) are the natural evolution
- Proposes a conversion algorithm: analyze agent task patterns → fine-tune SLM on those patterns → replace LLM with SLM

## Relevance to TINYCUA

This paper directly supports TINYCUA's architectural philosophy:

1. **SLMs + clean context > LLMs + noisy context** — Aligns with TINYCUA's core bet
2. **Heterogeneous SLM sub-agents** — This is exactly TINYCUA's sub-agent architecture
3. **Task-specific specialization** — TINYCUA's per-task context packaging creates the narrow, clean inputs that SLMs need
4. **Economic argument** — TINYCUA makes SLM-based agents practical by compensating for their weaknesses via context engineering

## Key Quote

> "Small language models (SLMs) are sufficiently powerful, inherently more suitable, and necessarily more economical for many invocations in agentic systems, and are therefore the future of agentic AI."

## How to Cite

```
@article{belcak2025slm,
  title={Small Language Models are the Future of Agentic AI},
  author={Belcak, Peter and Heinrich, Greg and Diao, Shizhe and Fu, Yonggan and Dong, Xin and Muralidharan, Saurav and Lin, Yingyan Celine and Molchanov, Pavlo},
  journal={arXiv preprint arXiv:2506.02153},
  year={2025}
}
```
