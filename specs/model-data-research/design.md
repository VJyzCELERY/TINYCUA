# Design Document: Model & Dataset Research for TINYCUA Finetuning

**Spec**: [specs/model-data-research/spec.md](spec.md)
**Status**: Draft
**Last Updated**: 2026-05-18
**Goal**: Research and decide optimal model & dataset for LLM fine-tuning on 16GB VRAM

---

## Overview

This document catalogs candidate models, datasets, and training configurations for TINYCUA's fine-tuning pipeline. Each option is annotated with VRAM budget, quality benchmarks, and references. The output is a structured decision matrix that justifies the final model+dataset selection for thesis defense.

---

## Model Options

### Option A: Qwen3.5-9B

| Attribute | Value |
|-----------|-------|
| **Parameters** | 9B |
| **Architecture** | Dense transformer, Gated Delta Network, Hybrid Attention |
| **Context Length** | 262K (1M with YaRN) |
| **MMLU-Pro** | 82.5 |
| **GPQA Diamond** | 81.7 |
| **Languages** | 201 |
| **Multimodal** | Native (early fusion) — no separate VL variant needed |
| **VRAM (INT4)** | ~6GB |
| **VRAM (QLoRA 4-bit train)** | ~10-12GB |
| **Fits 16GB?** | ✅ Yes |
| **Unsloth Compatible** | ✅ Yes |
| **Reference** | [Qwen3 Technical Report](https://arxiv.org/abs/2505.09388) (2025) |

### Option B: LLaMA-3-8B

| Attribute | Value |
|-----------|-------|
| **Parameters** | 8B |
| **Architecture** | Dense transformer (standard) |
| **Context Length** | 8K (extended to 128K in some variants) |
| **MMLU-Pro** | ~70 |
| **GPQA Diamond** | ~65 |
| **Languages** | ~20 |
| **Multimodal** | No (requires LLaMA-VL variant) |
| **VRAM (INT4)** | ~8GB |
| **VRAM (QLoRA 4-bit train)** | ~12-14GB |
| **Fits 16GB?** | ✅ Yes (tight) |
| **Unsloth Compatible** | ✅ Yes |
| **Reference** | [LLaMA 3](https://arxiv.org/abs/2407.21783) (2024) |

### Option C: DeepSeek-Coder-9B

| Attribute | Value |
|-----------|-------|
| **Parameters** | 9B |
| **Architecture** | Dense transformer |
| **Context Length** | 4K (extended to 32K in V2) |
| **MMLU-Pro** | ~65 (code-focused) |
| **GPQA Diamond** | N/A |
| **Languages** | ~10 (English/Chinese focused) |
| **Multimodal** | No (requires DeepSeek-VL) |
| **VRAM (INT4)** | ~6GB |
| **VRAM (QLoRA 4-bit train)** | ~10-12GB |
| **Fits 16GB?** | ✅ Yes |
| **Unsloth Compatible** | ✅ Yes |
| **Reference** | [DeepSeek-Coder](https://huggingface.co/deepseek-ai/deepseek-coder-9b-base) (2024) |

### Option D: Mistral-7B-v0.3

| Attribute | Value |
|-----------|-------|
| **Parameters** | 7.3B |
| **Architecture** | Dense transformer, sliding window attention |
| **Context Length** | 32K |
| **MMLU-Pro** | ~68 |
| **GPQA Diamond** | ~60 |
| **Languages** | ~20 (English/French focused) |
| **Multimodal** | No |
| **VRAM (INT4)** | ~5GB |
| **VRAM (QLoRA 4-bit train)** | ~9-11GB |
| **Fits 16GB?** | ✅ Yes |
| **Unsloth Compatible** | ✅ Yes |
| **Reference** | [Mistral v0.3](https://huggingface.co/mistralai/Mistral-7B-v0.3) (2024) |

### Option E: Gemma-2-9B

| Attribute | Value |
|-----------|-------|
| **Parameters** | 9B |
| **Architecture** | Dense transformer, GeGLU, sliding window |
| **Context Length** | 8K |
| **MMLU-Pro** | ~72 |
| **GPQA Diamond** | ~67 |
| **Languages** | ~20 (multilingual) |
| **Multimodal** | No |
| **VRAM (INT4)** | ~7GB |
| **VRAM (QLoRA 4-bit train)** | ~11-13GB |
| **Fits 16GB?** | ✅ Yes |
| **Unsloth Compatible** | ✅ Yes |
| **Reference** | [Gemma 2](https://arxiv.org/abs/2408.00118) (2024) |

### Option F: Qwen3-4B (lightweight baseline)

| Attribute | Value |
|-----------|-------|
| **Parameters** | 4B |
| **Architecture** | Dense transformer, Gated Delta Network |
| **Context Length** | 32K |
| **MMLU-Pro** | ~72 |
| **GPQA Diamond** | ~68 |
| **Languages** | 119 |
| **Multimodal** | No |
| **VRAM (INT4)** | ~3GB |
| **VRAM (QLoRA 4-bit train)** | ~6-8GB |
| **Fits 16GB?** | ✅ Yes (plenty of headroom) |
| **Unsloth Compatible** | ✅ Yes |
| **Reference** | [Qwen3 Technical Report](https://arxiv.org/abs/2505.09388) (2025) |

---

## Dataset Options

### Dataset A: tool-calling-mix (younissk)

| Attribute | Value |
|-----------|-------|
| **Samples** | ~3K |
| **Task Type** | Tool-calling / function-calling |
| **License** | MIT |
| **Language** | English |
| **Format** | Conversations with tool_calls array |
| **Source** | [younissk/tool-calling-mix](https://huggingface.co/datasets/younissk/tool-calling-mix) |
| **Already Used In** | Current TINYCUA pipeline |
| **VRAM (BS=1, seq=2048)** | ~10-12GB (with Qwen3.5-9B) |
| **Fits 16GB?** | ✅ Yes |
| **Notes** | Small, curated dataset. Fast iteration. Limited diversity. |

### Dataset B: ToolBench

| Attribute | Value |
|-----------|-------|
| **Samples** | ~120K |
| **Task Type** | Tool-calling (REST APIs) |
| **License** | MIT |
| **Language** | English |
| **Format** | Instruction + tool call sequences |
| **Source** | [THUDM/ToolBench](https://github.com/THUDM/ToolBench) |
| **VRAM (BS=1, seq=2048)** | ~12-14GB (with Qwen3.5-9B) |
| **Fits 16GB?** | ✅ Yes (tight) |
| **Notes** | Large, diverse tool set. Multi-step reasoning chains. |

### Dataset C: Glaive Function Calling V2

| Attribute | Value |
|-----------|-------|
| **Samples** | ~15K |
| **Task Type** | Function-calling |
| **License** | CC-BY-NC-4.0 |
| **Language** | English |
| **Format** | System prompt + function definitions + conversation turns |
| **Source** | [glaiveai/glaive-function-calling-v2](https://huggingface.co/datasets/glaiveai/glaive-function-calling-v2) |
| **VRAM (BS=1, seq=2048)** | ~10-12GB (with Qwen3.5-9B) |
| **Fits 16GB?** | ✅ Yes |
| **Notes** | High-quality synthetic data. Multi-turn conversation format. Commercial use restricted. |

### Dataset D: OpenHermes-2.5

| Attribute | Value |
|-----------|-------|
| **Samples** | ~1M |
| **Task Type** | General instruction following |
| **License** | MIT |
| **Language** | English |
| **Format** | System + user + assistant turns |
| **Source** | [teknium/OpenHermes-2.5](https://huggingface.co/datasets/teknium/OpenHermes-2.5) |
| **VRAM (BS=1, seq=2048)** | ~12-14GB (with Qwen3.5-9B) |
| **Fits 16GB?** | ✅ Yes (tight) |
| **Notes** | Largest option. General instruction, not tool-specific. May require filtering for tool-use subset. |

### Dataset E: Magpie-Pro

| Attribute | Value |
|-----------|-------|
| **Samples** | ~300K |
| **Task Type** | General instruction following |
| **License** | MIT |
| **Language** | English |
| **Format** | User + assistant turns (synthetic from strong models) |
| **Source** | [Magpie](https://huggingface.co/datasets/Magpie-Align/Magpie-Pro) |
| **VRAM (BS=1, seq=2048)** | ~12-14GB (with Qwen3.5-9B) |
| **Fits 16GB?** | ✅ Yes (tight) |
| **Notes** | Synthetic high-quality data from GPT-4. General purpose, not tool-specific. |

### Dataset F: AgentInstruct

| Attribute | Value |
|-----------|-------|
| **Samples** | ~2M |
| **Task Type** | Agentic / tool-use |
| **License** | MIT |
| **Language** | English |
| **Format** | Multi-turn conversations with tool calls |
| **Source** | [THUDM/AgentInstruct](https://huggingface.co/datasets/THUDM/AgentInstruct) |
| **VRAM (BS=1, seq=2048)** | ~14-16GB (with Qwen3.5-9B) |
| **Fits 16GB?** | ⚠️ Marginal (may OOM) |
| **Notes** | Very large. Agent-specific. May need filtering/subsetting or reduced seq length. |

---

## VRAM Budget Analysis

All estimates assume **QLoRA (NF4, double quantization)**, **gradient checkpointing enabled**, **batch size = 1**, **gradient accumulation = 12**.

| Model | Base VRAM (4-bit) | Training VRAM | Fits 16GB? |
|-------|-------------------|---------------|------------|
| Qwen3-4B | ~3GB | ~6-8GB | ✅ Spare |
| Mistral-7B | ~5GB | ~9-11GB | ✅ Spare |
| DeepSeek-Coder-9B | ~6GB | ~10-12GB | ✅ Good |
| Qwen3.5-9B | ~6GB | ~10-12GB | ✅ Good |
| Gemma-2-9B | ~7GB | ~11-13GB | ✅ Good |
| LLaMA-3-8B | ~8GB | ~12-14GB | ✅ Tight |

### With Different Sequence Lengths

| Model | Seq 1024 | Seq 2048 | Seq 4096 |
|-------|----------|----------|----------|
| Qwen3-4B | ~6GB | ~7GB | ~9GB |
| Qwen3.5-9B | ~10GB | ~11GB | ~13GB |
| Mistral-7B | ~9GB | ~10GB | ~12GB |
| LLaMA-3-8B | ~12GB | ~13GB | ~15GB ⚠️ |

---

## Decision Matrix

### Top Contenders

| Model | Dataset | VRAM | Quality | Tool-Specific | Recommendation |
|-------|---------|------|---------|---------------|---------------|
| **Qwen3.5-9B** | tool-calling-mix | ~11GB | Best reasoning | ✅ Native tool-call | **🏆 Best overall** |
| **Qwen3.5-9B** | Glaive FC V2 | ~11GB | Best reasoning | ✅ Native tool-call | **🏆 Best quality** |
| Qwen3.5-9B | ToolBench | ~13GB | Best reasoning | ✅ Multi-step tool | Strong alternative |
| Qwen3-4B | tool-calling-mix | ~7GB | Good | ✅ Native tool-call | Fastest iteration |
| Mistral-7B | Glaive FC V2 | ~10GB | Good | ⚠️ Needs training | Lightweight option |
| LLaMA-3-8B | OpenHermes | ~13GB | Good | ❌ General only | Baseline comparison |

---

## Final Recommendation

### Model: Qwen3.5-9B

**Justification**:
- Highest reasoning benchmarks (MMLU-Pro 82.5, GPQA 81.7) among 9B models.
- Most VRAM-efficient at INT4 (~6GB base, ~10-12GB training) leaving headroom for longer sequences.
- Native multimodal (early fusion) — essential if pipeline evolves to process screenshots.
- 262K context length supports complex multi-turn agent conversations.
- 201 languages enables multilingual agent scenarios.
- Strongest Unsloth community support. — [Qwen3 Technical Report (2025)](https://arxiv.org/abs/2505.09388)
- Unsloth-optimized: 2x faster training, 50% less VRAM vs raw HuggingFace. — [Unsloth Benchmarks](https://github.com/unslothai/unsloth)

### Dataset (Tier 1): Glaive Function Calling V2

**Justification**:
- Tool-call specific format reduces wasted training on non-agentic samples.
- ~15K high-quality synthetic samples — sufficient for domain adaptation, low risk of overfitting.
- Multi-turn conversation format aligns with agent deployment.
- Fits comfortably in ~11GB VRAM with Qwen3.5-9B.
- Proven in open-source agent fine-tuning community.

### Dataset (Tier 2 Fallback): tool-calling-mix

**Justification**:
- Already integrated into current TINYCUA pipeline — zero migration cost.
- ~3K curated samples for rapid prototyping before scaling up.
- MIT license — no restrictions.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Glaive FC V2 has NC license | High | Low | Use tool-calling-mix for thesis; Glaive for internal experiments |
| Qwen3.5-9B may not support Unsloth at branch cut | Medium | High | Check Unsloth model support matrix; fallback to Qwen3-4B |
| 15K samples insufficient for generalization | Low | Medium | Mix with OpenHermes subset for diversity |
| 16GB VRAM OOM with seq > 2048 | Medium | Medium | Use gradient checkpointing + gradient accumulation; test with seq=1024 first |

---

## References

- **Spec**: [specs/model-data-research/spec.md](spec.md)
- **Existing References**: `src/tinycua-finetune/references/` — detailed model, PEFT, hardware analysis
- **Key Papers**:
  - Qwen3 Technical Report (2025) — [arXiv:2505.09388](https://arxiv.org/abs/2505.09388)
  - QLoRA (2023) — [arXiv:2305.14314](https://arxiv.org/abs/2305.14314)
  - LLaMA 3 (2024) — [arXiv:2407.21783](https://arxiv.org/abs/2407.21783)
  - Gemma 2 (2024) — [arXiv:2408.00118](https://arxiv.org/abs/2408.00118)
  - DeepSeek-Coder (2024) — [HuggingFace](https://huggingface.co/deepseek-ai/deepseek-coder-9b-base)
  - Mistral v0.3 (2024) — [HuggingFace](https://huggingface.co/mistralai/Mistral-7B-v0.3)
- **Key Datasets**:
  - tool-calling-mix — [HF: younissk/tool-calling-mix](https://huggingface.co/datasets/younissk/tool-calling-mix)
  - ToolBench — [GitHub: THUDM/ToolBench](https://github.com/THUDM/ToolBench)
  - Glaive FC V2 — [HF: glaiveai/glaive-function-calling-v2](https://huggingface.co/datasets/glaiveai/glaive-function-calling-v2)
  - OpenHermes-2.5 — [HF: teknium/OpenHermes-2.5](https://huggingface.co/datasets/teknium/OpenHermes-2.5)
  - AgentInstruct — [HF: THUDM/AgentInstruct](https://huggingface.co/datasets/THUDM/AgentInstruct)
