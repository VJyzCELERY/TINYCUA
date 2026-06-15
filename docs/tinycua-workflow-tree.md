# TinyCUA Workflow Tree

Based on `src/tinycua/docs/design/` (post-simplification)

---

## 1. High-Level Architecture

```
SDK Agent.run(query)
  └── TinyCUALoop (extends SDK BaseLoop)
        ├── root Session
        └── NodeQueue ──► sequential execution, active = queue[0]
```

---

## 2. Node Types

```
┌─────────────────────────────────────────────────────────┐
│  DecisionNode (2-step: analysis → verdict → RouteMap)   │
│  ● QueryAnalyst                                         │
│  ● Worker                                               │
├─────────────────────────────────────────────────────────┤
│  ProcessNode (single focused responsibility)            │
│  ● TaskCreate      ● TaskAnalyzer    ● TaskAssessor    │
│  ● AnalysisEffort  ● TaskExecutor    ● ResultReviewer  │
│  ● ResultAggregation               ● Response          │
│  ● InformationDigester (on-demand)                      │
└─────────────────────────────────────────────────────────┘
```

---

## 3. All Loops in the System

```
┌─────────────────────────────────────────────────────────────┐
│                     LOOP 1: EFFORT LOOP                     │
│              (pre-execution, deterministic, no LLM)          │
│                                                             │
│   AnalysisEffort ──► TaskAssessor ──► TaskAnalyzer ──┐      │
│        ▲                                              │      │
│        └──────────────── pass_count++ ◄───────────────┘      │
│                                                             │
│   Terminates when pass_count >= pass_limit                   │
│   (none=0, low=1, medium=2, high=3)                        │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                   LOOP 2: REVIEW LOOP                       │
│              (post-execution, LLM-based)                     │
│                                                             │
│   TaskExecutor ──► ResultReviewer ──┐                       │
│        ▲                             │                       │
│        │        ┌── retry ◄──────────┘                       │
│        │        │                                            │
│        └────────┘                                            │
│                                                             │
│   retry: same task again                                    │
│   accept: advance (more tasks → executor, root done → next) │
│   replan: TaskAssessor → TaskAnalyzer → executor            │
│   open_question: stay active, wait for user                 │
│   threshold: failure_count >= 5 → must escalate             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                   LOOP 3: REPLAN LOOP                       │
│              (local recovery, no AnalysisEffort)             │
│                                                             │
│   TaskAssessor ──► TaskAnalyzer ──► TaskExecutor            │
│                                                             │
│   Scope: active task or local region only                   │
│   TaskAnalyzer mode: local_replan (no TaskInit tools)       │
│   Does NOT go through AnalysisEffort                        │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                LOOP 4: RESPONSE SUSPENSION                  │
│              (on-demand, InformationDigester)                │
│                                                             │
│   Response ──► suspend ──► InformationDigester              │
│        ▲                         │                          │
│        └──── propagate back ◄────┘                          │
│                                                             │
│   Trigger: context insufficient                             │
│   Digester creates fresh session, retrieves context         │
│   Propagates output back, Response resumes                  │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│              LOOP 5: UNCERTAIN / WAIT LOOP                  │
│              (QueryAnalyst waits for user)                   │
│                                                             │
│   QueryAnalyst ──► uncertain ──► stays active               │
│        ▲                         │                          │
│        └── user continuation ◄───┘                          │
│                                                             │
│   No queue mutation. QueryAnalyst re-runs classification.   │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. Full Workflow Tree with All Loops

```
User Query
    │
    ▼
┌──────────────────────┐
│   QueryAnalyst       │ ◄── Entry node (always first)
│   [DecisionNode]     │
│                      │
│  analysis → verdict  │
└──────┬───────────────┘
       │
       ├──► passthrough ──► forward to existing node/session
       │
       ├──► uncertain ──┐
       │                │   ┌─────────────────────────────┐
       │                └──►│ LOOP 5: WAIT FOR USER        │
       │                    │ QueryAnalyst stays active     │
       │                    │ ──► user continues ◄──┐      │
       │                    │                       │      │
       │                    └───────────────────────┘      │
       │                                                   │
       └──► worker ──┐
                     │
                     ▼
       ┌──────────────────────┐
       │     Worker           │ ◄── Decision hub
       │     [DecisionNode]   │
       │                      │
       │  analysis → verdict  │
       └──────┬───────────────┘
              │
              ├──► task_creation ──┐
              │                    │
              ├──► task_recreation─┤
              │                    │
              ├──► task_reanalysis─┤
              │                    │
              ├──► proceed_execution ──────────────────────────┐
              │                                                │
              └──► passthrough ──► forward to existing         │
                                   worker-owned node           │
                                                              │
       ┌──────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────┐
