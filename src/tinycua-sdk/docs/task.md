# Tasks: Agent Convenience API for File Attachments

Implementation tasks for the Agent file attachment convenience API. Check off items as completed.

## TDD Phase (Tests First)

- [ ] Write unit test: `test_run_empty_query_with_file_attachments` — empty str query + file_attachments produces `content: ""` + `attachments` key <!-- id: 0a -->
- [ ] Write unit test: `test_run_str_query_with_file_attachments` — str query + file_attachments produces `content: str` + `attachments` key shape <!-- id: 0 -->
- [ ] Write unit test: `test_run_str_query_without_file_attachments` — backward compatible (unchanged message dict) <!-- id: 1 -->
- [ ] Write unit test: `test_run_content_parts_query_without_attachments` — `list[ContentPart]` query uses parts directly <!-- id: 2 -->
- [ ] Write unit test: `test_run_content_parts_query_with_attachments_merges` — `list[ContentPart]` + file_attachments merges into single list <!-- id: 3 -->
- [ ] Write unit test: `test_run_empty_file_attachments_is_noop` — `file_attachments=[]` same as `None` <!-- id: 4 -->
- [ ] Write unit test: `test_run_invalid_file_attachments_raises_type_error` — non-FileAttachment items raise TypeError <!-- id: 5 -->
- [ ] Write unit test: `test_run_none_in_file_attachments_raises_type_error` — None items raise TypeError <!-- id: 6 -->
- [ ] Write unit test: `test_run_stream_with_file_attachments` — streaming works with file_attachments <!-- id: 7 -->
- [ ] Write unit test: `test_run_preserves_message_history_with_attachments` — message history preserved <!-- id: 8 -->
- [ ] Run unit tests — expect RED (failures) since implementation doesn't exist yet <!-- id: 9 -->
  ```bash
  cd src/tinycua-sdk && uv run pytest tests/unit/test_agent_file_attachments.py -v
  ```

## Implementation Phase

- [ ] Modify `Agent.run()` signature in `tinycua_sdk/agent/agent.py` <!-- id: 10 -->
  - [ ] Import `ContentPart` and `FileAttachment` from `tinycua_sdk.models.attachment`
  - [ ] Extend `query` parameter type from `str` to `str | list[ContentPart]`
  - [ ] Add `file_attachments: list[FileAttachment] | None = None` parameter
  - [ ] Add validation: raise `TypeError` if `file_attachments` contains non-`FileAttachment` or `None` items
  - [ ] Implement message construction logic per design decision tree:
    - `str` + no attachments → `{"role": "user", "content": query}`
    - `str` + attachments → `{"role": "user", "content": query, "attachments": file_attachments}`
    - `list[ContentPart]` + no attachments → `{"role": "user", "content": query}`
    - `list[ContentPart]` + attachments → merge into `list[ContentPart]`, no `attachments` key
  - [ ] Treat `file_attachments=[]` same as `None` (no-op)
  - [ ] Update `Agent.run()` docstring to document new parameters
- [ ] Add public exports to `tinycua_sdk/__init__.py` <!-- id: 11 -->
  - [ ] Add `from tinycua_sdk.models.attachment import ContentPart, FileAttachment` import
  - [ ] Add `"ContentPart"` and `"FileAttachment"` to `__all__`

## Testing Phase

- [ ] Run unit tests — expect GREEN (all pass) <!-- id: 12 -->
  ```bash
  cd src/tinycua-sdk && uv run pytest tests/unit/test_agent_file_attachments.py -v
  ```
- [ ] Run existing Agent.run() unit tests — confirm no regressions <!-- id: 13 -->
  ```bash
  cd src/tinycua-sdk && uv run pytest tests/unit/test_agent_run.py -v
  ```
- [ ] Run full unit test suite — confirm no regressions <!-- id: 14 -->
  ```bash
  cd src/tinycua-sdk && uv run pytest tests/unit/ -v
  ```

## Verification Phase

- [ ] Verify `from tinycua_sdk import FileAttachment, ContentPart` works <!-- id: 15 -->
- [ ] Verify backward compatibility: `agent.run("query")` produces identical results to current behavior <!-- id: 16 -->
- [ ] Verify `agent.run("query", file_attachments=[img])` produces correct message shape <!-- id: 17 -->
- [ ] Verify streaming: `agent.run("query", file_attachments=[img], stream=True)` yields events <!-- id: 18 -->

## Documentation Phase

- [ ] Update `docs/spec.md` success criteria checkboxes if needed <!-- id: 19 -->
- [ ] Update `docs/design.md` implementation phases checkboxes as completed <!-- id: 20 -->

## Review and Merge

- [ ] Create pull request <!-- id: 21 -->
- [ ] Address review feedback <!-- id: 22 -->
- [ ] Merge to base branch <!-- id: 23 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-05-22*