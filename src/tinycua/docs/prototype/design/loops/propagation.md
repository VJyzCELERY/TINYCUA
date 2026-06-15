# Propagation

**Status**: Code-only reconstruction

`PropagationRule` controls where chat history, session context, token usage, and failures propagate. Evidence: `src/tinycua/tinycua/loops/propagation.py:16-37`.

Predefined profiles exist for transient, natural termination, mid-progress, and selected internal output behavior. Evidence: `src/tinycua/tinycua/loops/propagation.py:39-73`.

`propagate_on_termination()` separates `prior`, `input`, and `output` entries. Only prior/input propagate upward; output entries are excluded and forwarded separately. Evidence: `src/tinycua/tinycua/loops/propagation.py:157-199`.

`forward_output_to_next()` returns session context entries whose segment is `output`. Evidence: `src/tinycua/tinycua/loops/propagation.py:235-259`.

`finalize_terminal_output()` commits terminal output entries to root session context and returns the first output content. Evidence: `src/tinycua/tinycua/loops/propagation.py:262-303`.
