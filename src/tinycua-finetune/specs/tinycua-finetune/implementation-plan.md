# Implementation: Colab Fine-Tuning Pipeline for Gemma 4 E4B IT

Colab notebook for QLoRA fine-tuning of Gemma 4 E4B IT on agentic reasoning traces, with GDrive checkpointing and auto-resume.

## Context

- **Spec Reference**: `specs/tinycua-finetune/spec.md`
- **Design Reference**: `specs/tinycua-finetune/design.md`
- **Priority**: P0
- **Estimated Effort**: M

## Proposed Changes

### Colab Notebooks

#### [NEW] `tinycua_finetune/colab-gpu-pipeline-finetune-gemma-e4b.ipynb`

- **Description**: Full Colab-compatible notebook with 27 cells covering model loading, dataset preprocessing, chat template application, LoRA config, test training (20 steps), full training (1 epoch), ToolBench eval, and GGUF export.

#### [NEW] `tinycua_finetune/colab_gpu_pipeline_finetune_gemma_e4b-test.ipynb`

- **Description**: Test/experimental variant of the Colab GPU pipeline for Gemma 4B E4B-IT. Provides a focused environment for iterative experimentation and debugging before finalizing the main pipeline.

**Common key design decisions**:
  - Use `FastModel.from_pretrained` (not `FastLanguageModel`) — Gemma 4 is unsupported by the old API
  - Use `tokenizer.tokenizer` for raw tokenizer ops — `Gemma4Processor` wraps the real tokenizer
  - Merge `tool` role messages into preceding `assistant` content to maintain strict `user/assistant` alternation required by the Gemma 4 chat template
  - Consecutive same-role messages merged (handles `assistant→tool→assistant→...` chains)
  - MAX_SEQ_LENGTH = 8192 for T4 16GB VRAM compatibility
  - Train on all tokens (no response-only masking) — full conversation structure is useful signal for agentic behavior
  - GDrive checkpointing with auto-resume from latest checkpoint
  - `train_on_responses_only` removed — was mismatching template tags and causing all-labels-100 issue

### Documentation

#### [MODIFY] `specs/tinycua-finetune/spec.md`

- **Description**: Added FR-013 — train on all tokens, not just assistant responses.

#### [MODIFY] `specs/tinycua-finetune/design.md`

- **Description**: Added technical decision item 5 — rationale for training on all tokens; fixed numbering.

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| colab-gpu-pipeline-finetune-gemma-e4b.ipynb | New | Full fine-tuning notebook for Gemma 4 E4B |
| colab_gpu_pipeline_finetune_gemma_e4b-test.ipynb | New | Test/experimental Colab pipeline variant |
| spec.md | Modify | Added FR-013 |
| design.md | Modify | Added training approach rationale |

## Verification Plan

### Manual Verification

- [ ] Test run (20 steps) completes without NaN loss or OOM on Colab T4
- [ ] Checkpoint saves to GDrive and auto-resumes correctly
- [ ] Full training (1 epoch) completes and model generates coherent tool-calling responses
- [ ] ToolBench eval shows measurable accuracy

### Performance Considerations

- [ ] T4 16GB VRAM fits 8192 seq length with batch_size=2, grad_accum=8
- [ ] Test run completes in ~15 min; full run in ~4-6 hrs

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| OOM on T4 with 8192 seq length | High | Reduce to 4096; or reduce batch_size to 1 |
| Colab session timeout during full training | Medium | GDrive checkpointing every 50 steps + auto-resume |
| Gemma 4 template changes in future unsloth releases | Low | Pin unsloth version; template is baked into tokenizer_config |

---

*Generated from spec.md and design.md*
*Last updated: 2026-05-25*
