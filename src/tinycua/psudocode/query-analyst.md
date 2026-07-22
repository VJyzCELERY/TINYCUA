# Algorithm 2: Query Analyst Node

> Pseudocode derived from subsection explanation of `QueryAnalystNode`

**Function:** `QueryAnalystNode(UserQuery, SessionContext)`

**Input:**
- `UserQuery` — the raw user input
- `SessionContext` — full session context (chat history + retrieved context)

**Output:**
- `EnhancedQuery` — query enriched with filtered context
- `Route` — classification label (`Passthrough` | `Worker`)

---

## Query Analyst Workflow

```
Function QueryAnalystNode(UserQuery, SessionContext):

    ─────────────────────────────────────────────
    STEP 1: Deduplication Guard
    ─────────────────────────────────────────────

    if QueryAnalystAlreadyActive(SessionContext):
        return None  // skip — only one Query Analyst per session

    ─────────────────────────────────────────────
    STEP 2: Context Collection (Read-Only)
    ─────────────────────────────────────────────

    // Inspect existing task status and explore information
    // using read-only tools only (no write operations)

    RootContext = ReadRootSession(SessionContext)
    ExistingNodeContext = InspectExistingNodes(SessionContext)
    ExploratoryContext = ExploreInformation(UserQuery, SessionContext)
        // e.g., read files, web search — read-only only

    ─────────────────────────────────────────────
    STEP 3: Temporary Reasoning Window
    ─────────────────────────────────────────────

    // Assemble a temporary reasoning window for classification
    // This window is NOT merged back to parent node
    // Output becomes durable only when merged into next node

    ReasoningWindow = {
        UserQuery,
        FilteredRootContext = FilterRelevant(RootContext, UserQuery),
        FilteredNodeContext = FilterRelevant(ExistingNodeContext, UserQuery),
        ExploratoryContext
    }

    ─────────────────────────────────────────────
    STEP 4: SLM Classification
    ─────────────────────────────────────────────

    // Call SLM to analyze context and user query
    Analysis = SLMAnalyze(ReasoningWindow)

    // SLM invokes classification tool to assign route
    Route = ClassifyRoute(Analysis)

    ─────────────────────────────────────────────
    STEP 5: Route Validation and Retry
    ─────────────────────────────────────────────

    RetryCount = 0
    MaxRetries = NodeRetryPolicy.MaxRetries

    while Route is invalid or Route is not invoked:

        RetryCount = RetryCount + 1

        if RetryCount > MaxRetries:
            // Fallback: default to passthrough or escalate
            Route = DefaultRoute()
            break

        // Retry classification
        Analysis = SLMAnalyze(ReasoningWindow)
        Route = ClassifyRoute(Analysis)

    ─────────────────────────────────────────────
    STEP 6: Route Dispatch
    ─────────────────────────────────────────────

    // Enhance query with filtered context from reasoning window
    EnhancedQuery = {
        UserQuery,
        Context = FilterRelevant(ReasoningWindow, UserQuery)
    }

    // Route map dispatches to appropriate handler
    if Route == Worker:
        // Spawn Information Digester before routing to Worker
        SpawnInformationDigester()
        return EnhancedQuery, Worker

    else if Route == Passthrough:
        return EnhancedQuery, Passthrough
```

---

## Tool Permissions

| Tool | Allowed | Purpose |
|------|---------|---------|
| ReadRootSession | Yes | Collect root session context |
| InspectExistingNodes | Yes | Check status of existing tasks |
| ExploreInformation | Yes | Read files, web search for routing context |
| WriteFile | **No** | Read-only node — no mutations |
| ModifyTask | **No** | Read-only node — no mutations |
| SpawnAgent | Conditional | Spawn Information Digester if Worker route |

---

## Retry Policy

| Condition | Action |
|-----------|--------|
| Route is invalid | Retry classification up to `MaxRetries` |
| Route is not invoked | Retry classification up to `MaxRetries` |
| MaxRetries exceeded | Use `DefaultRoute()` (passthrough fallback) |
| Query Analyst already active | Skip — deduplication enforced |

---

## Context Model

| Aspect | Behavior |
|--------|----------|
| Input | Full session context overhead |
| Processing | Filter to relevant information only |
| Reasoning window | Temporary — not merged back to parent |
| Output durability | Becomes durable only when merged into next node |
| Downstream merge | `EnhancedQuery` merged into Information Digester or Response Node |
