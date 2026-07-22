# TinyCUA Pseudocode Generator

## How to Use

1. Fill in the 3 fields below
2. Paste this entire prompt into the conversation
3. The model will output two files: `<section-name>.tex` and `<section-name>.md`

---

## Template

```
Generate IEEE-style pseudocode from my paper subsection write. Output two files.

## Section
[SECTION NAME — e.g., Query Analyst, Worker, Information Digester, Task Executor, etc.]

## Algorithm Number
[Algorithm N]

## My Paper Write
[PASTE YOUR SUBSECTION WRITE HERE — the prose you wrote for this section of your methodology]
```

---

## Instructions to Model

From the user's prose, extract and produce:

### Separation Rules

**Pseudocode (algorithm block)** — extract these as algorithmic steps:
- Boolean checks / guards
- Data collection / function calls
- Loop control flow (while, for)
- Conditional branching (if/else)
- Variable assignments and data construction
- Retry logic
- Route decisions / dispatch

**Companion Prose (methodology text)** — keep these as prose, NOT in the algorithm:
- Queue position invariants
- Propagation rules ("not merged back to parent", "durable only when merged")
- Tool constraints ("read-only", "no write operations")
- Deduplication policies
- Architectural role descriptions
- Design rationale

### File 1: <section-name>.tex

Use this exact LaTeX structure:

\documentclass{article}
\usepackage{algorithm}
\usepackage{algpseudocode}
\usepackage{amsmath}
\usepackage{amssymb}

\begin{document}

\begin{algorithm}[t]
\caption{TINYCUA [Section Name]}
\label{alg:[section-name]}
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
- Use // for section comments
- Use \gets for assignments
- Use \If, \ElsIf, \While, \For, \ForAll, \EndIf, \EndWhile, \EndFor
- Line numbers are automatic via algorithmic[1]
- Infer input/output variables from the prose
- Keep it algorithmic: loops, conditionals, data transforms only

### File 2: <section-name>.md

Use this exact markdown structure:

# Algorithm N: [Section Name]

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
[Prose description]

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

## Output Naming

Save files as:
- `psudocode/[section-name].tex`
- `psudocode/[section-name].md`

Where [section-name] is lowercase, hyphenated (e.g., query-analyst, task-executor, information-digester).
```
