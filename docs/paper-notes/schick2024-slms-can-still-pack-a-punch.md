# Small Language Models (SLMs) Can Still Pack a Punch: A Survey

**Authors:** Timo Schick, Hinrich Schütze
**Year:** 2024
**Venue:** arXiv
**Link:** https://arxiv.org/abs/2501.05465

## Key Contribution

Comprehensive survey of 1B–8B parameter SLMs. Shows that SLMs are **competitive with larger models when tasks are well-structured** and context is clean. Key argument: SLMs are not universally weaker — their weakness is context-dependent.

## Key Findings

- SLMs (1B–8B) can match or exceed LLM performance on focused tasks
- Performance gap widens as task complexity and context size increase
- SLMs benefit disproportionately from:
  - Well-structured inputs
  - Clean, focused context
  - Explicit task decomposition
- Quality of training data matters more than raw parameter count

## Relevance to TINYCUA

This paper supports TINYCUA's core hypothesis from the **solution side**:

1. SLMs ARE capable — they just need the right context structure
2. Task decomposition + clean context → SLMs can match LLM performance
3. The "clean context" requirement is exactly what TINYCUA's sub-agent isolation provides

If SLMs perform well with clean context, then investing in context engineering (TINYCUA's approach) is worthwhile.

## Contrast with Arora et al. (2024)

Where Arora is comprehensive on SLM *techniques*, Schick & Schütze focuses more on SLM *capability boundaries* — specifically when they succeed and when they fail.

## How to Cite

```
@article{schick2025slms,
  title={Small Language Models (SLMs) Can Still Pack a Punch: A Survey},
  author={Schick, Timo and Sch{\"u}tze, Hinrich},
  journal={arXiv preprint arXiv:2501.05465},
  year={2025}
}
```
