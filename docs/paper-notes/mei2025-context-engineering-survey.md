# A Survey of Context Engineering for Large Language Models

**Authors:** Lingrui Mei, Jiayu Yao, Yuyao Ge, Yiwei Wang, Baolong Bi, Yujun Cai, Jiahi Liu, Mingyu Li, Zhong-Zhi Li, Duzhen Zhang, Chenlin Zhou, Jiayi Mao, Tianze Xia, Jiafeng Guo, Shenghua Liu
**Year:** 2025
**Venue:** arXiv (ongoing work, 166 pages, 1411 citations)
**Link:** https://arxiv.org/abs/2507.13334

## Key Contribution

Introduces **Context Engineering** as a formal discipline — transcending simple prompt design to encompass systematic optimization of information payloads for LLMs. Provides a comprehensive taxonomy of 1400+ papers.

## Taxonomy

Context Engineering decomposes into:

**Foundational Components:**
1. **Context retrieval and generation** — what information enters the context
2. **Context processing** — how information is transformed/filtered
3. **Context management** — how context is organized and maintained

**System Implementations:**
1. **RAG** — retrieval-augmented generation
2. **Memory systems** — persistent context across sessions
3. **Tool-integrated reasoning** — context + tool use
4. **Multi-agent systems** — context distributed across agents

## Key Finding

Reveals a **critical asymmetry**: models augmented by context engineering show remarkable proficiency in *understanding* complex contexts, but exhibit pronounced limitations in *generating* equally sophisticated long-form outputs.

## Relevance to TINYCUA

This paper **formalizes what TINYCUA does**:

| Context Engineering Component | TINYCUA Implementation |
|------------------------------|----------------------|
| Context retrieval & generation | Information Digester with Enhanced Context Retrieval |
| Context processing | Task decomposition into focused sub-tasks |
| Context management | Sub-sessions with isolated chat_history and context |
| Multi-agent systems | 9 specialized agents in hierarchical session tree |

TINYCUA's core thesis — "decomposing context exposure reduces hallucination" — is a specific instantiation of Context Engineering's principles applied to small language models.

## How to Cite

```
@article{mei2025survey,
  title={A Survey of Context Engineering for Large Language Models},
  author={Mei, Lingrui and Yao, Jiayu and Ge, Yuyao and Wang, Yiwei and Bi, Baolong and Cai, Yujun and Liu, Jiazhi and Li, Mingyu and Li, Zhong-Zhi and Zhang, Duzhen and Zhou, Chenlin and Mao, Jiayi and Xia, Tianze and Guo, Jiafeng and Liu, Shenghua},
  journal={arXiv preprint arXiv:2507.13334},
  year={2025}
}
```

## Connection in Lit Review

Use to **ground TINYCUA in established terminology**. Instead of saying "we decompose context," say "TINYCUA implements context engineering through sub-agent isolation." This positions the work within a recognized field rather than as an ad-hoc solution.
