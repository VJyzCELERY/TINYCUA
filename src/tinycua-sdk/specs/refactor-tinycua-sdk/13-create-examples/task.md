# Tasks: Stage 13 — Create Examples

Implementation tasks for Stage 13. Check off items as completed.

## Implementation Phase

- [ ] Create docs/examples/01_basic_agent.py <!-- id: 0 -->
  - [ ] Import Agent and LLMModel from tinycua_sdk
  - [ ] Construct agent with base_url, model_name, system_prompt
  - [ ] Call agent.run() and print response
- [ ] Create docs/examples/02_tools.py <!-- id: 1 -->
  - [ ] Define @tool search() and @tool summarize()
  - [ ] Add tools via add_tools()
  - [ ] Run agent with tool-enabled query
- [ ] Create docs/examples/03_skills.py <!-- id: 2 -->
  - [ ] Define skill markdown with YAML frontmatter
  - [ ] Load skill with Skill.load()
  - [ ] Add skill via add_skills()
- [ ] Create docs/examples/04_config_file.py <!-- id: 3 -->
  - [ ] Create agent.yaml with name, instructions, llm_model, tools
  - [ ] Load agent with Agent.from_config("agent.yaml")
  - [ ] Run and print response
- [ ] Create docs/examples/05_streaming.py <!-- id: 4 -->
  - [ ] Pass stream=True to agent.run()
  - [ ] Iterate async chunks and print
- [ ] Create docs/examples/06_sub_agents.py <!-- id: 5 -->
  - [ ] Create coordinator, researcher, writer agents
  - [ ] Compose via add_skills or equivalent mechanism
  - [ ] Run coordinator with delegation prompt
- [ ] Create docs/examples/07_custom_loop.py <!-- id: 6 -->
  - [ ] Implement ReActLoop extending BaseLoop
  - [ ] Override run() with reasoning + acting steps
  - [ ] Pass custom loop to Agent constructor

## Testing Phase

- [ ] Verify all examples are importable (no SyntaxError) <!-- id: 7 -->
- [ ] Verify no imports from deleted modules <!-- id: 8 -->
- [ ] Run `python -m py_compile` on each example <!-- id: 9 -->

## Verification Phase

- [ ] Confirm all examples are stateless (no session/memory/storage) <!-- id: 10 -->
- [ ] Confirm all examples use new API only <!-- id: 11 -->
- [ ] Confirm Example 07 extends BaseLoop (no ReactLoop) <!-- id: 12 -->

## Review and Merge

- [ ] Review examples against spec.md acceptance criteria <!-- id: 13 -->
- [ ] Merge to main branch <!-- id: 14 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement-plan` to execute these tasks*
*Last updated: 2026-04-29*
