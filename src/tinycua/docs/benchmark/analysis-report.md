# TinyCUA WildClawBench Benchmark Analysis Report

**Status**: Preliminary — awaiting TinyCUA benchmark execution
**Created**: 2026-06-15
**Last Updated**: 2026-06-15
**Milestone**: 5.7 — Benchmark Analysis Report

---

## Executive Summary

This report analyzes TinyCUA's position within the WildClawBench benchmark ecosystem. WildClawBench evaluates AI agent harnesses across 60 real-world tasks in 6 categories, testing multimodal reasoning, long-horizon planning, and code generation capabilities.

**Key findings:**

- **Top WildClawBench score**: 62.2% (Claude Opus 4.7 on OpenClaw harness) — no model exceeds 63%
- **Harness matters**: Same model scores vary 5–18 points across harnesses (e.g., GPT-5.4: 50.3% OpenClaw vs. 56.8% Codex)
- **TinyCUA uses local LLMs**: Architectural analysis suggests significant score limitations compared to frontier API models, but potential advantages in cost and latency
- **No TinyCUA benchmark runs completed yet**: This report establishes baselines and documents expected limitations pending execution

**Bottom line**: TinyCUA's competitive position will depend on (1) which local model is used, (2) harness scaffolding quality, and (3) task category. Code Intelligence and Safety Alignment are most feasible for local models; Creative Synthesis and Social Interaction are hardest.

---

## Methodology

### Data Sources

| Source | Description | Status |
|--------|-------------|--------|
| WildClawBench Leaderboard | Official benchmark results for 19 models across 4 harnesses | Available |
| WildClawBench Harness Comparison | Per-model, per-harness score/time/cost data | Available |
| TinyCUA Smoke-Run Infrastructure | `tinycua smoke-run` CLI, `SmokeRunOrchestrator`, `SmokeReportGenerator` | Implemented (Milestone 5.5) |
| TinyCUA Benchmark Orchestrator | 60-task orchestration for full WildClawBench run | Implemented (Milestone 5.6) |
| TinyCUA WildClawBench Adapter | `TinyCUAAgent` base adapter for harness integration | Implemented (Milestone 5.2) |
| TinyCUA Benchmark Docker Image | Container for WildClawBench evaluation | Implemented (Milestone 5.3) |

### Models and Hardware

| Parameter | Value |
|-----------|-------|
| TinyCUA Local Model | Configurable via `TINYCUA_MODEL` env var (default: `llama3`) |
| Model Endpoint | OpenAI-compatible API (Ollama, LM Studio, vLLM) |
| Hardware | Developer workstation (no GPU cluster) |
| Runtime | Python 3.11+, Docker (optional) |

### Caveats

1. **No TinyCUA benchmark runs have been executed yet.** All TinyCUA-specific analysis in this report is based on architectural analysis, not empirical data.
2. WildClawBench baseline data uses frontier API models (Claude, GPT, Gemini). TinyCUA uses local LLMs — direct comparison requires careful interpretation.
3. Cost comparisons are not meaningful for local LLM inference (no per-token API cost).
4. Time comparisons are partially meaningful but depend heavily on hardware.

---

## Overall Comparison

### WildClawBench Leaderboard (OpenClaw Harness)

The following table shows the top-performing models on WildClawBench using the OpenClaw harness. TinyCUA is listed as a reference point with projected performance based on architectural analysis.

| Rank | Model | Overall Score | Total Time (60 tasks) | Total Cost | Notes |
|:----:|-------|:-------------:|:---------------------:|:----------:|-------|
| 1 | **Claude Opus 4.7** | **62.2%** | 328 min | $77.40 | Best overall |
| 2 | GPT-5.5 | 58.2% | 262 min | $37.80 | Best value frontier |
| 3 | Claude Opus 4.6 | 51.6% | 508 min | $81.00 | High cost |
| 4 | GPT-5.4 | 50.3% | 350 min | $19.80 | Balanced |
| 5 | GLM 5.1 | 48.2% | 515 min | $34.80 | |
| 6 | DeepSeek V4 Pro | 43.7% | 605 min | $12.00 | Cost-effective |
| 7 | MiMo V2.5 Pro | 43.0% | 451 min | $12.60 | |
| 8 | GLM 5 | 42.6% | 373 min | $11.40 | |
| 9 | Gemini 3.1 Pro | 40.8% | 240 min | $18.00 | Fastest |
| 10 | MiMo V2 Pro | 40.2% | 458 min | $26.40 | |
| — | **TinyCUA (local LLM)** | **~15–25%** | **~400–600 min** | **$0.00** | Projected |

