# Feature Specification: TINYCUA Fine-Tune Subproject

**Status**: In Progress
**Created**: 2026-03-11
**Last Updated**: 2026-05-18
**Subproject(s) Affected**: tinycua-finetune
**Focus**: Kaggle GPU + Unsloth QLoRA Notebook Pipeline

---

## Problem Statement

- **Goals**: Provide a reproducible fine-tuning pipeline using Kaggle GPU environments with Unsloth
  for efficient QLoRA training on open-weight models (Qwen3-4B, Qwen3-5-9B), producing fine-tuned
  models capable of structured tool-use and agentic behavior.
- **Gaps**: TINYCUA currently has no pipeline to train or adapt base models to structured
  tool-call output in cloud/Kaggle environments. Need optimized training for consumer GPU
  environments.
- **Non-Goals**:
  - RLHF / reward-model training.
  - Multi-node distributed training.
  - Accessing proprietary or commercial closed-weight models.
  - Serving, deployment, or inference infrastructure (that belongs to tinycua-runner).
  - Local CLI-based pipeline (deferred to future phase).
- **Constraints**:
  - Target: Kaggle GPU (P100/V100, 16+ GB VRAM).
  - Unsloth optimization for 30% less VRAM and 2x faster training.
  - QLoRA (4-bit NF4 + double quantization) via Unsloth.
  - Must produce HF-format checkpoints or push to HuggingFace Hub.

---

## User Scenarios & Testing

### Primary Scenario (Kaggle + Unsloth Notebook)

A developer runs the Jupyter notebook (`kaggle-gpu-pipeline-finetune-qwen3-4b-structure.ipynb`)
on Kaggle, which:
1. Loads a tool-calling dataset from HuggingFace (e.g., younissk/tool-calling-mix)
2. Applies data processing (convert to conversations, filter valid examples)
3. Fine-tunes a Qwen3-4B (or Qwen3-5-9B) base model using QLoRA via Unsloth
4. Optionally merges the LoRA adapter into base weights
5. Saves the model locally or pushes to HuggingFace Hub

This approach is suitable for:
- Kaggle/Google Colab GPU environments
- Rapid prototyping and experimentation
- Resource-efficient training (Unsloth optimization)
- Quick iteration on model/dataset combinations

### Acceptance Scenarios

1. **Given** a HuggingFace tool-calling dataset (e.g., younissk/tool-calling-mix) and a base model
   (Qwen3-4B/Qwen3-5-9B), **When** the Kaggle notebook pipeline is executed, **Then** a fine-tuned
   model checkpoint is saved/pushed without error.
2. **Given** a Kaggle notebook environment with GPU access, **When** Unsloth QLoRA training is run,
   **Then** training completes with ~30% less VRAM usage compared to standard PEFT.
3. **Given** a trained LoRA adapter and its corresponding base model, **When** adapter merging is
   invoked, **Then** a standalone HF-format checkpoint is produced.
4. **Given** invalid or filtered-out dataset examples, **When** data processing runs, **Then** those
   examples are skipped and only valid records are used for training.
5. **Given** W&B integration is configured, **When** training runs, **Then** experiment metrics
   are logged to the specified W&B project.

### Testing Approach

This pipeline targets Kaggle GPU environments as a notebook-driven experimental flow. Standard unit/integration tests are not applied because:
- **GPU-dependent**: requires Kaggle GPU (P100/V100) — no CI runner has this
- **External services**: HF datasets, W&B, Unsloth — require live API keys and runtime environments
- **Notebook-native**: primary artifact is a Kaggle notebook; scripts exist for review clarity only

**Validation**: run the notebook end-to-end on Kaggle and verify training completes without error. See `design.md` for full rationale.

### Edge Cases

- What happens when the HuggingFace dataset fails to load? The notebook must raise a clear error
  with dataset name and loading instructions.
- What if the base model is not available on HuggingFace? The notebook must handle the error
  and suggest alternative model IDs.
- What is the behavior when GPU VRAM is exceeded? Unsloth handles this gracefully, but the
  notebook should document expected VRAM usage for each model size.
- What happens when W&B API key is not configured? Training should proceed without error,
  skipping W&B logging.

