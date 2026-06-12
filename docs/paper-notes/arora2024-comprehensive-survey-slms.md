# A Comprehensive Survey of Small Language Models in the Era of Large Language Models: Techniques, Enhancements, Applications, Collaboration with LLMs, and Trustworthiness

**Authors:** Arora et al.
**Year:** 2024
**Venue:** ACM Computing Surveys
**Link:** https://dl.acm.org/doi/10.1145/3768165

## Key Contribution

Comprehensive survey covering the full SLM landscape: architectures, training techniques, compression methods, applications, and trustworthiness. Covers models up to ~2024.

## Key Findings

- **Fewer parameters → lower capacity → higher hallucination rates** in complex/long-context tasks
- SLMs excel in:
  - Resource-constrained environments (edge, mobile)
  - Domain-specific tasks (fine-tuned on narrow data)
  - Low-latency applications
- Key techniques to boost SLM performance:
  - Knowledge distillation from LLMs
  - Pruning and quantization
  - Parameter-efficient fine-tuning (LoRA, etc.)
  - Retrieval-augmented generation (RAG)
- Trustworthiness concerns are different for SLMs: they hallucinate differently (less fluent, more factual errors in long context)

## Relevance to TINYCUA

This paper provides the **foundational evidence** for TINYCUA's premise:

1. Confirms that SLMs have higher hallucination rates with complex/long contexts (Section 3's problem statement)
2. Lists RAG and context optimization as key SLM enhancement techniques (supports Section 5's context retrieval approach)
3. Establishes that task-specific SLMs can outperform generalist LLMs on narrow tasks (supports the sub-agent specialization argument)

## How to Cite

```
@article{arora2024comprehensive,
  title={A Comprehensive Survey of Small Language Models in the Era of Large Language Models: Techniques, Enhancements, Applications, Collaboration with LLMs, and Trustworthiness},
  author={Arora, Anushka and others},
  journal={ACM Computing Surveys},
  year={2024},
  doi={10.1145/3768165}
}
```
