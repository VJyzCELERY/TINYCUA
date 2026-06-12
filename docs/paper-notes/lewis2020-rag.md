# Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks

**Authors:** Patrick Lewis, Ethan Perez, Aleksandra Piktus, Fabio Petroni, Vladimir Karpukhin, Naman Goyal, Heinrich Küttler, Mike Lewis, Wen-tau Yih, Tim Rocktäschel, Sebastian Riedel, Douwe Kiela
**Year:** 2020
**Venue:** NeurIPS 2020
**Link:** https://arxiv.org/abs/2005.11401

## Key Contribution

Introduces **RAG (Retrieval-Augmented Generation)** — combines pre-trained parametric memory (seq2seq model) with non-parametric memory (dense vector index of Wikipedia) for language generation. The foundational paper that established the retrieve-then-generate paradigm.

## How It Works

1. **Retriever:** Pre-trained neural retriever fetches relevant documents from Wikipedia index
2. **Generator:** Pre-trained seq2seq model (BART) generates output conditioned on retrieved documents
3. Two formulations:
   - **RAG-Sequence:** Same retrieved passages for entire generated sequence
   - **RAG-Token:** Different passages per output token (more flexible)

## Key Results

- State-of-the-art on 3 open-domain QA tasks
- Outperforms parametric seq2seq models and task-specific retrieve-and-extract architectures
- Generates more specific, diverse, and factual language than parametric-only baselines

## Limitations (Relevant to TINYCUA)

| Limitation | Description |
|-----------|-------------|
| Single model | All retrieved context goes to one generator |
| Context bloat | Retrieved documents may include irrelevant content |
| No decomposition | Model must filter noise internally |
| Fixed retrieval | Retrieval happens once, not iteratively |

## Relevance to TINYCUA

RAG solved the "knowledge access" problem but not the "context management" problem:

| RAG Approach | TINYCUA Extension |
|-------------|-------------------|
| Retrieve relevant docs | Information Digester retrieves + filters |
| Feed all docs to one model | Distribute docs across specialized agents |
| Model filters noise internally | Context isolation removes noise by construction |
| Single generation pass | Task decomposition with iterative review |

TINYCUA inherits RAG's retrieval principle but adds **architectural context isolation** — each agent gets only the context it needs, rather than one model processing everything.

## How to Cite

```
@inproceedings{lewis2020retrieval,
  title={Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks},
  author={Lewis, Patrick and Perez, Ethan and Piktus, Aleksandra and Petroni, Fabio and Karpukhin, Vladimir and Goyal, Naman and K{\"u}ttler, Heinrich and Lewis, Mike and Yih, Wen-tau and Rockt{\"a}schel, Tim and Riedel, Sebastian and Kiela, Douwe},
  booktitle={Advances in Neural Information Processing Systems (NeurIPS)},
  year={2020}
}
```

## Connection in Lit Review

Use as the **starting point for the RAG section**. Establish that RAG solved knowledge access, then show how Gao et al. (2024) maps its evolution, then argue that TINYCUA extends RAG from single-model retrieval to multi-agent context orchestration.
