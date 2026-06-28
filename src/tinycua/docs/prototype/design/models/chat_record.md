# ChatRecord Model

**Status**: Code-only reconstruction

`ChatRecord` is an append-only audit transcript model extending `StateObject`. It stores role, record type, content, visibility, source/receiver node/session ids, origin record id, sequence, and metadata. Evidence: `src/tinycua/tinycua/models/chat_record.py:12-42`.

`TinyCUALoop._record_node_output()` appends assistant `ChatRecord`s to `root_session.chat_history` when content is non-empty. Evidence: `src/tinycua/tinycua/loops/tinycua_loop.py:245-255`.

Propagation can append internal propagation records when configured. Evidence: `src/tinycua/tinycua/loops/propagation.py:201-224`.
