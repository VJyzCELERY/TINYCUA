# Design: tinycua-finetune

> This file is the technical design for this subproject.
> Authoritative version: `../../../../specs/tinycua-finetune/design.md`

---

## Overview

`tinycua-finetune` provides a supervised fine-tuning pipeline for open-weight LLMs and
vision-LMMs to produce models capable of structured tool-use and agentic behavior. It
covers dataset synthesis from local tool manifests, QLoRA/LoRA training with optional CPU
offload, LoRA adapter merging, and GGUF conversion. Primary target hardware: single GPU
with 16 GB VRAM (7B models); experimental CPU-offload path for 13B models with 32 GB RAM.

---

## Architecture

```
[Tool Manifest Directory]
         |
         v
[synthesize_dataset.py] ──> [JSONL Training Dataset]
                                       |
                              [preprocess.py]
                                       |
              [Base Model (HF, local)] |
                       |               |
                       v               v
                 [train.py] <─────────'
                 qlora | lora | offload
                       |
                       v
           [LoRA Adapter (safetensors)]
                       |
                       v
           [convert_to_gguf.py]
           (merge adapters → GGUF)
                       |
                       v
              [.gguf artifact]
```

---

## Implementation Phases

### Phase 1 — MVP

- [ ] `tinycua_finetune/preprocess.py`
- [ ] `tinycua_finetune/synthesize_dataset.py`
- [ ] `tinycua_finetune/train.py`
- [ ] `tinycua_finetune/convert_to_gguf.py`
- [ ] `data/examples/manifest.json` and `data/examples/train.jsonl`
- [ ] Unit and integration tests
- [ ] Makefile targets: `train-qlora`, `train-offload`, `convert`

### Phase 2 — Enhancements _(post-MVP)_

- [ ] Vision-LMM mode (freeze image encoder, LoRA on LLM side)
- [ ] GPTQ quantization step before GGUF conversion
- [ ] DeepSpeed ZeRO stage 3 config

---

## Technical Decisions

1. **QLoRA as default** — enables 7B on 16 GB VRAM; matches primary hardware target.
2. **Accelerate CPU offload for 13B** — simpler than DeepSpeed for single-node Phase 1.
3. **safetensors** — safe serialization, compatible with HF ecosystem and GGUF converters.
4. **JSONL datasets** — simple, streamable, human-readable.
5. **Special tokens for tool calls** — deterministic parsing; avoids fragile free-text regex.
6. **GGUF conversion via external wrapper** — keeps code minimal; converter scripts change
   frequently and are best treated as a versioned external dependency.
