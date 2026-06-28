# Base Loop Integration

**Status**: Code-only reconstruction

`TinyCUALoop` subclasses SDK `BaseLoop`. Evidence: `src/tinycua/tinycua/loops/tinycua_loop.py:35`.

The SDK `Agent` accepts a configured loop and delegates `Agent.run()` to `loop.run(...)`. Evidence: `src/tinycua-sdk/tinycua_sdk/agent/agent.py:47-84`, `src/tinycua-sdk/tinycua_sdk/agent/agent.py:229-243`.

The SDK `BaseLoop` remains a standard tool-calling loop with max iterations and tool-call processing. Evidence: `src/tinycua-sdk/tinycua_sdk/agent/loop.py:21-152`.

TinyCUA replaces that default loop behavior with node-queue execution. Evidence: `src/tinycua/tinycua/loops/tinycua_loop.py:94-138`.
