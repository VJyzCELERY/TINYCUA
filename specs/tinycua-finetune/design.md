# Design Document: TINYCUA Fine-Tune Subproject

**Spec**: [specs/tinycua-finetune/spec.md](spec.md)
**Status**: In Progress
**Last Updated**: 2026-05-11
**Focus**: Kaggle GPU + Unsloth QLoRA Notebook Pipeline

---

## Overview

This document describes the technical design of `tinycua-finetune`, with focus on the
Kaggle GPU + Unsloth notebook-based pipeline for rapid fine-tuning of open-weight LLMs.

The primary approach uses Jupyter notebooks running on Kaggle GPU environments with
Unsloth optimization for efficient QLoRA training on Qwen3-4B and Qwen3-5-9B models.

---

## Architecture

### Notebook Pipeline (Primary Approach - Implemented)

```
[HuggingFace Dataset] (younissk/tool-calling-mix)
         |
         v
[Data Processing] (convert to conversations, filter valid)
         |
         v
[QLoRA Training via Unsloth] (NF4 + double quantization)
         |
         v
[Adapter Merge (optional)]
         |
         v
[Model Save] (local or push to HuggingFace Hub)
```

### Key Notebook Files

| File | Description |
|------|-------------|
| `kaggle-gpu-pipeline-finetune-qwen3-4b-structure.ipynb` | Primary notebook for Qwen3-4B training |
| `kaggle-gpu-pipeline-finetune-qwen3-5-9B.ipynb` | Extended notebook for Qwen3-5-9B training |

### Script-Based Pipeline (Review-Optimized)

The notebook has been split into separate Python scripts for easier code review. Each script corresponds to a notebook cell, enabling standard diff-based code review instead of JSON comparison.

**Directory Structure:**
```
kaggle-unsloth-finetune-pipeline/
├── finetune.py          # Manager script
└── scripts/
    ├── 01_wandb_login.py
    ├── 02_install_unsloth.py
    ├── 03_pip_install_alt.py
    ├── 04_gpu_detection.py
    ├── 05_load_model.py
    ├── 06_lora_config.py
    ├── 07_load_dataset.py
    ├── 08_preprocess_dataset.py
    ├── 09_apply_chat_template.py
    ├── 10_training_config.py
    ├── 11_train_on_responses.py
    ├── 12_run_training.py
    ├── 13_push_lora_to_hf.py
    ├── 14_save_merged_model.py
    ├── 15_export_gguf_direct.py
    ├── 16_export_gguf_llama_cpp.py
    └── 17_push_gguf_to_hf.py
```

**Manager Interface (follows .agents/ pattern):**
```bash
python finetune.py run all      # Run all 17 steps
python finetune.py run 7        # Run step 7 only
python finetune.py run 5-12     # Run steps 5 through 12
```

**Rationale:**
- ipynb files are stored as JSON, making diff review difficult
- Splitting into .py files allows standard code review
- Each script has clear purpose matching cell headers

**Notebook Reconstruction:**
If needed, scripts can be combined back via:
```bash
jupyter nbconvert --to notebook *.py
```

### Component Flow

```
[HuggingFace Dataset]
         |
         v
[Data Processing Cell]
  - Load dataset from HF
  - Convert to conversation format
  - Filter valid examples (valid=True, n_calls>0)
  - Apply chat template
         |
         v
[Model Loading Cell]
  - Load base model via Unsloth
  - Configure tokenizer with chat template
         |
         v
[Training Cell]
  - Configure LoRA parameters (r=16, lora_alpha=32)
  - Set training arguments (lr=1e-4, batch_size=2)
  - Run trainer with W&B integration
         |
         v
[Save/Export Cell]
  - Optionally merge adapter
  - Save locally or push to HF Hub
```

---

## Technical Decisions

1. **Unsloth for QLoRA optimization**
   - **Reason**: 30% less VRAM usage, 2x faster training compared to standard PEFT.
     NF4 quantization with double quantization for additional memory savings.
   - **Alternatives Considered**: Standard PEFT + bitsandbytes — less optimized.

2. **Kaggle GPU as primary environment**
   - **Reason**: Provides reliable P100/V100 GPU access with 16+ GB VRAM.
     No local GPU required, accessible for quick experimentation.
   - **Alternatives Considered**: Google Colab — similar but Kaggle offers better
     persistent storage and competition integration.

3. **Qwen3 model family**
   - **Reason**: Strong open-weight models compatible with Unsloth.
     Qwen3-4B fits comfortably in 16GB VRAM; Qwen3-5-9B for higher capacity.
   - **Alternatives Considered**: Llama-3, Mistral — supported by Unsloth but
     Qwen3 provides good tool-calling capabilities.

4. **HuggingFace datasets as data source**
   - **Reason**: Pre-built tool-calling datasets (younissk/tool-calling-mix)
     provide high-quality training data without manual dataset creation.
   - **Alternatives Considered**: Custom JSONL datasets — supported in future CLI phase.

5. **W&B for experiment tracking**
   - **Reason**: Integrates well with HuggingFace ecosystem, provides useful
     metrics visualization and comparison.
   - **Alternatives Considered**: MLflow — less integrated with HF/Unsloth.

---

## Configuration Parameters

### LoRA Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| r | 16 | LoRA rank |
| lora_alpha | 32 | LoRA alpha |
| lora_dropout | 0.05 | Dropout probability |
| target_modules | q_proj, k_proj, v_proj, o_proj, gate_proj, up_proj, down_proj | Modules to apply LoRA |

### Training Arguments

| Parameter | Default | Description |
|-----------|---------|-------------|
| learning_rate | 1e-4 | Initial learning rate |
| per_device_train_batch_size | 2 | Batch size per device |
| gradient_accumulation_steps | 4 | Gradient accumulation steps |
| num_train_epochs | 3 | Number of training epochs |
| max_seq_length | 512 | Maximum sequence length |
| warmup_steps | 10 | Warmup steps |
| logging_steps | 10 | Logging frequency |
| save_steps | 100 | Checkpoint save frequency |

---

## Risks & Mitigations

| Risk                                      | Likelihood | Impact | Mitigation                                                     |
|-------------------------------------------|------------|--------|----------------------------------------------------------------|
| Kaggle GPU timeout                        | Medium     | Medium | Document expected training time; use gradient checkpointing   |
| Dataset unavailable                       | Low        | High   | Document fallback datasets; handle errors gracefully         |
| Unsloth version incompatibility           | Low        | Medium | Pin tested version in requirements; document in notebook     |
| W&B API key missing                       | Low        | Low    | Make W&B optional; continue training without logging        |

---

## Status

The script-based pipeline is implemented and ready for review. Each script corresponds to a notebook cell for improved reviewability. See `kaggle-unsloth-finetune-pipeline/finetune.py` for orchestration.

---

## References

- Spec: `specs/tinycua-finetune/spec.md`
- Agent Instructions: `AGENTS.md`
- Coding Standards: `.agents/rules/002-code-standards.md`
- Testing Guidelines: `.agents/rules/003-testing.md`
- Unsloth Documentation: https://github.com/unslothai/unsloth
- Qwen3 Models: https://huggingface.co/collections/Qwen
- Tool-calling dataset: younissk/tool-calling-mix