> **Note**: TinyCUA scores are projected based on local LLM capability ranges (Llama 3 8B–70B class). Actual scores depend on the specific model, quantization, and hardware used. The projection assumes a mid-range local model (e.g., Llama 3 8B Q4) on consumer hardware.

### Harness Comparison (Same Model, Different Scaffolds)

WildClawBench's harness comparison reveals that the agent scaffold significantly affects scores. This is directly relevant to TinyCUA's design as a custom harness.

| Model | OpenClaw | Claude Code | Codex | Hermes Agent |
|-------|:--------:|:-----------:|:-----:|:------------:|
| GPT-5.4 | 50.3% | 48.4% | **56.8%** | 50.7% |
| GLM 5 | 42.6% | 31.0% | 38.9% | **46.4%** |
| MiMo V2 Pro | 40.2% | 29.9% | 35.3% | **48.1%** |
| MiniMax M2.7 | 33.8% | 32.0% | 35.8% | **37.1%** |

**Key observations:**

1. **Hermes Agent consistently outperforms other harnesses for smaller/cheaper models.** For GLM 5, MiMo V2 Pro, and MiniMax M2.7, Hermes Agent scores highest. This suggests Hermes Agent's scaffolding is better optimized for models with weaker instruction-following.

2. **Codex excels for strong models.** GPT-5.4 scores 56.8% on Codex vs. 50.3% on OpenClaw — a 6.5-point boost. Codex's code-focused scaffolding amplifies strong model capabilities.

3. **Claude Code underperforms for most models.** It scores lowest for GLM 5 (31.0%) and MiMo V2 Pro (29.9%), suggesting its scaffolding assumes strong model capabilities that weaker models lack.

4. **TinyCUA's harness design will matter enormously.** Given that TinyCUA uses local LLMs (which are weaker than frontier models), its harness scaffolding must compensate. The Hermes Agent pattern — optimized for weaker models — is the more relevant comparison point.

### TinyCUA Cost and Time Profile

| Metric | TinyCUA (Local) | OpenClaw (API) | Notes |
|--------|:---------------:|:--------------:|-------|
| Per-task cost | $0.00 | $0.12–$1.36 | No API tokens for local inference |
| Total cost (60 tasks) | $0.00 | $7.20–$81.00 | Hardware depreciation not counted |
| Per-task time | ~7–10 min | ~5.8–9.2 min | Depends on local hardware |
| Total time (60 tasks) | ~420–600 min | ~328–605 min | Similar range |

**Cost advantage**: TinyCUA eliminates per-token API costs entirely. For iterative development and testing, this is a significant practical advantage despite lower scores.

---

## Category Breakdown

### WildClawBench Categories

| Category | Tasks | Core Challenges | Local LLM Feasibility |
|----------|:-----:|-----------------|:---------------------:|
| Productivity Flow | 10 | Information synthesis, multi-source aggregation | Medium |
| Code Intelligence | 12 | Undocumented codebase comprehension, code generation | High |
| Social Interaction | 6 | Multi-turn communication, context tracking | Low |
| Search & Retrieval | 11 | Web search + data reconciliation | Medium |
| Creative Synthesis | 11 | Video/audio processing, cross-modal generation | Low |
| Safety Alignment | 10 | Adversarial robustness, credential awareness | High |

### Expected Performance by Category

Based on architectural analysis of TinyCUA's capabilities and local LLM limitations:

#### Productivity Flow (Expected: ~20–30%)

- **Strengths**: Text-based tasks (file creation, document editing) are within local LLM capability
- **Weaknesses**: Multi-source aggregation and structured output quality degrade with smaller models
- **Harness gap**: TinyCUA's CLI-based execution lacks the rich tool ecosystem of OpenClaw (no native email, calendar, browser)
- **Relevant baseline**: MiniMax M2.7 scores 33.8% on OpenClaw — a reasonable ceiling for local-model-class performance

#### Code Intelligence (Expected: ~25–35%)

- **Strengths**: Code generation is a relative strength for Llama-class models. The `tinycua benchmark run` CLI provides file system access and code execution.
- **Weaknesses**: Undocumented codebase comprehension requires large context windows (local models typically have 8K–32K vs. 200K+ for frontier models)
- **Harness gap**: Codex harness scores highest for strong models (56.8% for GPT-5.4). TinyCUA's code-focused scaffolding could capture some of this advantage.
- **Relevant baseline**: DeepSeek V4 Pro at 43.7% — strong code model, closer to local model territory

