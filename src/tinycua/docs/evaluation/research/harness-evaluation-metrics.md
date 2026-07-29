# Optimal Evaluation Metrics for Research Assignment on Harness

## Overview

This document evaluates potential metrics for assessing TinyCUA agent performance on research-oriented tasks within the WildClawBench harness framework. Research tasks include information retrieval, synthesis, fact verification, and source analysis.

## Research Task Taxonomy

Research assignments fall into four subcategories:

1. **Information Retrieval** — Finding specific facts, data points, or references
2. **Synthesis** — Combining multiple sources into coherent output
3. **Verification** — Cross-referencing claims against available sources
4. **Analysis** — Drawing conclusions from gathered information

## Candidate Metrics

### Primary Metrics

| Metric | Definition | Scoring | Applicability |
|--------|-----------|---------|---------------|
| **Accuracy** | Correctness of retrieved/synthesized facts | Binary or graded (0-1) | All research tasks |
| **Completeness** | Coverage of required information | Ratio of found/required items | Retrieval, Verification |
| **Source Quality** | Relevance and reliability of sources cited | Graded (0-1) | All research tasks |
| **Hallucination Rate** | Frequency of fabricated information | 1 - (verified / total claims) | Synthesis, Analysis |

### Secondary Metrics

| Metric | Definition | Scoring | Applicability |
|--------|-----------|---------|---------------|
| **Latency** | Time to complete research task | Seconds | All |
| **Tool Efficiency** | Ratio of useful tool calls to total calls | Useful calls / total calls | Retrieval, Verification |
| **Citation Integrity** | Accuracy of source attribution | Correct attributions / total attributions | All research tasks |
| **Consistency** | Agreement across multiple runs | Inter-run similarity score | All |

### Harness-Specific Metrics

| Metric | Definition | Scoring | Applicability |
|--------|-----------|---------|---------------|
| **Task Completion** | Whether the agent produced a final output | Binary | All |
| **Timeout Compliance** | Completion within harness timeout | Binary | All |
| **Artifact Quality** | Structured output correctness | Graded (0-1) | All |
| **Category Pass Rate** | Pass rate within WildClawBench category | Percentage | All |

## Recommended Scoring Model

For research assignments, a weighted composite score is recommended:

```
Research Score = 0.35 * Accuracy + 0.25 * Completeness + 0.20 * Source Quality + 0.10 * Hallucination Penalty + 0.10 * Tool Efficiency
```

Where:
- **Accuracy**: LLM-as-judge evaluation of factual correctness
- **Completeness**: Checklist-based coverage assessment
- **Source Quality**: Relevance scoring of cited sources
- **Hallucination Penalty**: (1 - hallucination_rate), penalizing fabrication
- **Tool Efficiency**: Ratio of productive tool calls

## Evaluation Methodology

### 1. Ground Truth Comparison
- Maintain gold-standard answers for research tasks
- Use exact match for factual retrieval
- Use semantic similarity for synthesis tasks (threshold: 0.85 cosine)

### 2. LLM-as-Judge
- Use a separate LLM instance to evaluate output quality
- Structured rubric with 1-5 scoring per dimension
- Calibration against human ratings (target: 0.9 Spearman correlation)

### 3. Harness Integration
- Extend `SmokeResult` with research-specific fields
- Add `research_score` and `hallucination_count` to `SmokeReport`
- Per-category aggregation for research task subsets

## Implementation Notes

- **Hallucination detection**: Cross-reference all factual claims against retrieved sources
- **Source quality**: Score based on source relevance (query match) and recency
- **Tool efficiency**: Track `enhanced_context_retrieval` cache hit rate as proxy
- **Consistency**: Run 3 trials per task, report mean and variance

## Open Questions

1. Should synthesis tasks weight source diversity as a separate metric?
2. How to handle tasks requiring external knowledge beyond provided sources?
3. Is inter-run consistency a quality signal or noise indicator?

## References

- WildClawBench evaluation harness: `tinycua/cli/smoke_run.py`
- Context retrieval tool: `tinycua/tools/enhanced_context_retrieval.py`
- Tool scoping: `tinycua/config/tool_scopes.py`
