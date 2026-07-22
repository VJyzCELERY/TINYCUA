# TinyCUA Node Pseudocode Generator

## How to Use

1. Fill in the fields below
2. Paste this entire prompt into the conversation
3. The model will output two files: `<node-name>.tex` and `<node-name>.md`

---

## Template

```
Generate IEEE-style pseudocode for a TinyCUA node. Output two files.

## Node Name
[QUERY_ANALYST | WORKER | INFORMATION_DIGESTER | TASK_CREATE | TASK_ANALYZER | TASK_ASSESSOR | TASK_EXECUTOR | RESULT_REVIEWER | RESULT_AGGREGATION | RESPONSE | your custom name]

## Algorithm Number
[Algorithm N]

## Node Type
[DecisionNode | ProcessNode]

## Input Variables
[Example: User query q, session context C, task tree T]

## Output Variables
[Example: Enhanced query q_enhanced, route label route]

## Your Prose Description
[PASTE YOUR WRITE HERE — describe what the node does, its steps, decisions, tool usage, constraints]

---

## Output Format

### File 1: <node-name>.tex

Use this exact LaTeX structure:

\documentclass{article}
\usepackage{algorithm}
\usepackage{algpseudocode}
\usepackage{amsmath}
\usepackage{amssymb}

\begin{document}

\begin{algorithm}[t]
\caption{TINYCUA [Node Name]}
\label{alg:[node-name]}
\begin{algorithmic}[1]
\Require [input variables with math notation]
\Ensure [output variables with math notation]

// Step 1: [comment]
\State ...

// Step 2: [comment]
\State ...

\end{algorithmic}
\end{algorithm}

\end{document}

Rules for .tex:
- Use \textsc{} for function names (e.g., \textsc{SLMAnalyze})
- Use \mathit{} for variables (e.g., \mathit{route})
- Use // for section comments (NOT \Statex \textit{--- ... ---})
- Use \gets for assignments
- Use \If, \ElsIf, \While, \For, \ForAll, \EndIf, \EndWhile, \EndFor
- Line numbers are automatic via algorithmic[1]
- Keep it algorithmic: loops, conditionals, data transforms only

### File 2: <node-name>.md

Use this exact markdown structure:

# Algorithm N: [Node Name]

> **Methodology section pairing:** The prose below accompanies Algorithm N
> in the paper. It covers design invariants and constraints that are not
> algorithmic and therefore remain outside the pseudocode block.

---

## Pseudocode (Algorithm N)

**Input:** [variables with math notation]
**Output:** [variables with math notation]

```
// Step 1: [Name]
[pseudocode]

// Step 2: [Name]
[pseudocode]
...
```

---

## Companion Prose (Not in Pseudocode)

The following design properties are described in the surrounding methodology
text and are **not** captured by the algorithm above:

### [Invariant Name 1]
[Prose description of design rule, constraint, or invariant]

### [Invariant Name 2]
[Prose description]

---

## Tool Permissions Summary

| Tool | Allowed | Purpose |
|------|---------|---------|
| [ToolName] | Yes/No/Conditional | [Purpose] |

---

## Retry Policy Summary

| Condition | Action |
|-----------|--------|
| [Condition] | [Action] |

---

## Separation Rules

What goes into PSEUDOCODE (the algorithm block):
- Boolean checks and guards
- Data collection / function calls
- Loop control flow (while, for)
- Conditional branching (if/else)
- Variable assignments and data construction
- Retry logic

What stays in COMPANION PROSE (methodology text):
- Queue position invariants ("always first in queue")
- Propagation rules ("not merged back to parent", "durable only when merged")
- Tool constraints ("read-only", "no write operations")
- Deduplication policies ("only spawned when none exists")
- Architectural role descriptions
- Design rationale
```
