# Contextual Compression in Retrieval-Augmented Generation for Large Language Models: A Survey

**Author:** Sourav Verma
**Year:** 2024
**Venue:** arXiv (ongoing work)
**Link:** https://arxiv.org/abs/2409.13385

## Key Contribution

Comprehensive survey of **contextual compression paradigms** in RAG systems. Maps the evolution of techniques for reducing context size while preserving relevant information for LLM generation.

## Core Problem Statement

RAG systems face three context-related limitations:
1. **Limited context window** — retrieved documents may exceed model capacity
2. **Irrelevant information** — retrieved content includes noise that degrades generation
3. **High processing overhead** — extensive contextual data increases compute cost

## Compression Taxonomy

The survey categorizes compression approaches into:

| Category | Method | Description |
|----------|--------|-------------|
| **Extractive** | Select relevant sentences/paragraphs | Keep subset of original text |
| **Abstractive** | Generate compressed summary | Rewrite content more concisely |
| **Embedding-based** | Replace text with dense representations | Like xRAG — extreme compression |
| **Hybrid** | Combine approaches | Multi-stage compression pipelines |

## Key Insight

Compression is not just about reducing tokens — it's about **preserving signal while removing noise**. The best compression methods maintain semantic fidelity while eliminating irrelevant content.

## Relevance to TINYCUA

TINYCUA's context isolation is a form of **structural compression** — not compressing text within a document, but compressing the *set of documents* each agent sees:

| Compression Type | What It Reduces | TINYCUA Equivalent |
|-----------------|----------------|-------------------|
| Extractive | Sentences within a document | Information Digester (extracts relevant info) |
| Abstractive | Document length via summarization | Task decomposition (each task gets focused context) |
| **Structural** | **Number of documents per agent** | **Sub-agent isolation (each agent sees only its docs)** |

TINYCUA combines all three: Information Digester extracts, Task Creator decomposes, and sub-agent isolation ensures structural compression.

## How to Cite

```
@article{verma2024contextual,
  title={Contextual Compression in Retrieval-Augmented Generation for Large Language Models: A Survey},
  author={Verma, Sourav},
  journal={arXiv preprint arXiv:2409.13385},
  year={2024}
}
```

## Connection in Lit Review

Use to position TINYCUA within the compression literature. The survey establishes that compression improves RAG quality; TINYCUA extends this principle from retrieval-time compression to **architecture-time compression** — building isolation into the agent structure rather than applying it as a post-processing step.
