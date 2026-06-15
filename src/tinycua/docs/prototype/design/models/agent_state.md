# Agent State Model

**Status**: Code-only reconstruction

No dedicated `AgentState` model was found in `src/tinycua/tinycua/models/` during code exploration.

The closest implemented state container is `Session`, which holds input context, chat history, reusable session context, task, and todo. Evidence: `src/tinycua/tinycua/models/session.py:15-40`.

SDK-level agent configuration/state is represented by `tinycua_sdk.agent.AgentConfig`. Evidence: `src/tinycua-sdk/tinycua_sdk/agent/config.py:26-49`.
