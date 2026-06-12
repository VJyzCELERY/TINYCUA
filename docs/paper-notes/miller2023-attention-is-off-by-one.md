# Attention Is Off By One

**Author:** Evan Miller
**Year:** 2023
**Venue:** Blog post (evanmiller.org) — author is at Anthropic
**Link:** https://www.evanmiller.org/attention-is-off-by-one.html

## Key Argument

Softmax in the attention mechanism has an "off-by-one" error: it forces every attention head to allocate probability mass to all tokens, **even when it has no information to add**. The denominator sums only over token scores, so attention weights always sum to 1 — a head cannot choose to "pass."

## Core Mechanism

Standard softmax in attention:

$$(softmax(x))_i = \frac{exp(x_i)}{\sum_j exp(x_j)}$$

The sum of weights is always 1 — the head *must* annotate, even when it would prefer to output zero. This creates noise because:

1. Specialized attention heads often want to abstain
2. Softmax forces them to assign weight somewhere
3. Those forced weights go to irrelevant tokens
4. The noise accumulates across heads and layers

## Proposed Fix: Softmax One (Quiet Attention)

$$(softmax_1(x))_i = \frac{exp(x_i)}{1 + \sum_j exp(x_j)}$$

Adding 1 to the denominator allows attention weights to sum to **less than 1**. When all scores are low, the output vector approaches zero — the head can stay "quiet."

## Relevance to TINYCUA

This paper provides the **mechanistic explanation** for why longer contexts degrade performance:

| Miller's claim | TINYCUA implication |
|----------------|---------------------|
| Softmax forces weight on irrelevant tokens | Irrelevant context consumes attention budget |
| Multi-head attention amplifies the problem | Each head compounds the noise |
| Heads cannot abstain | Every token gets processed, even useless ones |

Miller's solution (fix softmax) is complementary to TINYCUA's. TINYCUA addresses the same root cause — irrelevant tokens polluting attention — but from the **input side**: remove irrelevant context before it reaches the model, rather than fixing how the model handles it internally.

## How to Cite

Since this is a blog post (not a peer-reviewed paper), cite as:

```
Miller, E. (2023). Attention Is Off By One. https://www.evanmiller.org/attention-is-off-by-one.html
```

Or use the arXiv-style if your template allows informal citations:

```
@misc{miller2023attention,
  author = {Miller, Evan},
  title = {Attention Is Off By One},
  year = {2023},
  howpublished = {\url{https://www.evanmiller.org/attention-is-off-by-one.html}}
}
```

> **Note:** This has ~20+ citations on Google Scholar despite being a blog post. It is widely accepted as a valid reference in the ML community.

## Connection in Lit Review

Use after Vaswani (2017) — first establish how attention works, then use Miller to explain **why it breaks under long context**:

1. Vaswani: attention uses softmax over all tokens
2. Miller: softmax forces non-zero weights on irrelevant tokens → noise
3. Liu et al.: empirical proof that this degrades middle-context performance
4. TINYCUA: remove irrelevant context so softmax has nothing to over-attend to
