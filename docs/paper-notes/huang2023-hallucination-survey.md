# A Survey on Hallucination in Large Language Models: Principles, Taxonomy, Challenges, and Open Questions

**Authors:** Lei Huang, Weijiang Yu, Weitao Ma, Weihong Zhong, Zhangyin Feng, Haotian Wang, Qianglong Chen, Weihua Peng, Xiaocheng Feng, Bing Qin, Ting Liu
**Year:** 2023 (updated 2024)
**Venue:** ACM Transactions on Information Systems (TOIS)
**Link:** https://arxiv.org/abs/2311.05232

## Key Contribution

Comprehensive taxonomy of hallucination in LLMs — categorizes types, causes, detection methods, and mitigation strategies. Establishes hallucination as a systematic problem requiring systematic solutions.

## Hallucination Taxonomy

| Type | Description | Example |
|------|-------------|---------|
| **Intrinsic** | Contradicts source material | Summarizing a document incorrectly |
| **Extrinsic** | Not verifiable from source | Adding facts not in the input |
| **Factual** | Wrong world knowledge | Incorrect dates, names, numbers |
| **Faithfulness** | Output contradicts instruction | Following a prompt incorrectly |

## Causes of Hallucination

1. **Training data issues** — noise, bias, outdated information
2. **Decoding errors** — sampling, exposure bias
3. **Knowledge boundary** — model doesn't know what it doesn't know
4. **Context limitations** — irrelevant or insufficient context

## Mitigation Approaches

| Approach | Method | TINYCUA Relevance |
|----------|--------|-------------------|
| Retrieval augmentation | External knowledge grounding | Information Digester retrieves relevant context |
| Knowledge editing | Update model parameters | Not TINYCUA's approach |
| Decoding strategies | Adjust sampling | Orthogonal to TINYCUA |
| **Context optimization** | **Improve what the model sees** | **TINYCUA's core approach** |

## Key Finding for TINYCUA

The survey identifies **context-related hallucination** as a distinct category — when models generate plausible but incorrect content because the context is noisy, incomplete, or misleading. This is exactly what TINYCUA addresses.

## Relevance to TINYCUA

TINYCUA's context isolation directly mitigates context-induced hallucination:

| Hallucination Cause | TINYCUA Response |
|--------------------|------------------|
| Irrelevant context → attention noise | Sub-agents see only relevant context |
| Long context → lost in the middle | Each agent gets focused, short context |
| Knowledge boundary → confabulation | Information Digester grounds responses in retrieved data |
| Multi-step reasoning → error accumulation | Task decomposition with Result Reviewer |

## How to Cite

```
@article{huang2024survey,
  title={A Survey on Hallucination in Large Language Models: Principles, Taxonomy, Challenges, and Open Questions},
  author={Huang, Lei and Yu, Weijiang and Ma, Weitao and Zhong, Weihong and Feng, Zhangyin and Wang, Haotian and Chen, Qianglong and Peng, Weihua and Feng, Xiaocheng and Qin, Bing and Liu, Ting},
  journal={ACM Transactions on Information Systems},
  year={2024}
}
```

## Connection in Lit Review

Use to **categorize the problem TINYCUA solves**. The survey establishes that hallucination has multiple causes; TINYCUA specifically targets context-induced hallucination through architectural decomposition rather than prompting or fine-tuning.
