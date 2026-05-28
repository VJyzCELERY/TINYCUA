# Tasks: Agent Convenience API for File Attachments

Implementation tasks for the Agent file attachment convenience API. Check off items as completed.

## TDD Phase (Tests First)

- [x] Write unit test: `test_run_empty_query_with_file_attachments` — empty str query + file_attachments produces `content: ""` + `attachments` key <!-- id: 0a -->
- [x] Write unit test: `test_run_str_query_with_file_attachments` — str query + file_attachments produces `content: str` + `attachments` key shape <!-- id: 0 -->
- [x] Write unit test: `test_run_str_query_without_file_attachments` — backward compatible (unchanged message dict) <!-- id: 1 -->
- [x] Write unit test: `test_run_content_parts_query_without_attachments` — `list[ContentPart]` query uses parts directly <!-- id: 2 -->
- [x] Write unit test: `test_run_content_parts_query_with_attachments_merges` — `list[ContentPart]` + file_attachments merges into single list <!-- id: 3 -->
- [x] Write unit test: `test_run_empty_file_attachments_is_noop` — `file_attachments=[]` same as `None` <!-- id: 4 -->
- [x] Write unit test: `test_run_invalid_file_attachments_raises_type_error` — non-FileAttachment items raise TypeError <!-- id: 5 -->
- [x] Write unit test: `test_run_none_in_file_attachments_raises_type_error` — None items raise TypeError <!-- id: 6 -->
- [x] Write unit test: `test_run_invalid_query_type_raises_type_error` — non-str, non-list[ContentPart] query raises TypeError <!-- id: 6a -->
- [x] Write unit test: `test_run_content_parts_query_rejects_non_content_part_items` — list query with non-ContentPart items raises TypeError <!-- id: 6b -->
- [x] Write unit test: `test_run_empty_content_parts_query_raises_type_error` — empty `list[ContentPart]` query (`[]`) raises TypeError <!-- id: 6c -->
- [x] Write unit test: `test_run_stream_with_file_attachments` — streaming works with file_attachments <!-- id: 7 -->
- [x] Write unit test: `test_run_preserves_message_history_with_attachments` — message history preserved <!-- id: 8 -->
- [x] Run unit tests — expect RED (failures) since implementation doesn't exist yet <!-- id: 9 -->
  ```bash
  cd src/tinycua-sdk && uv run pytest tests/unit/test_agent_file_attachments.py -v
  ```

## Implementation Phase

- [x] Modify `Agent.run()` signature in `tinycua_sdk/agent/agent.py` <!-- id: 10 -->
  - [x] Import `ContentPart` and `FileAttachment` from `tinycua_sdk.models.attachment`
  - [x] Extend `query` parameter type from `str` to `str | list[ContentPart]`
  - [x] Add `file_attachments: list[FileAttachment] | None = None` parameter
  - [x] Add validation: raise `TypeError` if `file_attachments` contains non-`FileAttachment` or `None` items
  - [x] Implement message construction logic per design decision tree:
    - `str` + no attachments → `{"role": "user", "content": query}`
    - `str` + attachments → `{"role": "user", "content": query, "attachments": file_attachments}`
    - `list[ContentPart]` + no attachments → `{"role": "user", "content": query}`
    - `list[ContentPart]` + attachments → merge into `list[ContentPart]`, no `attachments` key
  - [x] Treat `file_attachments=[]` same as `None` (no-op)
  - [x] Update `Agent.run()` docstring to document new parameters
- [x] Add public exports to `tinycua_sdk/__init__.py` <!-- id: 11 -->
  - [x] Add `from tinycua_sdk.models.attachment import ContentPart, FileAttachment` import
  - [x] Add `"ContentPart"` and `"FileAttachment"` to `__all__`

## Testing Phase

- [x] Run unit tests — expect GREEN (all pass) <!-- id: 12 -->
  ```bash
  cd src/tinycua-sdk && uv run pytest tests/unit/test_agent_file_attachments.py -v
  ```
- [x] Run existing Agent.run() unit tests — confirm no regressions <!-- id: 13 -->
  ```bash
  cd src/tinycua-sdk && uv run pytest tests/unit/test_agent_run.py -v
  ```
- [x] Run full unit test suite — confirm no regressions <!-- id: 14 -->
  ```bash
  cd src/tinycua-sdk && uv run pytest tests/unit/ -v
  ```
- [x] Run full integration test suite — confirm no regressions <!-- id: 14a -->
  ```bash
  cd src/tinycua-sdk && uv run pytest tests/integration/ -v
  ```
- [x] Run ruff lint and mypy type check — clean <!-- id: 14b -->

## Verification Phase

- [x] Verify `from tinycua_sdk import FileAttachment, ContentPart` works <!-- id: 15 -->
- [x] Verify backward compatibility: `agent.run("query")` produces identical results to current behavior <!-- id: 16 -->
- [x] Verify `agent.run("query", file_attachments=[img])` produces correct message shape <!-- id: 17 -->
- [x] Verify streaming: `agent.run("query", file_attachments=[img], stream=True)` yields events <!-- id: 18 -->

## Documentation Phase

- [x] Update `docs/spec.md` success criteria checkboxes if needed <!-- id: 19 -->
- [x] Update `docs/design.md` implementation phases checkboxes as completed <!-- id: 20 -->
- [x] Update `src/tinycua-sdk/README.md` with new Agent convenience API examples <!-- id: 20a -->
  - Show `from tinycua_sdk import Agent, FileAttachment, ContentPart`
  - Show `agent.run("Describe this", file_attachments=[attachment])` usage
  - Show optional `query: list[ContentPart]` usage
  - Show streaming example or note that `stream=True` is supported

## Review and Merge

- [x] Create pull request <!-- id: 21 -->
- [ ] Address review feedback <!-- id: 22 -->
- [ ] Merge to base branch <!-- id: 23 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-05-22*