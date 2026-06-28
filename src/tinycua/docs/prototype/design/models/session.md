# Session Model

**Status**: Code-only reconstruction

`Session` tracks execution state: `session_id`, `parent_id`, `session_config`, `input_context`, `chat_history`, `session_context`, `task`, and `todo`. Evidence: `src/tinycua/tinycua/models/session.py:15-40`.

The loop copies SDK messages into `root_session.input_context` and intentionally avoids duplicating user messages into chat history. Evidence: `src/tinycua/tinycua/loops/tinycua_loop.py:119-124`.

`compact_context()` delegates to the configured compaction strategy and replaces either all session context or a contiguous window with a summary. Evidence: `src/tinycua/tinycua/models/session.py:42-140`.
