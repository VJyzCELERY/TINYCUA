# StateObject Model

**Status**: Code-only reconstruction

`StateObject` is a dataclass serialization base. Subclasses are registered by class name through `__init_subclass__`. Evidence: `src/tinycua/tinycua/models/state_object.py:13-34`.

It provides `to_dict()`, `from_dict()`, `to_json()`, and `from_json()`. Evidence: `src/tinycua/tinycua/models/state_object.py:35-90`.

Serialization recursively handles nested `StateObject`s, lists, and dicts. Evidence: `src/tinycua/tinycua/models/state_object.py:93-116`.
