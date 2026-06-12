# TinyCUA Architecture Diagrams

## 1. Component Hierarchy

```mermaid
graph TB
    subgraph SDK["SDK Layer"]
        Agent["Agent"]
        BaseLoop["BaseLoop"]
    end

    subgraph TinyCUALoop["TinyCUALoop extends BaseLoop"]
        RootSession["Root Session"]
        NodeQueue["NodeQueue"]
        PropagationRule["PropagationRule"]
    end

    subgraph DecisionNodes["DecisionNodes (LLM-powered routing)"]
        QueryAnalyst["QueryAnalystNode"]
        Worker["WorkerNode"]
    end

    subgraph ProcessNodes["ProcessNodes (execution)"]
        InfoDigester["InformationDigesterNode"]
        TaskCreate["TaskCreateNode"]
        TaskAnalyzer["TaskAnalyzerNode"]
        AnalysisEffort["AnalysisEffortNode"]
        TaskAssessor["TaskAssessorNode"]
        TaskExecutor["TaskExecutorNode"]
        ResultReviewer["ResultReviewerNode"]
        ResultAggregation["ResultAggregationNode"]
        Response["ResponseNode (terminal)"]
    end

    Agent --> BaseLoop
    BaseLoop --> TinyCUALoop
    TinyCUALoop --> RootSession
    TinyCUALoop --> NodeQueue
    NodeQueue --> DecisionNodes
    NodeQueue --> ProcessNodes

    style SDK fill:#2d3748,stroke:#4a5568,color:#fff
    style TinyCUALoop fill:#1a365d,stroke:#2b6cb0,color:#fff
    style DecisionNodes fill:#744210,stroke:#d69e2e,color:#fff
    style ProcessNodes fill:#22543d,stroke:#38a169,color:#fff
```

## 2. Node Class Hierarchy

```mermaid
classDiagram
    class Node {
        +node_id: str
        +session: Session
        +config: NodeConfigBase
        +is_terminal: bool
        +ensure_session()
        +build_messages()
        +validate_output()
        +on_complete()
    }

    class DecisionNode {
        +route_map: RouteMap
        +two_step_decision()
        +analysis_call()
        +verdict_call()
    }

    class ProcessNode {
        +process()
    }

    class QueryAnalystNode {
        +routes: worker, uncertain, passthrough
    }

    class WorkerNode {
        +routes: task_creation, task_recreation, task_reanalysis, passthrough, proceed_execution
    }

    class TaskCreateNode
    class TaskAnalyzerNode
    class AnalysisEffortNode
    class TaskAssessorNode
    class TaskExecutorNode
    class ResultReviewerNode
    class ResultAggregationNode
    class ResponseNode
    class InformationDigesterNode

    Node <|-- DecisionNode
    Node <|-- ProcessNode
    DecisionNode <|-- QueryAnalystNode
    DecisionNode <|-- WorkerNode
    ProcessNode <|-- TaskCreateNode
    ProcessNode <|-- TaskAnalyzerNode
    ProcessNode <|-- AnalysisEffortNode
    ProcessNode <|-- TaskAssessorNode
    ProcessNode <|-- TaskExecutorNode
    ProcessNode <|-- ResultReviewerNode
    ProcessNode <|-- ResultAggregationNode
    ProcessNode <|-- ResponseNode
    ProcessNode <|-- InformationDigesterNode
```

## 3. Main Execution Flow

```mermaid
flowchart TD
    Start["Agent.run(query)"] --> Loop["TinyCUALoop.run()"]
    Loop --> Init["1. Merge messages into root session"]
    Init --> PrepQA["2. Ensure QueryAnalyst at front"]
    PrepQA --> PrepResp["3. Ensure ResponseNode at end"]
    PrepResp --> QueueCheck{"4. Queue empty?"}

    QueueCheck -->|No| Node["node = queue.current"]
    Node --> Session["node.ensure_session()"]
    Session --> Input["node.build_messages()"]
    Input --> Tools["node.tool_policy.resolve()"]
    Tools --> LLM["agent._call_llm(messages, tools)"]
    LLM --> Validate["validate/retry per NodeRetryPolicy"]
    Validate --> Record["record chat history + session context"]
    Record --> OnComplete["node.on_complete(queue, result)"]
    OnComplete --> QueueCheck

    QueueCheck -->|Yes| Response["5. Return ResponseNode output"]

    style Start fill:#e53e3e,color:#fff
    style Response fill:#38a169,color:#fff
```

## 4. QueryAnalyst Routing

