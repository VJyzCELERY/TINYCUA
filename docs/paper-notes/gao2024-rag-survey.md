# Retrieval-Augmented Generation for Large Language Models: A Survey

**Authors:** Yunfan Gao, Yun Xiong, Xinyu Gao, Kangxiang Jia, Jinliu Pan, Yuxi Bi, Yi Dai, Jiawei Sun, Meng Wang, Haofen Wang
**Year:** 2024
**Venue:** arXiv (ongoing work)
**Link:** https://arxiv.org/abs/2312.10997

## Key Contribution

Comprehensive survey mapping the evolution of RAG paradigms and identifying their limitations. Establishes a taxonomy of RAG frameworks and evaluation methods.

## RAG Evolution

| Paradigm | Description | Limitation |
|----------|-------------|------------|
| **Naive RAG** | Simple retrieve-then-generate | Noisy retrieval, context bloat |
| **Advanced RAG** | Pre/post-retrieval optimization | Still single-model processing |
| **Modular RAG** | Composable retrieval + generation components | Needs orchestration framework |

## Three-Part Framework

1. **Retrieval** — fetch relevant documents from external knowledge
2. **Generation** — produce output conditioned on retrieved context
3. **Augmentation** — enhance retrieval or generation with additional techniques

## Key Challenges Identified

| Challenge | Description | TINYCUA Response |
|-----------|-------------|------------------|
| Hallucination | Model generates plausible but incorrect content | Context isolation reduces noise |
| Outdated knowledge | Static training data | RAG retrieval provides fresh info |
| Untraceable reasoning | Model doesn't show how it used context | Task decomposition makes reasoning explicit |
| Context bloat | Retrieved docs include irrelevant content | Sub-agents see only relevant context |
| Limited context window | Retrieved docs may exceed model capacity | Compression + isolation |

## Relevance to TINYCUA

The survey's **Modular RAG** concept directly parallels TINYCUA's architecture:

| Modular RAG Component | TINYCUA Agent |
|----------------------|---------------|
| Retrieval module | Information Digester |
| Processing module | Task Creator + Task Analyzer |
| Generation module | Task Executor + Primary Agent |
| Quality module | Result Reviewer |

TINYCUA is a **Modular RAG system implemented as a multi-agent hierarchy** — each agent is a specialized RAG module with its own context scope.

## How to Cite

```
@article{gao2024retrieval,
  title={Retrieval-Augmented Generation for Large Language Models: A Survey},
  author={Gao, Yunfan and Xiong, Yun and Gao, Xinyu and Jia, Kangxiang and Pan, Jinliu and Bi, Yuxi and Dai, Yi and Sun, Jiawei and Wang, Meng and Wang, Haofen},
  journal={arXiv preprint arXiv:2312.10997},
  year={2024}
}
```

## Connection in Lit Review

Use after Lewis et al. (2020) to show RAG's evolution and limitations. The survey's identification of "context bloat" and "untraceable reasoning" as key challenges directly motivates TINYCUA's approach: decompose context across agents to solve bloat, and decompose tasks to make reasoning explicit.
