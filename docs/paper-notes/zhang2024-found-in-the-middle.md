# Found in the Middle: How Language Models Use Long Contexts Better via Plug-and-Play Positional Encoding

**Authors:** Zhenyu Zhang, Runjin Chen, Shiwei Liu, Zhewei Yao, Olatunji Ruwase, Beidi Chen, Xiaoxia Wu, Zhangyang Wang
**Year:** 2024
**Venue:** NeurIPS 2024
**Link:** https://arxiv.org/abs/2403.04797

## Key Contribution

Proposes **Multi-scale Positional Encoding (Ms-PoE)** to address the "lost-in-the-middle" problem. A plug-and-play method that rescales positional indices to counteract the long-term decay effect of Rotary Position Embedding (RoPE).

## How It Works

- RoPE causes attention weights to decay with distance — tokens in the middle get lower attention
- Ms-PoE rescales position indices differently per attention head
- Different heads focus on different distance scales → multi-scale context fusion
- No fine-tuning required; no additional memory overhead

## Key Results

- Up to +3.8 average accuracy on Zero-SCROLLS benchmark
- Consistent improvement across multiple model families
- Works best for models using RoPE (most modern LLMs)

## Relevance to TINYCUA

This paper addresses the **same problem** as TINYCUA (context degradation) but with a **different approach**:

| Approach | Method | Strength | Weakness |
|----------|--------|----------|----------|
| Found in the Middle | Fix positional encoding | Preserves full context; no information loss | Does not reduce context size; does not prevent softmax dilution |
| TINYCUA | Remove irrelevant context | Eliminates noise at source; reduces token count | May lose information if compaction is imperfect |

TINYCUA's approach is **orthogonal and complementary**: positional encoding fixes help attention distribution, but TINYCUA's context compaction reduces the total attention burden. They could be combined.

## How to Cite

```
@inproceedings{zhang2024found,
  title={Found in the Middle: How Language Models Use Long Contexts Better via Plug-and-Play Positional Encoding},
  author={Zhang, Zhenyu and Chen, Runjin and Liu, Shiwei and Yao, Zhewei and Ruwase, Olatunji and Chen, Beidi and Wu, Xiaoxia and Wang, Zhangyang},
  booktitle={Advances in Neural Information Processing Systems},
  year={2024}
}
```

## Connection in Lit Review

Use this paper to show that the "lost in the middle" problem is recognized and actively being addressed — but existing solutions (positional fixes) address the symptom, not the cause. TINYCUA's context isolation approach is a more fundamental solution.
