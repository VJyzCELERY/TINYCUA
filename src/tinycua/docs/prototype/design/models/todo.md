# Todo Model

**Status**: Code-only reconstruction

`TodoItem` stores description, status (`pending` or `done`), order, and metadata. Evidence: `src/tinycua/tinycua/models/todo.py:9-23`.

`Todo` stores ordered items with a maximum count, appends pending items, marks items done, and returns the next pending item. Evidence: `src/tinycua/tinycua/models/todo.py:26-98`.

`Session.todo` is currently typed as `list[dict]`, not this `Todo` class. Evidence: `src/tinycua/tinycua/models/session.py:39-40`.
