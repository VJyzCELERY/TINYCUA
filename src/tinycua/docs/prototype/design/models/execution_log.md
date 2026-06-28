# Execution Log Model

**Status**: Code-only reconstruction

No dedicated `ExecutionLog` model was found in `src/tinycua/tinycua/models/` during code exploration.

Related surfaces:

- `ChatRecord` acts as an append-only node output/provenance record. Evidence: `src/tinycua/tinycua/models/chat_record.py:12-42`.
- CLI `agent.log` is written through `write_log_entry(...)` during `tinycua run`. Evidence: `src/tinycua/tinycua/cli/run.py:171-174`, `src/tinycua/tinycua/cli/run.py:210-224`.
