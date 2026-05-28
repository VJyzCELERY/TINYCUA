# Implementation: Remove Memory

Delete the entire `memory/` package and remove all memory references from `Agent`, config, and tools. Memory management (short-term context, long-term facts, embeddings, retrieval, compression) is a consumer concern. The SDK must be stateless and perform no memory I/O.

## Context

- **Spec Reference**: [spec.md](spec.md)
- **Design Reference**: [design.md](design.md)
- **Priority**: P0
- **Estimated Effort**: S

## Proposed Changes

### Memory Package Deletion

#### [DELETE] `tinycua_sdk/memory/__init__.py`

- **[Description of change]**: Remove package init that exports `Message`, `ShortTermMemory`, `LongTermMemory`, `ContextCompressor`, `CacheEntry`, and `PromptCache`.
- **[Rationale]**: Entire memory package is being removed.

#### [DELETE] `tinycua_sdk/memory/short_term.py`

- **[Description of change]**: Remove `ShortTermMemory` and its `Message` helper.
- **[Rationale]**: In-memory short-term storage is stateful and belongs in the consumer.

#### [DELETE] `tinycua_sdk/memory/long_term.py`

- **[Description of change]**: Remove `LongTermMemory` (file-based persistent facts).
- **[Rationale]**: File-based long-term storage is stateful and belongs in the consumer.

#### [DELETE] `tinycua_sdk/memory/plugin.py`

- **[Description of change]**: Remove memory plugin system.
- **[Rationale]**: Plugin system for memory is stateful and belongs in the consumer.

#### [DELETE] `tinycua_sdk/memory/compression.py`

- **[Description of change]**: Remove `ContextCompressor`.
- **[Rationale]**: Context compression is an algorithmic consumer concern.

#### [DELETE] `tinycua_sdk/memory/cache.py`

- **[Description of change]**: Remove `CacheEntry` and `PromptCache`.
- **[Rationale]**: Memory cache is stateful and belongs in the consumer.

### Tools Memory Deletion

#### [DELETE] `tinycua_sdk/tools/memory.py`

- **[Description of change]**: Remove `MemoryBackend`, `LocalMemoryBackend`, `RemoteMemoryBackend`, `HybridMemoryBackend`, and `get_memory_backend`.
- **[Rationale]**: Memory backend abstraction is stateful and belongs in the consumer.

### Remove Memory References from Remaining Code

#### [MODIFY] `tinycua_sdk/agent/agent.py`

- **[Description of change]**: Remove `planning_prompt`, `short_term_memory`, and `long_term_memory` parameters from `__init__`. Remove related docstrings and any memory-related logic.
- **[Rationale]**: Agent must not accept or reference memory.

#### [MODIFY] `tinycua_sdk/agent/executor.py`

- **[Description of change]**: Remove `planning_prompt` parameter from `__init__` and any forwarding to `Agent`.
- **[Rationale]**: Executor must not reference memory or planning prompt.

#### [MODIFY] `tinycua_sdk/agent/definition.py`

- **[Description of change]**: Remove `planning_prompt` parameter from `__init__` and the `planning_prompt` property. Remove related docstrings.
- **[Rationale]**: Agent definition must not reference memory or planning prompt.

#### [MODIFY] `tinycua_sdk/agent/config.py`

- **[Description of change]**: Remove `planning_prompt` field from `AgentConfig`, its serialization in `to_dict()`, and deserialization in `from_dict()`.
- **[Rationale]**: Agent config must not reference memory or planning prompt.

#### [MODIFY] `tinycua_sdk/runner/runner.py`

- **[Description of change]**: Remove `planning_prompt` attribute assignment (e.g., `self.planning_prompt = getattr(..., "planning_prompt", ...)`).
- **[Rationale]**: Runner must not reference memory or planning prompt.

#### [MODIFY] `tinycua_sdk/modeling/user.py`

- **[Description of change]**: Remove `long_term_memory` parameter from `__init__` and the `self.memory` assignment.
- **[Rationale]**: Clean lingering memory references. (This file will be deleted in Stage 06, but imports must not break now.)

#### [MODIFY] `tinycua_sdk/modeling/personality.py`

