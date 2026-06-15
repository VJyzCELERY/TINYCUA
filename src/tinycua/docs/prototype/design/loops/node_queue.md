# NodeQueue

**Status**: Code-only reconstruction

`NodeQueue` is a list-backed scheduler where `items[0]` is current. Evidence: `src/tinycua/tinycua/loops/node_queue.py:25-48`.

## Behaviors

- `input_for_current()` and `set_input()` track input by node id. Evidence: `src/tinycua/tinycua/loops/node_queue.py:58-75`.
- `advance()` calls current `propagate()`, forwards output entries to the next node, pops current, and cleans input. Evidence: `src/tinycua/tinycua/loops/node_queue.py:77-126`.
- `spawn_after_current()` inserts nodes after current. Evidence: `src/tinycua/tinycua/loops/node_queue.py:128-146`.
- `clear_after_current()` removes future nodes and their inputs. Evidence: `src/tinycua/tinycua/loops/node_queue.py:147-160`.
- `suspend_current_and_prepend()` prepends nodes without propagating current. Evidence: `src/tinycua/tinycua/loops/node_queue.py:162-184`.
- `ensure_terminal()` appends a terminal node when needed. Evidence: `src/tinycua/tinycua/loops/node_queue.py:186-200`.

Tests cover queue behavior in `src/tinycua/tests/unit/test_node_queue.py:49-242`.