```mermaid
flowchart TD
    QA["QueryAnalystNode enters"] --> PassthroughCheck{"Valid mandatory_passthrough?"}

    PassthroughCheck -->|Yes| Forward["Forward to target node/session"]
    PassthroughCheck -->|No| Classify["LLM Classification"]

    Classify --> Decision["Two-step decision:<br/>1. Analysis call<br/>2. Verdict call"]

    Decision --> Routes{"Route?"}

    Routes -->|"worker"| WorkerCheck{"Existing WorkerNode queued?"}
    Routes -->|"uncertain"| Uncertain["Wait for user continuation"]
    Routes -->|"passthrough"| PT["Forward to active node/session"]

    WorkerCheck -->|Yes| ForwardWorker["Forward input to existing Worker"]
    WorkerCheck -->|No| SpawnWorker["Spawn new WorkerNode"]

    style QA fill:#d69e2e,color:#000
    style SpawnWorker fill:#2b6cb0,color:#fff
```

## 5. Worker Routing

```mermaid
flowchart TD
    W["WorkerNode enters"] --> TaskCheck{"Task exists?"}

    TaskCheck -->|No| TC["task_creation route"]
    TaskCheck -->|Yes| NodeCheck{"Worker nodes queued/active?"}

    NodeCheck -->|Yes| LLMDecision["LLM Decision<br/>Labels: task_recreation,<br/>task_reanalysis,<br/>passthrough,<br/>proceed_execution"]
    NodeCheck -->|No| LLMDecision2["LLM Decision<br/>Labels: task_recreation,<br/>task_reanalysis,<br/>proceed_execution"]

    TC --> TaskCreate["TaskCreateNode → TaskAnalyzer<br/>→ AnalysisEffort → Executor"]
    LLMDecision --> Route{"Route?"}
    LLMDecision2 --> Route2{"Route?"}

    Route -->|"task_recreation"| Recreate["Clear + TaskAnalyzer(+Init)<br/>→ AnalysisEffort → Executor"]
    Route -->|"task_reanalysis"| Reanalyze["Clear + TaskAnalyzer(no Init)<br/>→ AnalysisEffort → Executor"]
    Route -->|"passthrough"| Pass["Advance to active node"]
    Route -->|"proceed_execution"| Exec["Executor → ResultReviewer<br/>→ Response"]

    Route2 -->|"task_recreation"| Recreate
    Route2 -->|"task_reanalysis"| Reanalyze
    Route2 -->|"proceed_execution"| Exec

    style W fill:#d69e2e,color:#000
    style TaskCreate fill:#38a169,color:#fff
```

## 6. Task Execution Flow (Inside Worker)

```mermaid
flowchart TD
    TC["TaskCreateNode"] --> TA["TaskAnalyzerNode<br/>(mode: initial)"]
    TA --> AE["AnalysisEffortNode<br/>(controls extra passes)"]

    AE --> EffortCheck{"Pass count < limit?"}
    EffortCheck -->|Yes| Extra["TaskAssessor → TaskAnalyzer"]
    Extra --> AE
    EffortCheck -->|No| Executor["TaskExecutorNode<br/>(ReAct-style)"]

    Executor --> Reviewer["ResultReviewerNode"]

    Reviewer --> Decision{"Decision?"}
    Decision -->|"accept"| AggCheck{"Root task done?"}
    Decision -->|"retry"| Executor
    Decision -->|"replan"| Replan["TaskAssessor(local)<br/>→ TaskAnalyzer(replan)<br/>→ TaskExecutor"]
    Decision -->|"open_question"| Reviewer

    AggCheck -->|Yes| Agg["ResultAggregationNode"]
    AggCheck -->|No| NextTask["Find unfinished task → Executor"]

    Agg --> Response["ResponseNode<br/>(terminal)"]

    style TC fill:#38a169,color:#fff
    style Executor fill:#3182ce,color:#fff
    style Reviewer fill:#d69e2e,color:#000
    style Response fill:#38a169,color:#fff
```

## 7. Queue Suspension & Suspension Example

```mermaid
flowchart LR
    subgraph Before["Before Suspension"]
        Q1["[ResponseNode]"]
    end

    subgraph During["During Digestion"]
        Q2["[InfoDigester, ResponseNode suspended]"]
    end

    subgraph After["After Digestion"]
        Q3["[ResponseNode resumes]"]
    end

    Q1 -->|"ResponseNode requests info"| Q2
    Q2 -->|"Digester propagates output"| Q3

    style Before fill:#2d3748,color:#fff
    style During fill:#744210,color:#fff
    style After fill:#22543d,color:#fff
```

## 8. Context Propagation Model

```mermaid
flowchart TD
    subgraph Propagation["Segmented Context Propagation"]
        QA2["QueryAnalyst"] -->|"forwards: [query, QA response]"| N1["Node1"]
        N1 -->|"Node1 context = prior + input + output"| N1Done["Node1 completes"]
        N1Done -->|"parent gets: prior + input"| Parent["Root/Parent Session"]
        N1Done -->|"Node2 gets: Node1 output"| N2["Node2"]
    end

    style Parent fill:#1a365d,color:#fff
    style QA2 fill:#d69e2e,color:#000
```
