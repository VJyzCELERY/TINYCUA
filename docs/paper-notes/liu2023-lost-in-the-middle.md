# Lost in the Middle: How Language Models Use Long Contexts

**Authors:** Nelson F. Liu, Kevin Lin, John Hewitt, Ashwin Paranjape, Michele Bevilacqua, Fabio Petroni, Percy Liang
**Year:** 2023 (published TACL 2024)
**Venue:** TACL
**Link:** https://arxiv.org/abs/2307.03172

## Key Finding

Language models perform **best when relevant information is at the beginning or end** of the input context, and **significantly degrade when relevant information is in the middle** of long contexts. Performance also decreases as the input context grows longer, even for explicitly long-context models.

## Experimental Setup

- **Task 1:** Multi-document question answering (find relevant passage among many)
- **Task 2:** Key-value retrieval (find a specific key-value pair in a long list)
- Tested on multiple model families and sizes

## Key Results

- U-shaped performance curve: high at start → low in middle → high at end
- Performance drops sharpen as context length increases
- Even models trained/optimized for long context show this pattern
- The effect is consistent across model architectures and sizes

## Relevance to TINYCUA

This is **the most directly relevant paper** for TINYCUA's core thesis. It provides empirical evidence that:

1. Longer context → degraded performance (supports the "context overload" premise)
2. The position of relevant information matters (supports the "context packaging" approach)
3. Models struggle to identify relevant information when it's surrounded by irrelevant content (supports removing irrelevant context entirely via per-task packaging)

TINYCUA's response: instead of relying on the model to find relevant information in a long context, give each sub-agent only the context it needs — eliminating the "middle" problem by construction.

## How to Cite (TACL 2024 version)

```
@article{liu2024lost,
  title={Lost in the middle: How language models use long contexts},
  author={Liu, Nelson F and Lin, Kevin and Hewitt, John and Paranjape, Ashwin and Bevilacqua, Michele and Petroni, Fabio and Liang, Percy},
  journal={Transactions of the Association for Computational Linguistics},
  volume={12},
  year={2024}
}
```

## Connection to Next Paper

Zhang et al. (2024) — "Found in the Middle" — proposes a positional encoding fix. But this addresses the symptom, not the cause. TINYCUA goes further by removing irrelevant context entirely.
