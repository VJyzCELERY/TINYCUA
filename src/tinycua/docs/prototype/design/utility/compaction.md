# Compaction Utility

**Status**: Code-only reconstruction

`CompactionStrategy` defines the abstract `compact(messages: list[dict]) -> dict` contract. Evidence: `src/tinycua/tinycua/compaction/strategy.py:8-34`.

`SimpleCompaction` is the default implementation. It is tool-less, can retain parent/fallback model config, returns an assistant-role summary dict, and wraps unknown errors in `CompactionError`. Evidence: `src/tinycua/tinycua/compaction/simple.py:11-94`.

The actual compaction agent call is stubbed by concatenating `role: content` strings. Evidence: `src/tinycua/tinycua/compaction/simple.py:96-118`.

`Session.compact_context()` delegates to the configured strategy and replaces context entries with the returned summary. Evidence: `src/tinycua/tinycua/models/session.py:42-140`.
