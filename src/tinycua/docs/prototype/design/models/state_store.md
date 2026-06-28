# State Store Model

**Status**: Code-only reconstruction

No dedicated state store abstraction was found in the prototype implementation.

State is stored in memory on `Session` and node instances. Evidence: `src/tinycua/tinycua/models/session.py:33-40`, `src/tinycua/tinycua/loops/node.py:110-138`.

Context serialization support exists through `StateObject`, but no persistent store layer is visible. Evidence: `src/tinycua/tinycua/models/state_object.py:35-90`.