---

## Requirements

### Functional Requirements

- **FR-001**: System MUST load training data from HuggingFace datasets (e.g., younissk/tool-calling-mix).
- **FR-002**: System MUST support QLoRA fine-tuning via Unsloth (NF4 + double quantization).
- **FR-003**: System MUST support Qwen3-4B and Qwen3-5-9B base models.
- **FR-004**: System MUST apply data processing: convert to conversation format, filter valid examples.
- **FR-005**: System MUST save fine-tuned model to local output directory or push to HuggingFace Hub.
- **FR-006**: System MUST optionally merge LoRA adapter into base weights before saving.
- **FR-007**: System MUST integrate with W&B for experiment tracking (optional, configurable).
- **FR-008**: System MUST configure training parameters: learning rate, batch size, gradient
  accumulation steps, max sequence length, epochs/steps via notebook cells.
- **FR-009**: System MUST use chat template formatting for model input/output.

### Key Entities

- **HuggingFace Dataset**: Pre-built tool-calling datasets (younissk/tool-calling-mix, etc.)
- **Base Model**: Qwen3-4B or Qwen3-5-9B from Unsloth or HuggingFace
- **LoRA Adapter**: Fine-tuned adapter weights via Unsloth/PEFT
- **Merged Checkpoint**: Full HF-format model after adapter merge
- **Fine-tuned Model**: Saved locally or pushed to HuggingFace Hub
- **Notebook Scripts**: Modular Python scripts derived from notebook cells for reviewability
  - Location: `kaggle-unsloth-finetune-pipeline/scripts/`
  - 17 scripts (01_wandb_login through 17_push_gguf_to_hf)
- **Manager Script**: finetune.py - orchestrates script execution via CLI

---

## Success Criteria

- **Notebook runs end-to-end**: Kaggle notebook completes without error from dataset loading
  through model save/push.
- **Training produces checkpoint**: QLoRA training writes adapter weights to output directory.
- **Merge produces valid HF checkpoint**: Merged output loads correctly with AutoModelForCausalLM.
- **Model pushes to Hub**: Optional push to HuggingFace Hub succeeds and produces valid model page.
- **VRAM efficiency**: Unsloth provides measurable VRAM savings vs standard PEFT.

---

## Testing Plan

### Manual Tests

- Run notebook on Kaggle with P100 GPU and verify successful completion.
- Verify fine-tuned model loads and generates tool-call responses.
- Test optional adapter merge and verify merged model works.
- Test optional HuggingFace Hub push and verify model page.

---

## Status Tracker

| Item                        | Status      | Notes                                      |
|-----------------------------|-------------|--------------------------------------------|
| Spec                        | In Progress | This document                              |
| Design                      | In Progress | See design.md                              |
| Kaggle notebook (4B)        | DONE        | kaggle-gpu-pipeline-finetune-qwen3-4b-structure.ipynb |
| Kaggle notebook (9B)        | TODO        | kaggle-gpu-pipeline-finetune-qwen3-5-9B.ipynb |
| Script-based pipeline       | DONE        | 17 scripts + finetune.py manager          |
| W&B integration             | DONE        | Integrated in notebooks                   |
| HF Hub push                 | DONE        | Optional feature in notebooks              |
| Adapter merge               | DONE        | Implemented in notebooks                   |

---

## References

- Notebook: `src/tinycua-finetune/tinycua_finetune/kaggle-gpu-pipeline-finetune-qwen3-4b-structure.ipynb`
- Pipeline scripts: `src/tinycua-finetune/tinycua_finetune/kaggle-unsloth-finetune-pipeline/`
- Manager: `finetune.py` (run via `python finetune.py run all`)
- Unsloth: https://github.com/unslothai/unsloth
- Dataset: younissk/tool-calling-mix

---

## Review Checklist

- [x] No implementation details (no code, framework, or architecture choices)
- [x] All mandatory sections completed
- [x] No `[NEEDS CLARIFICATION]` markers remain
- [x] Requirements are testable and unambiguous
- [x] Scope is clearly bounded with explicit non-goals
- [x] Success criteria are measurable