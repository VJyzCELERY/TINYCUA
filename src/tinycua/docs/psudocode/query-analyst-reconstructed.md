# Query Analyst Node — Reconstructed Write

## Original Write (for reference)

When queue is created, the Query Analyst node always be the front in the queue as the first node that will classify user queries and routing it to the appropriate downstream path. As the first input layer of the loop, the query analyst receives the overhead of the full context and filters it based on the relevant information that it finds. It collects context from the root session or existing nodes, and the user queries into a temporary reasoning window as guidance for the next node on the overview of useful context. This window is not fully merged back to the parent node. The output from the query analyst becomes durable only when received by and merged into the next node according to the segmented context model. The query analyst also enforces deduplication. It is only spawned when no query analyst already exists. The query analyst has only read-only exploratory tools. It can inspect the status of existing tasks and explore information such as reading files or web searching to assist routing decisions, but is not permitted to perform any write operation, ensuring that its role is solely to classify and route.

To classify the user's queries, this node calls SLM to analyze the context and user's queries. Once done, this analysis produces routing decisions that determine which downstream path the query should follow, either worker or passthrough route. Then, SLM invokes a classification tool to assign their route. If the route is invalid or not invoked, the process is retried according to the node retry policy. Once a valid label is established, the route map dispatches to the appropriate handler. If the route is worker, this node spawns the information digester before routing to the worker node.

---

## Reconstructed Write (Compact, Paper-Ready)

The Query Analyst is the first node in the queue. It classifies user queries and routes them to downstream handlers.

**Context collection.** The node receives the full session context and collects information from the root session, existing nodes, and read-only exploration (e.g., file reads, web search). A write-only constraint ensures the node cannot mutate state.

**Reasoning window.** Collected context is filtered for relevance and assembled into a temporary reasoning window. This window is not merged back to the parent node; output becomes durable only when propagated to the next node.

**Classification.** The node invokes an SLM to analyze the reasoning window and produce a route label. If the label is invalid, classification retries up to a configurable limit before falling back to a default route.

**Dispatch.** A valid label routes to either the passthrough path (direct response) or the worker path (via the Information Digester). Deduplication ensures only one Query Analyst exists per session.

---

## Algorithm 2: Query Analyst Node (Pseudocode)

**Input:** User query $q$, session context $C$
**Output:** Enhanced query $q_{\text{enhanced}}$, route label $\mathit{route}$

```
// Deduplication guard
if QueryAnalystAlreadyActive(C):
    return ⊥

// Context collection (read-only)
ctx ← CollectContext(q, C)

// Build reasoning window and classify
rw ← {q} ∪ FilterRelevant(ctx, q)
route ← ClassifyRoute(SLMAnalyze(rw))

// Validate route with retry
while route is invalid or not invoked:
    route ← ClassifyRoute(SLMAnalyze(rw))
    if retries exceeded:
        return q, DefaultRoute()

// Dispatch
q_enhanced ← {q} ∪ FilterRelevant(rw, q)
if route = Worker:
    SpawnInformationDigester()
return q_enhanced, route
```
