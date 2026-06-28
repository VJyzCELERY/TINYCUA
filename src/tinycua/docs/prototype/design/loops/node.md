# Node

**Status**: Code-only reconstruction

## Base responsibilities

`Node` stores `node_id`, config, session, parent, terminal flag, and instruction text. Evidence: `src/tinycua/tinycua/loops/node.py:96-138`.

`ensure_session()` reuses an existing session, adopts a parent node session when possible, or attaches the provided root/parent session. Evidence: `src/tinycua/tinycua/loops/node.py:139-169`.

`build_instruction()` combines override or static instruction with configurable append text. Evidence: `src/tinycua/tinycua/loops/node.py:171-193`.

`record_output()` writes a `SessionContextEntry(segment="output")` to the node session. Evidence: `src/tinycua/tinycua/loops/node.py:492-506`.

## ProcessNode and DecisionNode

Direct `ProcessNode.__call__()` performs build, validation, LLM call, retry, record, and propagate. Evidence: `src/tinycua/tinycua/loops/node.py:582-651`.

Direct `DecisionNode.__call__()` performs an analysis call and a classification call with classification retry. Evidence: `src/tinycua/tinycua/loops/node.py:786-876`.

The normal loop path currently bypasses these direct call methods. Evidence: `src/tinycua/tinycua/loops/tinycua_loop.py:624-652`.
