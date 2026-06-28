# Node Config

**Status**: Code-only reconstruction

## Observed implementation

`NodeConfigBase` groups node-level policy objects and customization hooks: instruction append, continuation append, retry append, propagation rule, tool policy, stream policy, retry policy, message policy, metadata, an optional node-local LLM client, and an optional monitor. Evidence: `src/tinycua/tinycua/config/node_config.py:156-186`.

## Policies

- `NodeMessagePolicy` controls whether session context and chat history are included, origin-record deduplication, and continuation role. Evidence: `src/tinycua/tinycua/config/node_config.py:15-32`.
- `NodeToolPolicy.resolve_tools()` starts with node tools, then includes no/selected/all outer tools, filtering denied outer tools and duplicates. Evidence: `src/tinycua/tinycua/config/node_config.py:34-106`.
- `NodeStreamPolicy` controls lifecycle event emission and final-response-only behavior. Evidence: `src/tinycua/tinycua/config/node_config.py:109-123`.
- `NodeRetryPolicy` controls max attempts, required tools/schema, custom validation, retry text, and exhaustion behavior. Evidence: `src/tinycua/tinycua/config/node_config.py:126-153`.

## Review note

The loop path calls `agent._call_llm()` directly, so retry/schema/classification behavior in direct `Node.__call__()` implementations may not run during normal loop execution. Evidence: `src/tinycua/tinycua/loops/tinycua_loop.py:624-652`.
