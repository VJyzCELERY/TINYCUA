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

### Step 1: Read the Architecture

Read `src/tinycua/psudocode/TinyCUA_Architecture.png`. Identify the node(s) relevant to this section. Note the incoming and outgoing edges, and how this node connects to the overall workflow.

### Step 2: Read the User's Write

Analyze the user's prose. This write describes an algorithm in natural language. Your job is to **reconstruct** it into formal pseudocode — transform the prose into algorithmic notation while preserving the same logic and steps.

### Step 3: Validate Against Design Docs

Cross-reference with `src/tinycua/docs/design/` to verify correctness. If the user's write omits details that exist in the design docs, note them but **do not add them** — the paper focuses on agent loops, not user uncertainty handling or other out-of-scope topics.

### Step 4: Generate Compact Pseudocode

**Max 15 lines of pseudocode.** Compress aggressively:
- Merge related assignments into single lines
- Combine simple if/else into one block
- Remove redundant intermediate variables
- Use inline conditionals where possible
- Skip trivial steps (e.g., `retryCount ← 0` can be implicit in the while condition)

If the algorithmic core exceeds 15 lines, prioritize the essential control flow and move secondary steps to companion prose.

### Step 5: Generate Compact Companion Prose

The companion prose explains what the pseudocode does NOT cover. It must be **shorter than the original write** — compress to ~30-50% length. One sentence per invariant.

### Separation Rules

**Reconstruction Rule:** The user's write is a prose description of an algorithm. Reconstruct it into pseudocode by:
1. Identify each step described in the prose
2. Map it to an algorithmic construct (assignment, if/else, while, function call)
3. Name variables and functions based on what the prose describes
4. Preserve the exact logic — do not add, skip, or reorder steps
5. If the prose says "calls X to analyze Y", write `result ← X(Y)`
6. If the prose says "retries until valid", write `while invalid: retry`
7. If the prose says "if route is worker, spawn Z", write `if route = Worker: Spawn(Z)`

**Pseudocode (algorithm block)** — reconstruct these from prose:
- Boolean checks / guards
- Data collection / function calls
- Loop control flow (while, for)
- Conditional branching (if/else)
- Variable assignments and data construction
- Retry logic
- Route decisions / dispatch

**Companion Prose (methodology text)** — keep as prose, NOT in algorithm:
- Queue position invariants (1 sentence)
- Propagation rules (1 sentence)
- Tool constraints (1 sentence)
- Deduplication policies (1 sentence)
- Architectural role (1 sentence)
- Design rationale (1 sentence)

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
- **Max 15 numbered lines** (excluding comments)
- Compress: merge assignments, combine if/else, inline where possible

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
[1-2 sentence description]

### [Invariant Name 2]
[1-2 sentence description]

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

---

## Scope Note

The paper focuses on the agent loop architecture. If the user's write or the
design docs mention features outside this scope (e.g., user uncertainty handling,
HITL UX, interrupt handling, resume flow), **exclude them from the pseudocode**.
They may be briefly noted in companion prose as "deferred" or "out of scope."
```
