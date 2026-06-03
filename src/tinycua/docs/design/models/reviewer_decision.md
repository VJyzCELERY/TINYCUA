# ReviewerDecision

> **Package:** `tinycua.models.reviewer_decision`
> **Status:** Target architecture

## Role

Reviewer decision models capture `TinyCUAResultReviewerNode` output.

Common outcomes:

- accept
- retry
- replan
- open question / no terminal decision

Open question behavior keeps the relevant node active for continuation rather than
forcing a terminal result.

## Related

- [`../loops/node.md`](../loops/node.md)
- [`../loops/worker_concept.md`](../loops/worker_concept.md)
