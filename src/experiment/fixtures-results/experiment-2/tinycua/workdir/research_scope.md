# Research Scope: Frontier LLM Report

## Research Boundaries and Requirements

### Required Document Structure

The report must use exactly these H2 chapters in specified order:

1. **Scope** - Define research boundaries, methodology, and limitations
2. **Models** - Compare at least 3 named model families with capability analysis
3. **Evidence** - Collect and verify source URLs (minimum 3 distinct sources)
4. **Benchmark Interpretation** - Explain evaluation dependencies
5. **Conclusion** - Synthesize findings without declaring a winner

### Hard Constraints

#### Format Requirements
- Table header must be exactly: `| Model | Provider | Evidence |`
- Every heading must be unique (no duplicate H2 headings)
- May add useful H2 chapters after required ones, but maintain exact order of required chapters

#### Content Requirements
- **Model Families**: Compare at least 3 named model families
- **Source Citations**: Minimum 3 distinct source URLs required
- **Evaluation Dimensions** (all 6 must be covered):
  - Capability
  - Cost
  - Latency
  - Context length
  - Safety
  - Evaluation limits

#### Benchmark Dependency Explanations Required
The report must explain how benchmarks depend on:
1. **Task** - Task type and complexity affect results
2. **Prompting** - Quality of prompts influences benchmark scores
3. **Tools** - Tool usage capabilities impact performance
4. **Reproducibility** - Need for consistent evaluation conditions
5. **Contamination** - Data leakage risks in evaluation

#### Citation Requirements
- Must cite at least 3 distinct source URLs
- Sources must be cited rather than claiming a single "best" model
- Explain why sources support conclusions

### Required Workspace Files

The following files must exist in the workspace:
- `TASK.md` - Contains acceptance criteria and immutable instructions
- `.agent_scripts/` - Directory containing search utilities
  - `search.sh` - Shell script for web searching via SearXNG
  - `README.md` - Documentation for agent scripts

### Verification Criteria

| Section | Verification Criteria |
|---------|----------------------|
| Scope | Documents research boundaries, methodology, and file requirements |
| Models | Contains Markdown table with exact header `Model | Provider | Evidence`; compares ≥3 model families; covers all 6 dimensions |
| Evidence | Documents at least 3 distinct source URLs with verification |
| Benchmark Interpretation | Explains all 5 benchmark dependencies (task, prompting, tools, reproducibility, contamination) |
| Conclusion | Synthesizes findings without declaring single "best" model; cites sources to support conclusions |

### Research Methodology

1. **Model Selection**: Identify at least 3 distinct model families from leading providers
2. **Evidence Collection**: Gather source URLs from reputable sources (Hugging Face, official blogs, technical papers)
3. **Benchmark Analysis**: Review evaluations from multiple sources to avoid single-source bias
4. **Cross-Reference**: Verify claims against multiple independent sources

### Limitations

- Evaluation results vary by benchmark suite and evaluation protocol
- Results depend on specific task types and prompting strategies
- Context length capabilities may vary across model versions
- Safety evaluations depend on test sets and evaluation methodology
