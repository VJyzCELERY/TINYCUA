# Information Digester Node

**Status**: Code-only reconstruction

`TinyCUAInformationDigesterNode` is a `ProcessNode` intended to produce `DigestedInformation` for downstream nodes. Evidence: `src/tinycua/tinycua/loops/information_digester.py:30-44`.

Direct `__call__()` extracts the original query, calls the parent process-node lifecycle, parses response content into `DigestedInformation`, and stores it in `_current_digest`. Evidence: `src/tinycua/tinycua/loops/information_digester.py:70-89`.

Parsing tries JSON first, then falls back to raw content as `context_summary`, and empty content becomes `DigestedInformation.fallback(...)`. Evidence: `src/tinycua/tinycua/loops/information_digester.py:91-128`.

The digester always creates a fresh session when one is not already attached. Evidence: `src/tinycua/tinycua/loops/information_digester.py:130-150`.

Review note: the loop path does not call this `__call__()`, so digest parsing may not occur during normal loop execution. Evidence: `src/tinycua/tinycua/loops/tinycua_loop.py:624-652`.
