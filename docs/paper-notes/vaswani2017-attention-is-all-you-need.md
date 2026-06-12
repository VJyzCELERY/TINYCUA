# Attention Is All You Need

**Authors:** Vaswani et al.
**Year:** 2017
**Venue:** NeurIPS
**Link:** https://arxiv.org/abs/1706.03762

## Key Contribution

Introduced the Transformer architecture, which replaced recurrent (RNN) and convolutional (CNN) layers with a pure attention mechanism. Core innovation is **Scaled Dot-Product Attention** (Section 3.2.1):

$$Attention(Q, K, V) = softmax(QK^T / \sqrt{d_k}) V$$

## Relevance to TINYCUA

- The **softmax** over all tokens is the root mechanism behind TINYCUA's core problem: every token (relevant or not) receives some attention weight. As context grows, irrelevant tokens consume attention probability mass.
- The Transformer is the foundation model architecture that all modern LLMs (and SLMs) are built on. Understanding this is prerequisite to understanding why context compaction matters.

## Key Concepts for TINYCUA

1. **Self-attention** — each token attends to every other token in the sequence. Cost is $O(n^2)$.
2. **Softmax normalization** — forces a probability distribution over all tokens. Even "noise" tokens get non-zero weight.
3. **Multi-head attention** — multiple attention heads can specialize; but each head still operates over the full context.
4. **Positional encoding** — transformers are permutation-invariant; position is injected via added embeddings. This becomes relevant for the "lost in the middle" phenomenon.

## How to Cite

```
@inproceedings{vaswani2017attention,
  title={Attention is all you need},
  author={Vaswani, Ashish and Shazeer, Noam and Parmar, Niki and Uszkoreit, Jakob and Jones, Llion and Gomez, Aidan N and Kaiser, {\L}ukasz and Polosukhin, Illia},
  booktitle={Advances in Neural Information Processing Systems},
  year={2017}
}
```

## Connection to Next Paper

Miller (2023) and Liu et al. (2023) build on this: they show that the softmax mechanism causes performance degradation when relevant information sits in the middle of long contexts.