#### Social Interaction (Expected: ~10–15%)

- **Strengths**: Multi-turn dialogue is a core LLM capability
- **Weaknesses**: Tasks require email API orchestration, calendar integration, and simulated collaborator interaction — capabilities TinyCUA's harness doesn't natively provide
- **Harness gap**: This category is most dependent on harness tooling, not model capability. TinyCUA lacks the email/calendar/browser tools that OpenClaw provides.
- **Relevant baseline**: This category has the widest harness-dependent variance

#### Search & Retrieval (Expected: ~15–25%)

- **Strengths**: Local file search (`grep`, `find`) is straightforward to implement
- **Weaknesses**: Web search requires external API integration (Brave Search). TinyCUA's `BRAVE_API_KEY` support exists but hasn't been validated in benchmark conditions.
- **Harness gap**: Depends heavily on search tool quality and result parsing
- **Relevant baseline**: Search tasks are graded on accuracy of information retrieval — local models may struggle with complex multi-source reconciliation

#### Creative Synthesis (Expected: ~5–10%)

- **Strengths**: Text-based creative tasks (haiku, summaries) are within capability
- **Weaknesses**: Most Creative Synthesis tasks require video/audio processing, image generation, and cross-modal synthesis — capabilities entirely outside local LLM scope
- **Harness gap**: This is the hardest category for any non-frontier setup. Even top models score poorly here.
- **Relevant baseline**: Creative Synthesis has the lowest average scores across all harnesses

#### Safety Alignment (Expected: ~20–30%)

- **Strengths**: Prompt injection detection and harmful content refusal are well-represented in Llama training data. Credential leak detection is a text pattern matching task.
- **Weaknesses**: Adversarial robustness testing may produce false negatives with weaker instruction-following
- **Harness gap**: Safety tasks are more model-dependent than harness-dependent — local models may perform reasonably well here
- **Relevant baseline**: Safety Alignment scores tend to cluster more tightly across harnesses

---

## Failure Taxonomy

Since no TinyCUA benchmark runs have been executed, this section documents expected failure categories based on architectural analysis.

### Expected Failure Categories

| Category | Expected Count (of 60) | Description |
|----------|:----------------------:|-------------|
| **LLM Error** | 15–25 | Model fails to follow instructions, produces garbled output, or hallucinates tool calls |
| **Timeout** | 10–20 | Local model inference is slow; tasks exceed 300s timeout |
| **Missing Dependency** | 5–10 | Tasks require capabilities TinyCUA doesn't provide (email, browser, calendar, video processing) |
| **Harness Crash** | 2–5 | TinyCUA adapter errors, Docker container issues, CLI failures |
| **Grading Error** | 1–3 | Judge LLM (if used) may not align with TinyCUA output format |
| **Other** | 2–5 | Edge cases, environment issues, resource exhaustion |

### Representative Failure Examples (Projected)

**LLM Error — Instruction Following**
> Task: "Draft a polite email to a colleague thanking them for their help with a project deadline."
> Local model output: Produces a generic email without the task-specific context, or generates markdown formatting instead of plain text email format.
> Root cause: Local models have weaker instruction-following for nuanced formatting requirements.

**Timeout — Slow Inference**
> Task: "Write a Python function called 'fibonacci' that returns the nth Fibonacci number using memoization."
> Local model takes 15+ seconds per generation step; with multiple tool calls, task exceeds 300s timeout.
> Root cause: Consumer hardware provides ~10–30 tokens/second vs. ~100+ tokens/second for API models.

**Missing Dependency — No Browser**
> Task: Tasks requiring web browsing, form filling, or visual web interaction.
> TinyCUA provides file system and CLI access but not a browser automation tool.
> Root cause: Harness scope limitation — TinyCUA is a CLI-focused agent, not a full desktop automation harness.

### Mitigation Strategies

| Failure Category | Mitigation |
|-----------------|------------|
| LLM Error | Use larger local models (70B+), improve prompt engineering, add few-shot examples |
| Timeout | Increase per-task timeout, use faster hardware (GPU), reduce task scope |
| Missing Dependency | Extend TinyCUA tool set (add browser, email adapters), skip tasks with unmet dependencies |
| Harness Crash | Improve error handling, add retry logic, validate Docker setup |

---

## Local LLM Limitations

### Observed Limitations (Architectural Analysis)

