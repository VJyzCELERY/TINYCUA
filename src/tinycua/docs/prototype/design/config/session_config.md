# Session Config

**Status**: Code-only reconstruction

## Observed implementation

`SessionConfig` holds optional compaction strategy, max context messages, optional max context tokens, and metadata. Evidence: `src/tinycua/tinycua/config/session_config.py:13-27`.

`create_tinycua_agent()` applies a provided `SessionConfig` to the root `Session` and also stores it on `TinyCUALoop`. Evidence: `src/tinycua/tinycua/factory.py:47-54`.

`Session.compact_context()` consults `session_config.compaction_strategy`; if no strategy exists it returns `None`. Evidence: `src/tinycua/tinycua/models/session.py:42-64`.
