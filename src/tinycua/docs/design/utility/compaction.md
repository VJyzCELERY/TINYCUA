# CompactionStrategy

> **Status:** Target architecture

Compaction is session-level behavior selected through `SessionConfig`, but the
compaction strategy class owns compaction behavior and configuration.

```text
SessionConfig
  · compaction_strategy
```

TinyCUA has root and per-node sessions. Compaction should apply to the session whose
`session_context` is being mutated. `chat_history` remains an audit trail and should not
be destructively compacted.

## Strategy Contract

```text
CompactionStrategy
  · compact(messages: list[dict]) → dict
```

Input is a list of message dicts, usually a session's `session_context` or a node-selected
subset of that context.

Output is exactly one assistant-role message:

```text
{"role": "assistant", "content": "<summary of compacted context>"}
```

Compaction summarizes information into one reusable context message. It does not create
the continuation prompt for the next LLM call; continuation is node responsibility.

## Internal Agent Exception

Normal TinyCUA node execution does not create internal SDK Agents inside
`TinyCUALoop`. `CompactionStrategy` is the explicit exception: a strategy may use its own
internal Agent, direct model call, heuristic summarizer, or any other implementation.

`SessionConfig` selects the strategy. The strategy class is the authority for its own
configuration, including whether it uses an Agent, which instructions it uses, and what
model/tools it requires.

## SimpleCompaction

`SimpleCompaction` is the default/simple compaction strategy.

```text
SimpleCompaction extends CompactionStrategy
```

Behavior:

1. Inherit parent SDK Agent configuration when available, especially language model and
   provider configuration.
2. Use a documented default fallback configuration when no parent Agent/config exists.
3. Run a small compaction Agent over the selected session messages.
4. Use no tools.
5. Use a simple system instruction: it is a compaction agent.
6. Use a simple assistant-role continuation prompt: summarize the provided session into
   one compact reusable summary.
7. Return the compaction Agent's final response as one assistant-role message:

   ```text
   {"role": "assistant", "content": response}
   ```

The compaction Agent receives selected session context as `messages`. The caller/node is
responsible for deciding which messages to pass, including whether to exclude static
system prompts or include any dynamic system context needed for the summary.

## System Messages

Compaction should generally avoid compacting system-role messages. Nodes/callers decide
what context to pass to the strategy. A node may pass additional dynamic compaction
instructions separately if the strategy supports them, but the compaction target should
usually be assistant/user/tool context rather than static system prompts.

## Related

- [`../config/session_config.md`](../config/session_config.md)
- [`../models/session.md`](../models/session.md)
