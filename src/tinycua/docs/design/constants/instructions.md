# Instruction and Continuation Constants

> **Status:** Target architecture

Each TinyCUA node has hardcoded instruction and continuation constants that define its
required behavior. User/config customization is append-only.

```text
final_instruction = HARD_CODED_NODE_INSTRUCTION + custom_instruction_append
final_continuation = HARD_CODED_NODE_CONTINUATION + custom_continuation_append
final_retry = HARD_CODED_NODE_RETRY_CONTINUATION + custom_retry_append
```

Constants should exist for:

- `TinyCUAQueryAnalystNode`
- `TinyCUAInformationDigesterNode`
- `TinyCUAWorkerNode`
- `TinyCUATaskAnalyzerNode`
- `TinyCUATaskAssessorNode`
- `TinyCUATaskExecutorNode`
- `TinyCUAResultReviewerNode`
- `TinyCUAResponseNode`

Internal continuations are assistant-role messages. Only actual external user input is
role `user`.

## Related

- [`../config/node_config.md`](../config/node_config.md)
- [`../loops/node.md`](../loops/node.md)
