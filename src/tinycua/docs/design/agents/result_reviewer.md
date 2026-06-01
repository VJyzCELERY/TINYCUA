# Result Reviewer AgentNode Spec Card

Source of truth: [`agent_node/result_reviewer.md`](../agent_node/result_reviewer.md). This is a navigation summary — for implementation details, see the source-of-truth doc.

## Summary

- Reviews `TaskExecutorState` or plain review input.
- Classification labels: `accept`, `retry`, `replan`.
- `escalate_user` is removed; indecision keeps reviewer active with an open question.
- Uses specialized minimal review toolset.
- Emits `ResultReviewerState` or remains active without terminal decision.

## Related

- [ResultReviewerState](../state/information.md#resultreviewerstate)
- [ReviewerDecision](../state/reviewer_decision.md)
- [TinyCUAWorker execution/review loop](../orchestration/worker.md#execution--review-loop)
