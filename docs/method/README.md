# Methodology Section — TINYCUA Paper

This directory contains diagrams and formulas for the methodology section.

## Section Structure

### Core Formulas

1. **Context Exposure Optimization** — `formula-1-context-exposure.md`
   - Minimax objective for context distribution
   - Completeness constraint
   - Attention theory relationship

2. **Query Routing Decision Process** — `formula-2-query-routing.md`
   - Two-step LLM decision (analysis → verdict)
   - Route semantics (passthrough/worker/uncertain)
   - Transient context property

3. **Effort-Controlled Task Decomposition** — `formula-3-effort-decomposition.md`
   - Pass limit function $L(e)$
   - Decomposition algorithm
   - Worker route variants

4. **Task Executor ReAct Model** — `formula-4-executor-context.md`
   - ReAct execution loop
   - Context composition
   - Isolation properties

5. **Review Loop with Failure Threshold** — `formula-5-review-threshold.md`
   - Reviewer decision space
   - Failure counter evolution
   - Threshold constraint

6. **Segmented Context Propagation** — `formula-6-context-propagation.md`
   - Session context segmentation
   - Propagation rules
   - Deduplication mechanism

7. **Context Compaction** — `formula-7-compaction.md`
   - Compaction trigger conditions
   - Strategy contract
   - Compaction invariants

8. **NodeQueue Sequential Execution** — `formula-8-nodequeue-execution.md`
   - Queue operations
   - Execution loop
   - Bootstrap invariants

9. **Result Aggregation BFS Traversal** — `formula-9-result-aggregation.md`
   - Guided BFS right-to-left
   - Sufficiency check
   - Consolidation functions

10. **Information Digestion Model** — `formula-10-information-digestion.md`
    - Trigger condition
    - Lazy context access
    - Fallback behavior

11. **Response Synthesis** — `formula-11-response-synthesis.md`
    - Context sufficiency check
    - Suspension model
    - Synthesis algorithm

### Integrated Methodology

**Methodology Draft** — `methodology-draft.md`
- Complete methodology chapter with all formulas integrated
- Sections 3.1-3.11 covering all components
- References to figures and formulas

### Diagrams

- `fig1-architecture.mmd` — System Architecture
- `fig2-query-routing.mmd` — Query Routing
- `fig3-decomposition-loop.mmd` — Decomposition Loop
- `fig4-react-loop.mmd` — ReAct Execution Loop
- `fig5-review-loop.mmd` — Review Decision Tree
- `fig6-context-propagation.mmd` — Context Propagation
- `fig7-compaction.mmd` — Compaction Process
- `fig8-long-query-flow.mmd` — Long Query Flow
- `fig9-query-analyst-flow.mmd` — Query Analyst Flow
- `fig10-big-picture-architecture.mmd` — Big Picture Architecture

## Design Source

All content is verified against `src/tinycua/docs/design/` as the primary source of truth.

Key concepts:
- **NodeQueue**: Sequential execution of processing nodes
- **DecisionNode**: Two-step LLM decision (analysis → verdict → RouteMap dispatch)
- **ProcessNode**: Direct execution without routing
- **PropagationRule**: Controls context flow between nodes
- **CompactionStrategy**: Session context management

## Formula Integration

The formulas are designed to work together:

1. **Context Exposure** (Formula 1) provides the optimization objective
2. **Query Routing** (Formula 2) classifies and routes queries
3. **Effort Decomposition** (Formula 3) controls task planning depth
4. **Executor Context** (Formula 4) isolates task execution
5. **Review Threshold** (Formula 5) prevents infinite retries
6. **Context Propagation** (Formula 6) manages information flow
7. **Context Compaction** (Formula 7) manages window pressure
8. **NodeQueue Execution** (Formula 8) orchestrates node sequence
9. **Result Aggregation** (Formula 9) consolidates task results
10. **Information Digestion** (Formula 10) gathers additional context
11. **Response Synthesis** (Formula 11) produces final output

## Diagram Rendering

```bash
# Render all Mermaid diagrams to SVG
for f in *.mmd; do mmdc -i "$f" -o "${f%.mmd}.svg" -t dark -b transparent; done
```

## Mermaid CDN (for GitHub preview)

If `mmdc` is unavailable, paste `.mmd` content into [Mermaid Live Editor](https://mermaid.live/).