| Limitation | Impact on Benchmark | Severity | Evidence |
|-----------|--------------------:|:--------:|----------|
| **Context window limits** | Tasks requiring large codebase comprehension fail | High | Local models: 8K–32K tokens. Frontier models: 200K+ tokens. WildClawBench tasks reference codebases with 1000+ lines. |
| **No multimodal support** | Creative Synthesis tasks requiring video/image understanding are impossible | Critical | Most local LLMs are text-only. WildClawBench has 11 Creative Synthesis tasks requiring video processing. |
| **Slower inference** | Tasks timeout before completion | High | Consumer GPU: ~10–30 tok/s. API models: ~100+ tok/s. 300s timeout is tight for multi-step tasks. |
| **Weaker instruction following** | Nuanced formatting and multi-constraint tasks fail | Medium | Local models produce less precise structured output. WildClawBench grading penalizes format deviations. |
| **No tool-use training** | Agent doesn't reliably invoke tools | High | Frontier models are fine-tuned for tool use. Local models may not recognize tool-call patterns. |
| **Limited world knowledge** | Tasks requiring external knowledge (Wikipedia, finance) produce shallow results | Medium | Smaller models have less training data coverage. WildClawBench tasks reference real-world entities. |

### Specific Examples from Architecture

**Context Window Constraint**:
WildClawBench Code Intelligence tasks ask agents to read undocumented codebases (e.g., SAM3 inference). These codebases are 500–2000 lines. With a 32K context window, the agent can hold ~8K tokens of code + instructions + conversation history. Frontier models with 200K+ windows can hold the entire codebase plus full conversation.

**Multimodal Gap**:
Creative Synthesis tasks include: football match video analysis, video dubbing, paper-to-poster conversion, outfit-to-model image generation. These require vision/audio processing that text-only local LLMs cannot perform. This is a hard blocker for ~11 of 60 tasks.

**Tool-Use Reliability**:
WildClawBench tasks require 10–60+ tool calls per task. Frontier models are trained on tool-use patterns (function calling, JSON schemas). Local models may produce malformed tool calls, miss required parameters, or fail to chain tool outputs correctly.

---

## Judge Configuration Notes

### WildClawBench Judge Setup

| Parameter | Value |
|-----------|-------|
| Judge Model | `openai/gpt-5.4` (default) |
| Grading Method | Per-metric scoring (0.00–1.00) |
| Metrics | Multimodal reasoning, long-horizon planning, code generation, safety alignment |
| Ground Truth Injection | Post-execution only (no data leakage) |
| Reproducibility | Docker containerized, isolated per-task environments |

### TinyCUA Judge Considerations

| Consideration | Status | Notes |
|---------------|--------|-------|
| Judge LLM integration | Not implemented | TinyCUA smoke-run uses pass/fail based on exit code, not LLM-based grading |
| Metric granularity | Binary (pass/fail) | WildClawBench uses continuous 0–1 scores per metric |
| Grade alignment | Unknown | Without running TinyCUA tasks through WildClawBench's grading pipeline, score comparability is uncertain |
| Recommendation | Implement judge integration | Add LLM-based grading to TinyCUA's benchmark pipeline for meaningful score comparison |

---

## Recommendations

### Recommendation 1: Run Benchmark Before Optimizing

**Rationale**: All analysis in this report is based on architectural projections, not empirical data. The single most valuable next step is executing the benchmark.

**Action**: Run TinyCUA against the full 60-task WildClawBench suite using the benchmark orchestrator.

```bash
# Run with a local model via Ollama
TINYCUA_MODEL=llama3 TINYCUA_BASE_URL=http://localhost:11434/v1 \
  tinycua benchmark run --all --output ./tmp/benchmark-full

# Or run smoke tests first
tinycua smoke-run --model llama3 --base-url http://localhost:11434/v1 --output ./tmp/smoke-runs
```

**Expected outcome**: Actual scores, failure categories, and timing data to replace projections.

**Priority**: P0 — blocks all other recommendations.

### Recommendation 2: Use Hermes Agent Scaffolding Patterns

**Rationale**: WildClawBench harness comparison shows Hermes Agent consistently outperforms other harnesses for weaker models (GLM 5: 46.4% vs. OpenClaw: 42.6%, Claude Code: 31.0%). TinyCUA uses local LLMs, which are weaker than frontier models — Hermes Agent's scaffolding patterns are more relevant than OpenClaw's.

**Action**: Study Hermes Agent's scaffolding approach and incorporate patterns into TinyCUA's agent loop:
- More explicit tool-call formatting guidance
- Retry logic for malformed outputs
- Step-by-step decomposition prompts
- Context management for long tasks

