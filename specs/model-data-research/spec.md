# Feature Specification: Model & Dataset Research for TINYCUA Finetuning

**Status**: Draft
**Created**: 2026-05-18
**Last Updated**: 2026-05-18
**Subproject(s) Affected**: tinycua-finetune

---

## Problem Statement

- **Goals**: Research and document available open-weight LLMs, datasets, and fine-tuning configurations suitable for computer-use agent training on consumer GPU hardware (16GB VRAM). Produce a curated decision matrix to guide model/dataset selection for TINYCUA's fine-tuning pipeline.
- **Gaps**: The current pipeline is built around Qwen3-4B/Qwen3.5-9B + tool-calling-mix dataset. No structured comparison exists to justify these choices versus alternatives (DeepSeek, LLaMA, Mistral, other datasets). No VRAM budget analysis maps each option to hardware feasibility.
- **Non-Goals**:
  - Running actual training experiments (this is a research-only branch).
  - Serving, deployment, or inference infrastructure.
  - Code implementation of any kind.
- **Constraints**:
  - Target GPU: RTX 5080 Laptop (16GB VRAM).
  - PEFT method: QLoRA (NF4 + double quantization).
  - Framework: Unsloth-compatible models only.
  - Must support tool-calling / function-calling fine-tuning format.

---

## User Scenarios & Testing

### Primary Scenario

A developer or thesis student wants to select the optimal model and dataset for fine-tuning a computer-use LLM. They browse the collected references to compare options by key criteria: reasoning benchmarks, VRAM footprint, context length, multilingual support, dataset quality, and tool-calling compatibility.

### Acceptance Scenarios

1. **Given** a list of candidate models, **When** comparing VRAM requirements, **Then** each model shows its 4-bit quantized VRAM footprint (ensuring at least one option fits 16GB).
2. **Given** a list of candidate datasets, **When** reviewing dataset statistics, **Then** each dataset includes: number of samples, domain focus, tool-call format, license, and source URL.
3. **Given** a hardware constraint of 16GB VRAM, **When** evaluating any model+dataset combination, **Then** a VRAM budget table shows the combination is feasible.

---

## Requirements

### Functional Requirements

- **FR-001**: Spec MUST catalog at least 5 open-weight LLMs (3B-9B params) with reasoning benchmarks and VRAM estimates at 4-bit quantization.
- **FR-002**: Spec MUST catalog at least 5 publicly available datasets suitable for tool-calling / function-calling / agent fine-tuning.
- **FR-003**: Each model entry MUST include: parameter count, architecture type, context length, supported languages, MMLU-Pro/GPQA scores, VRAM estimate (INT4), and source paper/model card URL.
- **FR-004**: Each dataset entry MUST include: sample count, task type (tool-call, function-call, agentic), license, language, data format, source URL, and hardware feasibility notes.
- **FR-005**: Design MUST provide option matrices mapping each model+dataset+config combination to a VRAM budget and expected quality trade-off.

### Key Entities

- **Open-Weight LLM**: A pre-trained language model with publicly available weights suitable for fine-tuning (e.g., Qwen3.5-9B, LLaMA-3-8B, DeepSeek-Coder-9B, Mistral-7B, Gemma-2-9B).
- **Fine-Tuning Dataset**: A structured collection of instruction-response pairs, optionally with tool-call/function-call annotations (e.g., tool-calling-mix, ToolBench, Glaive, OpenHermes, Magpie).
- **Fine-Tuning Configuration**: A specific combination of PEFT method (QLoRA/LoRA), quantization (NF4/FP16), batch size, gradient checkpointing, and sequence length that determines total VRAM consumption.

---

## Success Criteria

- [ ] **Model catalog**: ≥5 models documented with benchmarks, VRAM, and sources.
- [ ] **Dataset catalog**: ≥5 datasets documented with size, format, license, and sources.
- [ ] **Decision matrix**: Each model+dataset option mapped to VRAM budget.
- [ ] **Final recommendation**: One model and one dataset recommended with justification.

---

## Testing Plan

### Research Validation

- All benchmark numbers cross-referenced against official model cards / papers.
- VRAM estimates validated against community reports (Reddit, HuggingFace discussion, Unsloth benchmarks).
- Dataset statistics verified against HuggingFace dataset viewer.

---

## Status Tracker

| Item | Status | Notes |
|------|--------|-------|
| Model catalog | TODO | Collect from references + external sources |
| Dataset catalog | TODO | Collect from references + HuggingFace search |
| VRAM analysis | TODO | Map each combo to GB estimate |
| Recommendation | TODO | Synthesize findings |

---

## Open Questions

1. **Should VL (vision-language) models be included separately?**
   - Computer-use agents typically need multimodal input (screenshots). Need to decide if spec covers VL models or just text-only LLMs.
   - **Status**: Open — answer depends on whether TINYCUA pipeline processes screenshots directly or via an external vision encoder.

2. **Are proprietary API-based models (GPT-4o, Claude) in scope?**
   - Thesis defense may want to compare against baselines.
   - **Status**: Discussion — likely out of scope for fine-tuning but useful as baselines.

---

## Review Checklist

- [ ] No implementation details
- [ ] All mandatory sections completed
- [ ] No `[NEEDS CLARIFICATION]` markers remain
- [ ] Requirements are testable and unambiguous
- [ ] Scope is clearly bounded with explicit non-goals
- [ ] Success criteria are measurable
