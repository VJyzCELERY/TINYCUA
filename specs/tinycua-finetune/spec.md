# Feature Specification: TINYCUA Fine-Tune Subproject

**Status**: In Progress
**Created**: 2026-03-11
**Last Updated**: 2026-05-25
**Subproject(s) Affected**: tinycua-finetune

---

## Problem Statement

- **Goals**: Provide a reproducible fine-tuning pipeline so a developer can take any open-weight
  base model (text LLM or vision-LMM) and produce a fine-tuned model that reliably performs
  tool-use and agentic behavior, then export the result to GGUF format for lightweight local
  inference on consumer hardware.
- **Gaps**: TINYCUA currently has no pipeline to train or adapt base models to structured
  tool-call output. There is no dataset generation facility that ties training data to the
  actual tools that exist in the project. There is no conversion step to produce portable GGUF
  artifacts.
- **Non-Goals**:
  - RLHF / reward-model training.
  - Multi-node distributed training.
  - Accessing proprietary or commercial closed-weight models.
  - Serving, deployment, or inference infrastructure (that belongs to tinycua-runner).
  - Automated hyperparameter search.
- **Constraints**:
  - Must run on a single consumer GPU (target: 16 GB VRAM) for 7B models.
  - Must support experimental 13B runs via CPU-offload on the same hardware (32 GB system RAM).
  - Must produce standard HF-format checkpoints (safetensors) as an intermediate artifact.
  - Tool-call format must be compatible with TINYCUA tool manifest conventions so that
    generated data can later be consumed by tinycua-runner.
  - Must provide a Colab-compatible GPU pipeline for cloud-based fine-tuning with free-tier
    GPU access (target: Gemma 4B E4B-IT on T4/L4 GPU, 16 GB VRAM).

---

## User Scenarios & Testing

### Primary Scenario

A developer has a local directory of TINYCUA tools each with a manifest descriptor. They run
the dataset synthesizer which reads each tool's manifest, generates instruction-response pairs
that include structured tool invocations, and writes a JSONL training file. They then run the
training entry-point against a local HF base model using QLoRA mode, receive a saved LoRA
adapter checkpoint, merge it into the base weights, and finally convert the merged checkpoint
to a GGUF file they can load directly in llama.cpp or llama-cpp-python.

### Acceptance Scenarios

1. **Given** a base text LLM in HF format and a JSONL training file, **When** training is
   invoked in QLoRA mode, **Then** a LoRA adapter checkpoint in safetensors format is written
   to the configured output directory.
2. **Given** a local tools directory containing at least one tool with a valid manifest,
   **When** the dataset synthesizer is run, **Then** a valid JSONL file is produced containing
   at least one record per tool with the correct schema fields
   (`id`, `instruction`, `tool_calls`, `output`).
3. **Given** a trained LoRA adapter and its corresponding base model, **When** the conversion
   command is run, **Then** a `.gguf` file is produced in the output directory.
4. **Given** a vision-LMM base model in HF format, **When** training is configured for VLM
   mode, **Then** only the LLM components receive LoRA adapters (the image encoder is frozen).
5. **Given** a 13B model that exceeds GPU VRAM, **When** offload mode is enabled,
   **Then** training proceeds by paging model layers to CPU RAM without crashing.
6. **Given** a tool manifest with no `dry_run_output` field, **When** the synthesizer runs,
   **Then** it raises a clear validation error naming the missing field.

### Edge Cases

- What happens when the JSONL dataset is empty? The preprocessor must raise a clear error
  before training begins.
- What if the base model directory is missing or corrupt? The training entry-point must fail
  fast with an actionable error message.
- What is the behavior when GPU VRAM is exceeded without offload enabled? The system should
  surface the OOM error as-is (no silent fallback).
- What happens when a tool manifest contains a tool with an unsupported args schema type?
  The synthesizer must log a warning and skip that tool rather than crash.

---

## Requirements

### Functional Requirements

- **FR-001**: System MUST accept a local Hugging Face format base model (text LLM or
  vision-LMM) as input identified by a local directory path.
- **FR-002**: System MUST support QLoRA fine-tuning mode (4-bit quantized base model +
  LoRA adapters via bitsandbytes).
- **FR-003**: System MUST support standard LoRA fine-tuning mode (float16 base model +
  LoRA adapters) as an alternative to QLoRA.
- **FR-004**: System MUST support CPU-offload training mode via Accelerate to allow
  experimental 13B training on 16 GB VRAM + 32 GB system RAM.
- **FR-005**: System MUST load training data from JSONL files where each record contains
  at minimum: `id`, `instruction`, `tool_calls` (list), and `output`.
- **FR-006**: System MUST include a dataset synthesizer that reads a tool manifest
  directory and generates JSONL training records covering each listed tool.
- **FR-007**: System MUST save fine-tuned LoRA adapter weights in safetensors format.
- **FR-008**: System MUST provide a merge step that combines LoRA adapters with the base
  model to produce a standalone HF-format checkpoint (safetensors).
- **FR-009**: System MUST provide a conversion step that takes the merged HF checkpoint
  and produces a GGUF artifact suitable for llama.cpp inference.
- **FR-010**: Users MUST be able to configure all training parameters (model path, dataset
  path, output path, mode, LoRA rank, learning rate, batch size, gradient accumulation
  steps, max sequence length, epochs/steps) via CLI arguments.