│    TaskCreate         │ ◄── only for task_creation route
│    [ProcessNode]      │
└──────┬────────────────┘
       │
       ▼
┌──────────────────────┐
│   TaskAnalyzer        │ ◄── mode: initial_analysis / recreation / reanalysis
│   [ProcessNode]       │
└──────┬────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────┐
│                                                              │
│              LOOP 1: EFFORT LOOP                             │
│              (no LLM, deterministic)                          │
│                                                              │
│   ┌──────────────────────┐                                    │
│   │   AnalysisEffort      │                                   │
│   │   pass_count=0        │                                   │
│   └──────┬────────────────┘                                    │
│          │                                                    │
│          ├── pass_count < limit ──┐                           │
│          │                        │                           │
│          │                        ▼                           │
│          │              ┌──────────────────┐                  │
│          │              │   TaskAssessor    │                  │
│          │              │                  │                  │
│          │              │ select tasks     │                  │
│          │              └──┬──────────┬───┘                  │
│          │                 │          │                       │
│          │                 │          └── no tasks ──► back   │
│          │                 │               to AnalysisEffort  │
│          │                 ▼                                  │
│          │              ┌──────────────────┐                  │
│          │              │   TaskAnalyzer    │                  │
│          │              │                  │                  │
│          │              │ decompose tasks  │                  │
│          │              └──────┬───────────┘                  │
│          │                     │                              │
│          │                     ▼                              │
│          │              back to AnalysisEffort                 │
│          │              (pass_count++)                        │
│          │                                                    │
│          └── pass_count >= limit ──┐                          │
│                                   │                           │
└───────────────────────────────────┘                           │
                                                                │
       ┌───────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────┐
│    TaskExecutor       │ ◄── ReAct execution
│    [ProcessNode]      │     (only node that runs task actions)
└──────┬────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────┐
│                                                              │
│              LOOP 2: REVIEW LOOP                             │
│              (LLM-based)                                     │
│                                                              │
│   ┌──────────────────────┐                                   │
│   │   ResultReviewer      │                                  │
│   │   [ProcessNode]       │                                  │
│   └──┬───┬───┬───┬───────┘                                   │
│      │   │   │   │                                           │
│      │   │   │   └──► open_question ──► stay active          │
│      │   │   │              │       (mandatory_passthrough)  │
│      │   │   │              │                                │
│      │   │   │              ▼                                │
│      │   │   │         user continues ──► back to executor   │
│      │   │   │                                               │
│      │   │   └───► replan ──┐    ┌───────────────────────────┤
│      │   │                  │    │                            │
│      │   │                  ▼    │  LOOP 3: REPLAN LOOP      │
│      │   │         ┌──────────┐  │  (local, no AnalysisEffort)│
│      │   │         │TaskAssessor│ │                            │
│      │   │         └────┬─────┘  │                            │
│      │   │              ▼        │                            │
│      │   │         ┌──────────┐  │                            │
│      │   │         │TaskAnalyzer│ │  mode: local_replan       │
│      │   │         └────┬─────┘  │                            │
│      │   │              ▼        │                            │
│      │   │         TaskExecutor ◄┘                            │
│      │   │              │                                     │
│      │   │              └────────── back to ResultReviewer ──┘
│      │   │                                                   │
│      │   └────► retry ──► TaskExecutor (same task) ──► back   │
│      │                                          to Reviewer   │
│      │                                                       │
│      └──► accept ──┬── more tasks ──► TaskExecutor (next)    │
│                    │                    ──► back to Reviewer  │
│                    │                                          │
│                    └── root done ──┐                          │
│                                   │                           │
└───────────────────────────────────┘                           │
                                                                │
       ┌───────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────┐
