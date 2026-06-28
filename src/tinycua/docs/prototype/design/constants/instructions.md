# Instructions

**Status**: Code-only reconstruction

## Observed implementation

Instructions are embedded as module constants or constructor defaults in node modules, then merged through `Node.build_instruction()` and `SystemPromptBuilder`.

Evidence:

- Base instruction merge and custom append: `src/tinycua/tinycua/loops/node.py:171-193`.
- Query analyst instruction: `src/tinycua/tinycua/loops/query_analyst.py:23-28`.
- Information digester instruction: `src/tinycua/tinycua/loops/information_digester.py:22-27`.
- Worker instruction: `src/tinycua/tinycua/loops/worker.py:15-20`.
- Task create instruction: `src/tinycua/tinycua/loops/task_create.py:15-20`.
- Response node instruction: `src/tinycua/tinycua/loops/response_node.py:42-47`.

## Loop integration

`TinyCUALoop._build_node_messages()` builds a system message from `node.build_instruction(override_instructions)`. Evidence: `src/tinycua/tinycua/loops/tinycua_loop.py:738-746`.
