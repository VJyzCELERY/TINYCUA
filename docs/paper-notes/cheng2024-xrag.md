# xRAG: Extreme Context Compression for Retrieval-Augmented Generation with One Token

**Authors:** Xin Cheng, Xun Wang, Xingxing Zhang, Tao Ge, Si-Qing Chen, Furu Wei, Huishuai Zhang, Dongyan Zhao
**Year:** 2024
**Venue:** NeurIPS 2024
**Link:** https://openreview.net/forum?id=6pTlXqrO0p

## Key Contribution

Proposes **xRAG** — a context compression method that reinterprets document embeddings (from dense retrieval) as features from a retrieval modality, then fuses them into the LM representation space. Replaces entire documents with their embeddings — achieving **extreme compression** (one token per document).

## How It Works

1. Dense retriever produces document embeddings (typically used only for retrieval)
2. xRAG treats these embeddings as **retrieval modality features**
3. Modality bridge (only trainable component) fuses embeddings into LM space
4. Textual content is eliminated — only the embedding remains
5. Retriever and LM stay frozen; only the bridge is trained

## Key Results

- **+10% average improvement** across 6 knowledge-intensive tasks
- Works across LM backbones: dense 7B to 8x7B MoE
- **3.53x reduction in FLOPs** while matching uncompressed performance
- Outperforms previous context compression methods

## Relevance to TINYCUA

xRAG and TINYCUA address the same problem (context bloat) from different angles:

| Approach | Method | Compression | Trade-off |
|----------|--------|-------------|-----------|
| xRAG | Replace documents with embeddings | Extreme (1 token/doc) | Loses explicit text; relies on embedding quality |
| TINYCUA | Decompose context across sub-agents | Structural (per-agent isolation) | Preserves text; relies on decomposition quality |

**Complementary:** xRAG compresses *what* goes into context; TINYCUA controls *who* sees which context. They could be combined — use xRAG-style compression within TINYCUA's sub-agent context packaging.

## How to Cite

```
@inproceedings{cheng2024xrag,
  title={xRAG: Extreme Context Compression for Retrieval-augmented Generation with One Token},
  author={Cheng, Xin and Wang, Xun and Zhang, Xingxing and Ge, Tao and Chen, Si-Qing and Wei, Furu and Zhang, Huishuai and Zhao, Dongyan},
  booktitle={Advances in Neural Information Processing Systems (NeurIPS)},
  year={2024}
}
```

## Connection in Lit Review

Use in the Context Engineering section to show that context compression is an active research direction. TINYCUA's contribution is not compression per se, but **context orchestration** — deciding what each agent sees. xRAG proves that reducing context quantity improves quality, validating TINYCUA's premise.