│  ResultAggregation    │
│  [ProcessNode]        │
│                       │
│  guided BFS traversal │
│  consolidate results  │
└──────┬────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────┐
│                                                              │
│              LOOP 4: RESPONSE SUSPENSION                     │
│              (on-demand)                                     │
│                                                              │
│   ┌──────────────────────┐                                   │
│   │     Response          │ ◄── terminal                      │
│   │     [ProcessNode]     │                                   │
│   │                       │                                   │
│   │  context sufficient?  │                                   │
│   └──┬────────────────┬───┘                                   │
│      │                │                                       │
│      │ YES            │ NO                                    │
│      │                │                                       │
│      ▼                ▼                                       │
│   ┌────────┐   ┌──────────────────────┐                      │
│   │ terminal│   │ suspend + prepend:   │                      │
│   │ (answer)│   │ InformationDigester  │                      │
│   └────────┘   │ [ProcessNode]        │                      │
│                │                      │                      │
│                │ fresh session        │                      │
│                │ context retrieval    │                      │
│                │ digest information   │                      │
│                └──────┬───────────────┘                      │
│                       │                                       │
│                       │ propagate back to Response            │
│                       ▼                                       │
│                Response resumes ──► terminal                  │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## 5. Loop Summary Table

| Loop | Type | LLM? | Trigger | Termination | Scope |
|------|------|------|---------|-------------|-------|
| **Effort Loop** | Pre-execution planning | No | After initial TaskAnalyzer pass | pass_count >= pass_limit | Full task tree |
| **Review Loop** | Post-execution quality gate | Yes | After TaskExecutor completes | accept (more tasks or root done), threshold (5 retries) | Active task |
| **Replan Loop** | Local recovery | Yes | Reviewer decides replan | TaskExecutor completes successfully | Active task / local region |
| **Response Suspension** | On-demand context gathering | Yes | ResponseNode: context insufficient | InformationDigester propagates back | Single digest request |
| **Uncertain/Wait** | User continuation | Yes | QueryAnalyst: uncertain label | User sends continuation | None (stays in place) |

---

## 6. Worker Route Shapes (queue after Worker)

```
task_creation:
  Worker → TaskCreate → TaskAnalyzer → AnalysisEffort ──► LOOP 1 ──►
    TaskExecutor → ResultReviewer ──► LOOP 2 ──► ResultAggregation → Response ──► LOOP 4

task_recreation:
  Worker → TaskAnalyzer(+TaskInit) → AnalysisEffort ──► LOOP 1 ──►
    TaskExecutor → ResultReviewer ──► LOOP 2 ──► ResultAggregation → Response ──► LOOP 4

task_reanalysis:
  Worker → TaskAnalyzer(no TaskInit) → AnalysisEffort ──► LOOP 1 ──►
    TaskExecutor → ResultReviewer ──► LOOP 2 ──► ResultAggregation → Response ──► LOOP 4

proceed_execution:
  Worker → TaskExecutor → ResultReviewer ──► LOOP 2 ──► ResultAggregation → Response ──► LOOP 4

passthrough:
  Worker → forward input to existing worker-owned node/session
```

---

## 7. Propagation Rules

```
┌─────────────────────────────────────────────────────────┐
│  On node completion:                                     │
│                                                          │
│  session_context = prior_context + input_segment         │
│                                       + output_segment   │
│                                                          │
│  On termination:                                         │
│    parent gets: prior + input                            │
│    next node gets: output (as NodeInput)                 │
│                                                          │
│  Dedupe: origin_record_id prevents duplication           │
│                                                          │
│  Transient nodes (QueryAnalyst, Worker):                 │
│    do NOT backward-propagate their assembled context     │
│    output becomes durable only through next node's input │
└─────────────────────────────────────────────────────────┘
```

---

## 8. Key Design Principles

| # | Principle | Description |
|---|-----------|-------------|
| 1 | **No graph runtime** | Sequential NodeQueue replaces AgentGraph. Position = control flow. |
| 2 | **Two LLM node types** | DecisionNode (2-step analysis+verdict+RouteMap) vs ProcessNode (single task). |
| 3 | **Transient routing nodes** | QueryAnalyst and Worker don't propagate their own context. |
| 4 | **Suspension for nested flows** | InformationDigester spawned by suspending ResponseNode. |
| 5 | **Mandatory passthrough** | Deterministic continuation bypasses LLM classification. |
| 6 | **Effort-gated planning** | AnalysisEffortNode (no LLM) controls decomposition passes. |
| 7 | **Review-driven loop** | ResultReviewer gates retry/replan/accept/open_question. |
| 8 | **Compaction boundary** | session_context is mutable (compactable); chat_history is immutable (audit). |
| 9 | **Todo as local driver** | Each node session has Todo for local step tracking; Task is broader goal. |
| 10 | **Failure threshold** | Reviewer retries capped at 5 (configurable), then must escalate. |
