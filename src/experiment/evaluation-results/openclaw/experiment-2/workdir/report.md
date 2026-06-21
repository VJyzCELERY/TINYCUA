# Frontier Large Language Models Report
**Date:** June 21, 2026  
**Sources:** Vellum AI Leaderboard, ClickRank.ai, Artificial Analysis, LMSYS Chatbot Arena

---

## Executive Summary

The current frontier of large language models (LLMs) in mid-2026 is characterized by:

1. **No single model dominates all tasks** - Different leaders excel at different benchmarks
2. **Benchmark saturation has intensified** - Traditional metrics like MMLU are no longer useful for differentiation; harder tests like GPQA Diamond, Humanity's Last Exam, and SWE-Bench Verified now separate top models
3. **The gap between rank 1 and rank 8 is small** - Arena Elo scores cluster between 1,450-1,561 for frontier models
4. **Open-source has closed the gap significantly** - DeepSeek V3.2 and Qwen 3.5 compete with proprietary models at a fraction of the cost

---

## Top Models by Category

### 🧠 Reasoning & Intelligence (GPQA Diamond)
| Rank | Model | Score |
|------|-------|-------|
| 1 | **Claude Mythos Preview** | 94.6% |
| 2 | Claude Fable 5 / Claude Opus 4.7/4.8 | ~93-94% |
| 3 | GPT-5 | 90%+ |

### 📐 Math (AIME 2026)
| Rank | Model | Score |
|------|-------|-------|
| 1 | **GPT-5** | 100% (Perfect) |
| 2 | Gemini 3.1 Pro / GPT-5.2 | ~95-100% |
| 3 | Claude Opus 4.6 | ~85% |

### 💻 Coding (SWE-Bench Verified)
| Rank | Model | Score |
|------|-------|-------|
| 1 | **Claude Opus 4.5** | 80.9% |
| 2 | GPT-5 / Grok 4 | ~76-78% |
| 3 | DeepSeek V3.2 (Open) | ~72% |

### 🎯 Overall Intelligence (Humanity's Last Exam)
| Rank | Model | Score |
|------|-------|-------|
| 1 | **Claude Mythos Preview** | 64.7% |
| 2 | Claude Opus 4.8 | ~57-58% |
| 3 | Gemini 3 Pro / GPT-5.5 Pro | ~44-45% |

### 👁️ Visual Reasoning (ARC-AGI 2)
| Rank | Model | Score |
|------|-------|-------|
| 1 | **GPT-5.5** | 85% |
| 2 | Claude Opus 4.6 | ~59-69% |

### 🌐 Multilingual Reasoning (MMMLU)
| Rank | Model | Score |
|------|-------|-------|
| 1 | **Gemini 3 Pro** | 91.8% |
| 2 | Claude Opus 4.6/4.5 | ~90-91% |

---

## Speed & Latency Leaders

### ⚡ Fastest Output (Tokens/sec)
| Rank | Model | Speed |
|------|-------|-------|
| 1 | **Llama 4 Scout** | 2,600 t/s |
| 2 | Llama 3.3 70b | 2,500 t/s |
| 3 | Llama 3.1 70b | 2,100 t/s |

### ⏱️ Lowest Latency (TTFT - Time to First Token)
| Rank | Model | TTFT |
|------|-------|-------|
| 1 | **GPT-5.3 Codex** | 0.003s |
| 2 | Nova Micro / Llama 4 Scout | ~0.3s |

---

## 💰 Cost Leaders (per 1M tokens)

### Cheapest Models
| Rank | Model | Input/Output Cost |
|------|-------|------------------|
| 1 | **Qwen3.5 0.8B** | $0.02 / $0.07 |
| 2 | Nova Micro | $0.04 / $0.14 |
| 3 | Gemma 3 27b/3n E4B | $0.07 / $0.07 |

### Most Expensive (Frontier)
| Rank | Model | Input/Output Cost |
|------|-------|------------------|
| 1 | **GPT-5.5 Pro** | $30 / $180 |
| 2 | GPT-4.5 | $75 / $150 |
| 3 | Claude Opus 4.6/4.7 | $5 / $25 |

---

## 🏆 Arena Elo Rankings (Human Preference)

Frontier models cluster between **Elo 1,450-1,561**:

| Rank | Model | Arena Elo |
|------|-------|-----------|
| 1 | **GPT-5** | ~1,561 |
| 2-3 | Claude Mythos Preview / Fable 5 | ~1,480-1,520 |
| 4+ | Gemini 3 Pro, Grok 4.2, DeepSeek V3.2 | ~1,450-1,490 |

---

## Key Benchmark Explanations

- **GPQA Diamond** - Graduate-level science questions (physics, chemistry, biology). Tests advanced reasoning.
- **Humanity's Last Exam** - 3,000+ expert-level questions across all academic disciplines. The "final exam" before superhuman AI.
- **SWE-Bench Verified** - Real GitHub issues that models must fix with working code + automated unit tests.
- **AIME 2026** - American Invitational Mathematics Examination (Olympiad level).
- **ARC-AGI 2** - Abstract visual puzzles requiring novel pattern recognition and fluid intelligence.
- **MMMLU** - Massive Multitask Language Understanding across multiple languages.

---

## Important Trends in 2026

### Benchmark Saturation
Traditional benchmarks like MMLU are now useless for differentiation:
- Frontier models score 90%+ on all top-tier benchmarks
- Harder tests (GPQA Diamond, Humanity's Last Exam) now separate elite models
- Automated unit-test grading makes SWE-Bench results more reproducible than "LLM-as-a-judge" evaluations

### The Cost-Quality Tradeoff
| Tier | Models | Price Range |
|------|--------|-------------|
| Budget AI | Qwen3.5 0.8B, Nova Micro | $0.02-0.14 / M tokens |
| Mid-tier Open | DeepSeek V3.2, Llama 4 Scout | $0.11-0.60 / M tokens |
| Frontier Proprietary | GPT-5, Claude Opus, Gemini 3 Pro | $2-75+ / M tokens |

### Context Window Arms Race
- **Llama 4 Scout**: 10M token context (fastest, cheapest)
- **Claude Mythos Preview/Fable 5**: 1M token context
- **Grok 4.2**: 2M token context for long documents
- **Gemini 3 Pro/Pro Max**: 10M+ token context

---

## Recommendations by Use Case

### For Enterprise Production:
**Claude Opus 4.6 / Claude Mythos Preview** - Best balance of reasoning, coding ability, and reliability with 1M-2M context.

### For Math-heavy Tasks:
**GPT-5** - Perfect AIME score + highest Arena Elo for overall preference.

### For Coding Projects:
**Claude Opus 4.5** leads SWE-Bench; **DeepSeek V3.2** offers open-source alternative at 1/10th the cost.

### For Speed-critical Applications:
**Llama 4 Scout** (2,600 t/s) or **GPT-5.3 Codex** (0.003s TTFT).

### For Budget-conscious AI Ops:
**Qwen3.5 0.8B** at $0.02/M tokens - cheapest ranked model in 2026.

---

## Data Sources & Methodology

This report aggregates data from:
- **Vellum.ai Leaderboard** - Task-specific benchmark comparisons (June 2026)
- **ClickRank.ai LLM Leaderboard** - Human preference + pricing analysis (May-June 2026)
- **Artificial Analysis** - Composite intelligence index across 356 models
- **LMSYS Chatbot Arena** - Crowdsourced Elo ratings from 1M+ blind A/B battles

*Note: All data reflects the state as of June 21, 2026. New models typically appear on leaderboards within 24-48 hours of release.*