- **[Description of change]**: Remove `long_term_memory` parameter from `__init__` and the `self.memory` assignment.
- **[Rationale]**: Clean lingering memory references.

#### [MODIFY] `tinycua_sdk/tools/__init__.py`

- **[Description of change]**: Remove all imports and `__all__` entries for `MemoryBackend`, `LocalMemoryBackend`, `HybridMemoryBackend`, and `get_memory_backend`.
- **[Rationale]**: SDK tools package must not export deleted memory symbols.

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `memory/` package | Remove | Entire package deleted |
| `tools/memory.py` | Remove | Memory backend abstractions deleted |
| `agent/agent.py` | Modify | Remove memory/planning_prompt parameters |
| `agent/executor.py` | Modify | Remove planning_prompt parameter |
| `agent/definition.py` | Modify | Remove planning_prompt parameter and property |
| `agent/config.py` | Modify | Remove planning_prompt from config |
| `runner/runner.py` | Modify | Remove planning_prompt attribute |
| `modeling/user.py` | Modify | Remove long_term_memory parameter |
| `modeling/personality.py` | Modify | Remove long_term_memory parameter |
| `tools/__init__.py` | Modify | Remove memory backend exports |

## Data Model Changes

No new types added. Existing memory types (`ShortTermMemory`, `LongTermMemory`, `ContextCompressor`, `CacheEntry`, `PromptCache`, `MemoryBackend`, `LocalMemoryBackend`, `HybridMemoryBackend`) are removed. Consumers must define their own memory strategy.

## API Changes

### Removed APIs

| Symbol | Location | Replacement |
|--------|----------|-------------|
| `ShortTermMemory` | `memory/short_term.py` | Consumer implements own context window |
| `LongTermMemory` | `memory/long_term.py` | Consumer implements own persistence |
| `ContextCompressor` | `memory/compression.py` | Consumer implements own compression |
| `CacheEntry` | `memory/cache.py` | Consumer implements own caching |
| `PromptCache` | `memory/cache.py` | Consumer implements own caching |
| `MemoryBackend` | `tools/memory.py` | Consumer implements own memory backend |
| `LocalMemoryBackend` | `tools/memory.py` | Consumer implements own memory backend |
| `HybridMemoryBackend` | `tools/memory.py` | Consumer implements own memory backend |
| `get_memory_backend` | `tools/memory.py` | Consumer implements own memory backend |
| `planning_prompt` | `agent/*.py` | Consumer injects planning via system prompt |

## Verification Plan

### Automated Tests

- [ ] Run `pytest` in `src/tinycua-sdk/` — all remaining tests pass.
- [ ] Run `make lint` — no import errors or undefined references.

### Manual Verification

- [ ] Confirm `tinycua_sdk/memory/` directory no longer exists.
- [ ] Confirm `tinycua_sdk/tools/memory.py` no longer exists.
- [ ] Confirm no `from tinycua_sdk.memory` or `import tinycua_sdk.memory` strings remain in `src/tinycua-sdk/tinycua_sdk/`.
- [ ] Confirm no `ShortTermMemory`, `LongTermMemory`, or `planning_prompt` references remain in `agent/`.

## Rollout Strategy

1. **Phase 1** (Deletion): Delete all files under `tinycua_sdk/memory/` and `tinucua_sdk/tools/memory.py`.
2. **Phase 2** (Cleanup): Remove memory imports and parameters from `agent/`, `runner/`, `modeling/`, and `tools/__init__.py`.
3. **Phase 3** (Verification): Run `make lint` and `make test` until clean.

## Dependencies

### External Dependencies

None removed or added.

### Internal Dependencies

- **Requires**: Stage 01, Stage 02, Stage 03, Stage 04
- **Blocks**: None (can proceed in parallel with Stages 06–07)

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Hidden memory imports in non-obvious files | Medium | Use `rg` to search entire `tinycua_sdk/` tree before and after deletion |
| Tests import deleted symbols | Low | Run `pytest` and delete/update broken tests |
| `runner.py` or `modeling/` files break due to missing memory params | Low | Remove parameters cleanly and run tests |

---

*Generated from spec.md and design.md*
*Last updated: 2026-04-29*