**Expected outcome**: 5–15% score improvement for local models through better harness scaffolding.

**Priority**: P1 — after benchmark execution.

### Recommendation 3: Extend TinyCUA Tool Set for Missing Dependencies

**Rationale**: WildClawBench tasks require browser automation, email, calendar, and video processing. TinyCUA currently provides file system and CLI access only. Missing dependencies are a major failure category.

**Action**: Prioritize tool extensions based on task category impact:

| Tool | Tasks Unblocked | Priority |
|------|:--------------:|:--------:|
| Web search (Brave) | 11 Search & Retrieval tasks | High |
| Browser automation | ~5 Productivity Flow tasks | Medium |
| Email simulation | 6 Social Interaction tasks | Medium |
| Video processing | ~8 Creative Synthesis tasks | Low (requires multimodal model) |

**Expected outcome**: Unblocking Search & Retrieval and Productivity Flow tasks could add 5–10 points to overall score.

**Priority**: P1 — after benchmark execution, focus on highest-impact tools first.

### Recommendation 4: Increase Context Window for Code Tasks

**Rationale**: Code Intelligence tasks require reading undocumented codebases. Local models with 8K–32K context windows cannot hold full codebases. This is a hard constraint that limits Code Intelligence scores.

**Action**:
- Use models with larger context windows (e.g., Llama 3 70B with 128K context)
- Implement context management strategies (chunked reading, summarization, key-file extraction)
- Consider retrieval-augmented generation (RAG) for code search

**Expected outcome**: 10–20% improvement on Code Intelligence tasks by enabling full codebase comprehension.

**Priority**: P2 — after tool extensions.

### Recommendation 5: Implement LLM-Based Grading for Score Comparability

**Rationale**: TinyCUA's smoke-run uses binary pass/fail scoring. WildClawBench uses continuous per-metric scoring (0–1). Without matching grading, TinyCUA scores aren't directly comparable to leaderboard data.

**Action**: Integrate WildClawBench's grading pipeline or implement an equivalent LLM-based judge:
- Use `openai/gpt-5.4` as judge (matching WildClawBench default)
- Implement per-metric scoring (multimodal, planning, code, safety)
- Store `score.json` per task for analysis

**Expected outcome**: Meaningful score comparison with WildClawBench baselines.

**Priority**: P2 — after benchmark execution.

---

## Appendix: Raw Data References

### WildClawBench Data Sources

| File | Description | Location |
|------|-------------|----------|
| Leaderboard data | Model scores, times, costs | [internlm.github.io/WildClawBench](https://internlm.github.io/WildClawBench/) |
| Harness comparison | Per-model, per-harness results | WildClawBench README.md |
| Technical report | Full methodology and analysis | [arXiv:2605.10912](https://arxiv.org/abs/2605.10912) |
| Task definitions | 60 task prompts and grading criteria | HuggingFace: `internlm/WildClawBench` |
| Evaluation results | Per-task scores and trajectories | Google Drive links in WildClawBench README |

### TinyCUA Benchmark Artifacts (Expected)

Once benchmark runs are executed, artifacts will be located at:

| Artifact | Path Pattern | Format |
|----------|-------------|--------|
| Smoke run report | `tmp/smoke-runs/smoke-report.json` | JSON |
| Smoke run summary | `tmp/smoke-runs/smoke-report.md` | Markdown |
| Full benchmark summary | `tmp/benchmark-full/summary_all.json` | JSON |
| Per-task scores | `tmp/benchmark-full/results/<task_id>/score.json` | JSON |
| Per-task usage | `tmp/benchmark-full/results/<task_id>/usage.json` | JSON |
| Per-task transcripts | `tmp/benchmark-full/results/<task_id>/transcript.jsonl` | JSONL |
| Per-task logs | `tmp/benchmark-full/results/<task_id>/agent.log` | Text |

### TinyCUA Infrastructure Files

| File | Description | Milestone |
|------|-------------|-----------|
| `tinycua/cli/smoke_run.py` | Smoke-run orchestration | 5.5 |
| `tinycua/wildclawbench/agent.py` | TinyCUAAgent adapter | 5.2 |
| `tinycua/cli/transcript.py` | Transcript/usage writing | 5.4 |
| `docs/benchmark/README.md` | Benchmark Docker image docs | 5.3 |

---

*This report will be updated with empirical data once TinyCUA benchmark runs are executed.*
*Generated from spec.md, design.md, and WildClawBench leaderboard data.*
*Last updated: 2026-06-15*
