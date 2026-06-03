# DigestedInformation

> **Package:** `tinycua.models.digested_information`
> **Status:** Target architecture

## Role

`DigestedInformation` captures the useful output from `TinyCUAInformationDigesterNode`.

Typical fields:

```text
DigestedInformation
  · context_summary
  · key_points
  · advisory_instructions
  · constraints
  · known_gaps
```

When InformationDigester is prepended by `TinyCUAResponseNode`, selected digest output
propagates back to the response node session.

## Related

- [`../tools/digester.md`](../tools/digester.md)
- [`../loops/node_queue.md`](../loops/node_queue.md)
