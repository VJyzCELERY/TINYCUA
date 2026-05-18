# Research Task Checklist: Model & Dataset Selection

**Branch**: docs/model-data-researchs
**Goal**: Populate spec/design with research data, produce final recommendation for thesis.
**References**: `src/tinycua-finetune/references/` (6 docs covering models, PEFT, hardware, agents, argumentation)

---

## Phase 1 — Model Catalog Research <!-- id: 1 -->

- [ ] **1.1 Verify Qwen3.5-9B data** — Cross-reference design.md entry against `references/01_models.md` and `references/06_argumentation.md`. Confirm MMLU-Pro 82.5, GPQA 81.7, VRAM ~6GB INT4.
- [ ] **1.2 Verify LLaMA-3-8B data** — Cross-reference against `references/01_models.md`. Confirm VRAM ~8GB INT4, ~70 MMLU-Pro.
- [ ] **1.3 Verify DeepSeek-Coder-9B data** — Cross-reference against `references/01_models.md`. Confirm VRAM ~6GB INT4, code-focused benchmarks.
- [ ] **1.4 Add Mistral-7B-v0.3** — Research and fill in VRAM, benchmarks, context length (not in existing references; external search needed).
- [ ] **1.5 Add Gemma-2-9B** — Research and fill in VRAM, benchmarks, context length (not in existing references; external search needed).
- [ ] **1.6 Add Qwen3-4B** — Research and fill in. Already used in current pipeline but VRAM/benchmark data needed from `references/01_models.md`.
- [ ] **1.7 VRAM comparison table** — Verify all VRAM estimates against `references/05_hardware.md` memory breakdown (Section 6).

## Phase 2 — Dataset Catalog Research <!-- id: 2 -->

- [ ] **2.1 Verify tool-calling-mix** — Confirm sample count, license, format from HuggingFace dataset page. Already in use; note any updates.
- [ ] **2.2 Verify ToolBench** — Research current state (THUDM/ToolBench). Confirm sample count, license, format.
- [ ] **2.3 Verify Glaive FC V2** — Check HuggingFace for latest stats. Confirm CC-BY-NC-4.0 license compatibility.
- [ ] **2.4 Verify OpenHermes-2.5** — Check HuggingFace for latest stats. Confirm tool-call subset availability.
- [ ] **2.5 Verify Magpie-Pro** — Check HuggingFace. Confirm license and format.
- [ ] **2.6 Verify AgentInstruct** — Check THUDM/AgentInstruct. Confirm size and VRAM concern (~14-16GB marginal).
- [ ] **2.7 Tool-call format comparison** — Document data format differences across datasets (OpenAI function-calling vs ReAct vs custom tool format). Reference `references/04_agents.md` Section 7.

## Phase 3 — VRAM & Hardware Analysis <!-- id: 3 -->

- [ ] **3.1 Cross-reference design.md VRAM tables** — Verify all numbers against `references/05_hardware.md`:
  - 4-bit base memory (Section 6: ~5GB for model)
  - QLoRA training memory (Section 6: ~11-12GB total)
  - Gradient checkpointing impact (Section 4)
  - Sequence length scaling (Section 7: max_seq_length 2048)
- [ ] **3.2 Verify PEFT method choice** — Confirm QLoRA is the right choice using `references/02_peft_methods.md` and `references/03_comparison.md`:
  - QLoRA vs LoRA VRAM comparison
  - Quality trade-off (2-3%)
  - Why not VeRA/IA³ (reference `references/06_argumentation.md` Part 2)
- [ ] **3.3 Hardware justification** — Pull ready-to-use statements from `references/06_argumentation.md` Part 6 into design.md.
- [ ] **3.4 Sequence length sensitivity** — Add analysis: what VRAM budget looks like at seq 1024 vs 2048 vs 4096 for each model.

## Phase 4 — Decision Synthesis <!-- id: 4 -->

- [ ] **4.1 Validate final recommendation** — Confirm Qwen3.5-9B + Glaive FC V2 is justified using evidence from all reference docs.
- [ ] **4.2 Add fallback recommendations** — Document Qwen3-4B + tool-calling-mix as low-resource alternative.
- [ ] **4.3 Add comparison against current pipeline** — Note that current pipeline uses Qwen3-4B + tool-calling-mix. Document what upgrading to Qwen3.5-9B + Glaive FC V2 gains (benchmarks, tool quality, context length).
- [ ] **4.4 Write thesis-ready justification** — Pull from `references/06_argumentation.md` to produce 3 ready-to-use statements (model, PEFT, hardware).

## Phase 5 — Documentation & Cleanup <!-- id: 5 -->

- [ ] **5.1 Update design.md** — Fill in any remaining TODO/placeholder fields with verified data.
- [ ] **5.2 Review spec.md** — Ensure success criteria are still accurate and no open questions remain unresolved.
- [ ] **5.3 Final review** — Read both spec.md and design.md top-to-bottom for coherence and completeness.
- [ ] **5.4 Commit** — Once all tasks complete, stage and commit with user permission.

---

## Quick Reference

| Reference File | What It Covers |
|----------------|-----------------|
| `references/01_models.md` | 9B model benchmarks, VRAM, comparison table |
| `references/02_peft_methods.md` | LoRA, QLoRA, DoRA, AdaLoRA, VeRA, IA³ comparison |
| `references/03_comparison.md` | Full fine-tuning vs PEFT, quality/vram trade-off |
| `references/04_agents.md` | Agent frameworks, computer-use datasets, training data format |
| `references/05_hardware.md` | GPU specs, quantization (GPTQ/AWQ/NF4), memory breakdown |
| `references/06_argumentation.md` | Thesis defense statements, ready-to-use justifications |