- **FR-011**: System MUST inject special tokens for structured tool-call formatting
  (`<tool>`, `</tool>`, `<tool_name>`, `</tool_name>`, `<tool_args>`, `</tool_args>`,
  `<tool_result>`, `</tool_result>`) and resize model embeddings accordingly.
- **FR-012**: For vision-LMM mode, System MUST freeze the image encoder and apply LoRA
  adapters only to the language model components.

### Key Entities

- **Tool Manifest**: JSON file describing one tool — name, description, args schema,
  example call, and dry-run output. Stored alongside each tool or in a central
  `manifest.json`.
- **Training Dataset**: JSONL file with one record per line. Each record represents one
  training example with an instruction, optional context input, structured tool calls, and
  the expected final answer.
- **Training Config**: The set of parameters that fully describe a training run (model
  path, mode, hyperparameters, output paths). Can be provided via CLI.
- **LoRA Adapter**: Fine-tuned adapter weights (safetensors) that augment a frozen base
  model. Lightweight and model-family-specific.
- **Merged Checkpoint**: Full HF-format model produced by merging LoRA adapters into the
  base model weights. Ready for conversion.
- **GGUF Artifact**: Final model file in GGUF format. Portable, quantized, loadable
  directly by llama.cpp / llama-cpp-python for CPU or hybrid inference.

---

## Success Criteria

- **Dataset synthesis works end-to-end**: Given a manifest directory, the synthesizer
  produces a valid, non-empty JSONL file with correct schema.
- **Training produces a checkpoint**: A full QLoRA training run (even 1–5 steps on a
  small synthetic dataset) completes without error and writes a safetensors adapter.
- **Merge produces a valid HF checkpoint**: The merged output loads correctly with
  `AutoModelForCausalLM.from_pretrained`.
- **Conversion produces a loadable GGUF**: The `.gguf` artifact loads in llama-cpp-python
  and responds to a prompt without error.
- **Offload mode extends reachable model size**: A 13B model that OOMs without offload
  can be trained with offload mode enabled on 16 GB VRAM + 32 GB RAM.
- **All unit tests pass**: `make test` passes with no failures.
- **Lint is clean**: `make lint` produces no errors.

---

## Testing Plan

### Unit Tests

- Preprocessor: JSONL loading (happy path, empty file, missing field), prompt formatting
  with tool tokens, tokenization output shapes.
- Manifest loader: valid manifest parsing, missing required field error, unsupported args
  type warning and skip behavior.
- Dataset synthesizer: record count matches tool count, output schema validation,
  output file is valid JSONL.

### Integration Tests

- Smoke training run: 1–10 training steps on a tiny synthetic dataset (10 records) with a
  small stub/CPU model to verify the full pipeline runs without error.
- Conversion stub: given a minimal HF checkpoint, the conversion wrapper runs without
  crashing and produces an output file (even if GGUF tooling is absent, the wrapper must
  fail loudly with an actionable message rather than silently).

### Manual Tests

- Full QLoRA run on a real 7B model locally with the example manifest dataset.
- Load produced GGUF in llama-cpp-python and verify tool-call token output.

---

## Status Tracker

| Item                        | Status      | Notes                                      |
|-----------------------------|-------------|--------------------------------------------|
| Spec                        | In Progress | This document                              |
| Design                      | In Progress | See design.md                              |
| Subproject scaffold          | In Progress | Folder structure, Makefile, pyproject.toml |
| Dataset schema              | TODO        |                                            |
| Tool manifest schema         | TODO        |                                            |
| Preprocessor                | TODO        |                                            |
| Dataset synthesizer         | TODO        |                                            |
| Training engine (QLoRA)     | In Progress | QLoRA via Colab GPU pipeline (Gemma 4B)   |
| Training engine (offload)   | TODO        |                                            |
| Adapter merge               | TODO        |                                            |
| GGUF conversion wrapper     | TODO        |                                            |
| Vision-LMM support          | TODO        | Phase 2                                    |

---

## Open Questions

1. **Tool manifest location convention**
   - **Owner**: TBD
   - **Target**: Before Phase 1 implementation
   - **Status**: Discussion
   - **Proposed Answer**: Each tool lives in its own directory under a `tools/` folder;
     each tool directory contains a `manifest.json`. The synthesizer accepts a root
     `tools/` directory path and discovers manifests recursively.

2. **GGUF conversion tooling version pinning**
   - **Owner**: TBD
   - **Target**: Before Phase 1 implementation
   - **Status**: Discussion
   - **Proposed Answer**: Document the exact tested version of the llama.cpp conversion
     helper in `docs/` and fail loudly with the expected version if it is absent.

3. **Supported base model families (Phase 1)**
   - **Owner**: TBD
   - **Target**: Before Phase 1 implementation
   - **Status**: Proposed
   - **Proposed Answer**: Any HF CausalLM model that is compatible with PEFT LoRA
     (Llama-2, Mistral, Falcon). VLM families deferred to Phase 2.

---

## Review Checklist

- [x] No implementation details (no code, framework, or architecture choices)
- [x] All mandatory sections completed
- [ ] No `[NEEDS CLARIFICATION]` markers remain
- [x] Requirements are testable and unambiguous
- [x] Scope is clearly bounded with explicit non-goals
- [x] Success criteria are measurable
