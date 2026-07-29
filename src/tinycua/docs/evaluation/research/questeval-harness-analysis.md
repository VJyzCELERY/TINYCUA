# QuestEval-Inspired Evaluation Harness Without LLM Judge

## Paper Summary

**QuestEval** (Scialom et al., EMNLP 2021) proposes a reference-less summarization evaluation metric using Question Generation (QG) and Question Answering (QA) models. It achieves higher correlation with human judgments than ROUGE/BERTScore without requiring ground-truth summaries.

## Core Idea

Instead of comparing output to a reference (ROUGE) or asking an LLM to judge quality, QuestEval:

1. **Generates questions** from the source document and/or summary
2. **Answers questions** using a QA model on both source and summary
3. **Compares answers** to measure factual consistency and relevance

```
Source Document → QG → Questions → QA(Source, Q) → Answer_source
                                                              ↓ compare (F1/answerability)
Summary         → QG → Questions → QA(Summary, Q) → Answer_summary
```

## Key Components

### 1. Precision (Factual Consistency)
- Generate questions from the **summary**
- Answer each question from both **source** and **summary**
- Score = F1 between answers
- High score = summary facts are supported by source

### 2. Recall (Relevance)
- Generate questions from the **source document**
- Check if summary can answer them
- Score = fraction of questions answerable from summary
- High score = summary captures important source information

### 3. Question Weighter (W)
- Learned classifier to distinguish important vs anecdotal questions
- Trained on human summaries: questions whose answers appear in gold summaries = important
- Improves Relevance correlation (+4%)

### 4. Final Score
- Harmonic mean of Precision and Recall (F-score)
- Range: [0, 1], directly comparable with ROUGE

## Results from Paper

| Metric | Consistency | Coherence | Fluency | Relevance | Average |
|--------|-------------|-----------|---------|-----------|---------|
| ROUGE-1 (11 refs) | 18.1 | 20.1 | 14.9 | 35.6 | 22.2 |
| BERTScore (11 refs) | 20.3 | 18.5 | 21.6 | 31.9 | 23.1 |
| ROUGE-1 (1 ref) | 11.0 | 9.8 | 7.5 | 18.9 | 11.8 |
| **QuestEval (0 refs)** | **42.0** | **24.0** | **28.4** | **39.2** | **33.5** |

QuestEval with **zero references** outperforms all baselines with 11 references.

## Application to TinyCUA Research Evaluation Harness

### Why This Fits

1. **No LLM Judge**: Uses local QA/QG models (T5-based), no API calls needed
2. **No Reference Summaries**: Works without gold-standard outputs
3. **Measures Hallucination**: Precision component directly detects factual inconsistency
4. **Measures Completeness**: Recall component measures information coverage
5. **Quantitative**: Produces numeric scores, not subjective ratings

### Implementation Architecture

```
┌─────────────────────────────────────────────────────────┐
│                  Research Evaluation Harness             │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Input:                                                 │
│    - Source document/context                            │
│    - Agent output (summary/analysis)                    │
│                                                         │
│  Components:                                            │
│    ┌─────────────┐    ┌─────────────┐                   │
│    │  QG Model   │    │  QA Model   │                   │
│    │  (T5-based) │    │  (T5-based) │                   │
│    └──────┬──────┘    └──────┬──────┘                   │
│           │                  │                          │
│           ▼                  ▼                          │
│    ┌─────────────────────────────────┐                  │
│    │      Question Generator         │                  │
│    │  - From source (for recall)     │                  │
│    │  - From summary (for precision) │                  │
│    └──────────────┬──────────────────┘                  │
│                   │                                     │
│                   ▼                                     │
│    ┌─────────────────────────────────┐                  │
│    │      Answer Comparator         │                  │
│    │  - F1 score (precision)        │                  │
│    │  - Answerability (recall)      │                  │
│    └──────────────┬──────────────────┘                  │
│                   │                                     │
│                   ▼                                     │
│    ┌─────────────────────────────────┐                  │
│    │      Weighted Scorer           │                  │
│    │  - Question importance weights │                  │
│    │  - Harmonic mean (F-score)     │                  │
│    └─────────────────────────────────┘                  │
│                                                         │
│  Output:                                                │
│    - precision_score (factual consistency)              │
│    - recall_score (information coverage)                │
│    - questeval_score (harmonic mean)                    │
│    - hallucination_count (questions with wrong answers) │
│    - question_details (for debugging)                   │
└─────────────────────────────────────────────────────────┘
```

### Metrics for TinyCUA Research Tasks

| Metric | Source | Measures |
|--------|--------|----------|
| `factual_consistency` | QuestEval Precision | Hallucination rate |
| `information_coverage` | QuestEval Recall | Completeness |
| `questeval_score` | F(Precision, Recall) | Overall quality |
| `hallucination_count` | Wrong answers in precision | Specific errors |
| `tool_efficiency` | Cache hits / total calls | Resource usage |
| `latency` | End-to-end time | Performance |

### Integration Points

1. **Extend `SmokeResult`**: Add `research_score`, `factual_consistency`, `hallucination_count`
2. **Extend `SmokeReport`**: Add per-category research metrics aggregation
3. **New CLI command**: `tinycua evaluate-research` for standalone research evaluation
4. **Harness integration**: Auto-detect research tasks, apply QuestEval scoring

### Model Requirements

- **QA Model**: T5-small (77M params) or T5-base (220M params)
- **QG Model**: Same T5 fine-tuned on SQuAD for question generation
- **Hardware**: CPU inference OK for small models, GPU recommended for scale
- **No external API**: Fully local execution

### Potential Challenges

1. **Domain specificity**: SQuAD-trained models may struggle with technical/domain-specific content
2. **Question quality**: Generated questions may not capture all important aspects
3. **Answer matching**: F1 may miss semantic equivalence (e.g., "ACL" vs "Association for Computational Linguistics")
4. **Weight transfer**: Question weighter trained on CNN/DM may not generalize

### Mitigation Strategies

1. **Domain adaptation**: Fine-tune QA/QG on domain-specific QA datasets
2. **Question filtering**: Use answerability confidence to filter low-quality questions
3. **Semantic matching**: Augment F1 with embedding-based similarity
4. **Weight calibration**: Train question weighter on TinyCUA-specific data

## Open Research Questions

1. Can we use a single model for both QG and QA (multi-task T5)?
2. How to handle multi-document research tasks?
3. Should we weight questions by source reliability (e.g., peer-reviewed vs blog)?
4. Can we combine QuestEval with embedding-based metrics for better semantic matching?

## References

- Scialom et al. (2021). QuestEval: Summarization Asks for Fact-based Evaluation. EMNLP.
- Wang et al. (2020). QAGS: Factual Consistency Evaluation via QA.
- Fabbri et al. (2020). SummEval: Revisiting Summarization Evaluation.
