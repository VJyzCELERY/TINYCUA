# Formula 6: Context Compaction

## Compaction Trigger

Context compaction is triggered when the session context exceeds configured limits:

```
compact(session_context)  ⟺  len(session_context) > max_context_messages
                           OR  token_count(session_context) > max_context_tokens
```

Nodes call `session.compact_context()` when these thresholds would be exceeded.

## Compaction Strategy

The `CompactionStrategy` produces exactly one assistant-role summary message:

```
compact(messages: list[dict]) -> {"role": "assistant", "content": "<summary>"}
```

The default implementation `SimpleCompaction`:
1. Receives parent SDK Agent config snapshot during setup
2. Runs a small compaction Agent over selected session messages
3. No tools available to the compaction agent
4. Returns final response as one assistant-role message

## Invariants

| Property | Description |
|----------|-------------|
| **Immutable audit trail** | `chat_history` is never modified or deleted. It serves as the ground-truth record of all interactions. |
| **Mutable working context** | `session_context` is the compactable working state. Summaries replace raw messages. |
| **Node-triggered** | Nodes explicitly call `session.compact_context()` when thresholds are exceeded. |
| **Single summary** | Compaction produces exactly ONE assistant-role message, not multiple summaries. |
| **System message exclusion** | Compaction excludes system-role messages by default. |

## Compaction is Not Background

Unlike the previous design, compaction is NOT a background system process. It is triggered explicitly by nodes when they detect that `max_context_messages` or `max_context_tokens` would be exceeded. The node decides what context to pass to the compaction strategy.

## Exception

`CompactionStrategy` is the ONLY exception that may create its own internal SDK Agent inside `TinyCUALoop`. This is required for the LLM-based summarization.
