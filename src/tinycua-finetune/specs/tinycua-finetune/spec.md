# Specification: tinycua-finetune

> This file is the feature spec for this subproject.
> Authoritative version: `../../../../specs/tinycua-finetune/spec.md`

---

## Problem Statement

Fine-tune open-weight LLMs and vision-LMMs to perform structured tool-use and agentic
behavior, synthesize training datasets directly from local TINYCUA tool manifests, and
export the resulting models to GGUF format for lightweight local inference.

---

## Requirements

- **FR-001**: Accept a local HF-format base model (text LLM or vision-LMM) by directory path.
- **FR-002**: Support QLoRA fine-tuning (4-bit base + LoRA adapters via bitsandbytes).
- **FR-003**: Support standard LoRA fine-tuning (float16 base + LoRA adapters).
- **FR-004**: Support CPU-offload training via Accelerate for experimental 13B runs.
- **FR-005**: Load training data from JSONL files (`id`, `instruction`, `tool_calls`, `output`).
- **FR-006**: Synthesize JSONL training datasets from a local tool manifest directory.
- **FR-007**: Save fine-tuned LoRA adapter weights in safetensors format.
- **FR-008**: Merge LoRA adapters into the base model to produce a standalone HF checkpoint.
- **FR-009**: Convert a merged HF checkpoint to GGUF format.
- **FR-010**: Configure all training parameters via CLI arguments.
- **FR-011**: Inject special tool-call tokens and resize model embeddings before training.
- **FR-012**: For vision-LMM mode, freeze the image encoder and apply LoRA to LLM components only.

---

## Success Criteria

- Dataset synthesis produces a valid JSONL file from a manifest directory.
- QLoRA training run completes and writes a safetensors adapter.
- Merged output loads with `AutoModelForCausalLM.from_pretrained`.
- GGUF artifact loads in llama-cpp-python and responds to a prompt.
- All unit and integration tests pass (`make test`).
- Lint is clean (`make lint`).

---

## Testing Plan

- Unit: JSONL loading, prompt formatting, tokenization, manifest parsing, synthesizer output.
- Integration: 1-step smoke training run on tiny synthetic dataset; conversion wrapper stub.
