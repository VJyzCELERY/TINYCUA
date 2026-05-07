# Stage 05 — Design: Remove Memory

## Overview

Delete the `memory/` package and remove memory references from `Agent`. Memory management (short-term context, long-term facts, embeddings, retrieval) is a consumer concern.

## Design Decisions

### Why Delete Memory?

1. **Stateful by definition**: Memory stores information across runs. This is runtime state.
2. **Consumer owns memory strategy**: The consumer decides:
   - What to remember (full conversations, summaries, facts, embeddings)
   - How to store it (in-memory, Redis, vector DB, file)
   - When to retrieve it (on every turn, on trigger, never)
   - How to compress/forget (sliding window, summarization, importance scoring)
3. **Embeddings are infrastructure**: Vector DBs (Pinecone, Weaviate, pgvector) are deployment concerns.
4. **Context compression is algorithmic**: The consumer decides how to fit long conversations into context windows.

### What Replaces Memory?

Nothing in the SDK. The consumer injects memory into `Agent.run()` via:
1. **System prompt**: Include relevant facts in `LLMModel.system_prompt`
2. **Message history**: Pass retrieved context as `messages` parameter
3. **Instructions**: Include memory-based directives in `Agent.instructions`

## Files to Delete

| File | Reason |
|------|--------|
| `memory/__init__.py` | Package init |
| `memory/short_term.py` | In-memory short-term storage — stateful |
| `memory/long_term.py` | File-based long-term storage — stateful |
| `memory/plugin.py` | Memory plugin system — stateful |
| `memory/compression.py` | Context compression — consumer concern |
| `memory/cache.py` | Memory cache — stateful |
| `storage/snapshot.py` | Snapshot manager (memory-related) — stateful |
| `tools/memory.py` | MemoryBackend — stateful |
| `tools/memory_tools.py` | remember/recall/forget tools — depend on memory |

## Code Changes in Agent

### Remove memory parameters

```python
# BEFORE
class Agent:
    def __init__(self, ..., 
                 short_term_memory=None, 
                 long_term_memory=None, 
                 planning_prompt=None,
                 ...):
        self.short_term_memory = short_term_memory
        self.long_term_memory = long_term_memory
        self.planning_prompt = planning_prompt

# AFTER
class Agent:
    def __init__(self, ..., loop=None, ...):
        # Memory parameters removed
```

### Remove memory interactions from loop

```python
# BEFORE (loop.py)
async def run(self, agent, query):
    # Load memory
    facts = agent.long_term_memory.recall(query)
    context = agent.short_term_memory.get_recent()
    
    # Build prompt with memory
    prompt = f"{agent.planning_prompt}\n\nFacts: {facts}\n\nContext: {context}\n\nQuery: {query}"
    ...

# AFTER (loop.py)
async def run(self, agent, messages, tools):
    # Agent loop operates on messages passed by consumer
    # No memory fetching
    ...
```

## Impact Analysis

### Files that reference memory

```bash
grep -r "short_term_memory\|long_term_memory\|planning_prompt" \
  src/tinycua-sdk/tinycua_sdk/
```

### Expected impact

- `agent/agent.py` — Remove memory parameters
- `agent/executor.py` — Remove memory loading in run()
- `agent/definition.py` — Remove memory fields
- `agent/config.py` — Remove memory from AgentConfig
- `agent/loop.py` — Remove memory references
- `tools/memory.py` — Deleted
- `tools/memory_tools.py` — Deleted

## Consumer Migration Guide

### Before (SDK manages memory)
```python
from tinycua_sdk import Agent, ShortTermMemory, LongTermMemory

stm = ShortTermMemory()
ltm = LongTermMemory()
agent = Agent(
    short_term_memory=stm,
    long_term_memory=ltm,
    planning_prompt="Think step by step",
)
response = await agent.run("What did we discuss earlier?")
```

### After (Consumer manages memory)
```python
from tinycua_sdk import Agent, LLMModel

# Consumer's own memory implementation
class MyMemory:
    def recall(self, query: str) -> list[str]:
        # Consumer's own retrieval logic
        ...

memory = MyMemory()

# Consumer injects memory into the prompt
facts = memory.recall("What did we discuss earlier?")
system = f"You are a helpful assistant.\n\nRelevant facts:\n" + "\n".join(facts)

agent = Agent(llm_model=LLMModel(system_prompt=system))
response = await agent.run("What did we discuss earlier?")
```

## Acceptance Criteria

- [ ] `memory/` package is deleted entirely.
- [ ] `storage/snapshot.py` is deleted.
- [ ] `tools/memory.py` is deleted.
- [ ] `tools/memory_tools.py` is deleted.
- [ ] `Agent` does not accept `short_term_memory`, `long_term_memory`, or `planning_prompt`.
- [ ] `Agent.run()` does not fetch or store memory.
- [ ] `pytest` still passes for remaining tests.

## Dependencies

- **Requires**: Stage 01, Stage 02.
- **Blocks**: None (can proceed in parallel with Stages 03, 04, 06–07).
