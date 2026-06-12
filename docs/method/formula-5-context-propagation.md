# Formula 5: Segmented Context Propagation

## Definition

Context flows between nodes using a segmented model that controls what information is durable vs. transient.

## Session Context Composition

For each node Nᵢ:

```
session_context(Nᵢ) = prior_context + input_segment + output_segment
```

Where:

- **prior\_context**: Context inherited from parent/ancestor nodes (immutable for this execution)
- **input\_segment**: Context specific to this node's task
- **output\_segment**: Context produced by this node's execution

## Propagation Rules

### On Node Termination

```
propagate_to_parent = session_context \ output_segment
forward_to_next_node = output_segment
```

The parent receives everything **except** the output segment. The next node receives **only** the output segment as its input.

### Transient Nodes

Nodes like QueryAnalyst and Worker are transient — their assembled context is **not** backward-propagated to the parent.

```
Nᵢ ∈ Transient ⟹ propagate_to_parent(Nᵢ) = ∅
```

Their output becomes durable only when a subsequent non-transient node ingests it as input.

## Deduplication

When merging contexts across propagation boundaries:

```
origin_record_id(r) ⟹ {
  keep earliest existing record   if duplicate found
  add record                      otherwise
}
```

This prevents information duplication when the same fact flows through multiple propagation paths.

## Example

```
Node₁ execution:
  session_context = [prior | input₁ | output₁]
  termination:
    parent ← [prior | input₁]        (output₁ excluded)
    Node₂ ← [output₁]                (becomes Node₂'s input_segment)

Node₂ execution:
  session_context = [output₁ | input₂ | output₂]
  termination:
    parent ← [output₁ | input₂]      (output₂ excluded)
    Node₃ ← [output₂]
```
