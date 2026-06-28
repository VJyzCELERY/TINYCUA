# Classification Model

**Status**: Code-only reconstruction

No dedicated classification dataclass was found. Classification is represented by strings and `DecisionResult`.

`DecisionResult` stores `route_label`, `analysis_response`, and `classification_response`. Evidence: `src/tinycua/tinycua/loops/node.py:78-94`.

`DecisionNode` stores allowed labels in `classification_labels` and matches labels by substring containment. Evidence: `src/tinycua/tinycua/loops/node.py:654-694`, `src/tinycua/tinycua/loops/node.py:743-784`.
