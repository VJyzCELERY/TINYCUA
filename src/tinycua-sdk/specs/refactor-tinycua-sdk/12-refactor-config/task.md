# Tasks: Stage 12 — Refactor Core Config

Implementation tasks for Stage 12. Check off items as completed.

## Implementation Phase

- [ ] Remove `memory` and `session` fields from `SDKConfig` <!-- id: 0 -->
- [ ] Remove `environment` field from `SDKConfig` <!-- id: 1 -->
- [ ] Add `model_config = ConfigDict(frozen=True)` to `LLMConfig` <!-- id: 2 -->
- [ ] Add `model_config = ConfigDict(frozen=True)` to `LoopConfig` <!-- id: 3 -->
- [ ] Add `model_config = ConfigDict(frozen=True)` to `SkillsConfig` <!-- id: 4 -->
- [ ] Add `model_config = ConfigDict(frozen=True)` to `SDKConfig` <!-- id: 5 -->
- [ ] Add `to_dict()` and `from_dict()` to `LLMConfig` <!-- id: 6 -->
- [ ] Add `to_dict()` and `from_dict()` to `LoopConfig` <!-- id: 7 -->
- [ ] Add `to_dict()` and `from_dict()` to `SkillsConfig` <!-- id: 8 -->
- [ ] Add `to_dict()`, `from_dict()`, `from_yaml()`, and `from_json()` to `SDKConfig` <!-- id: 9 -->
- [ ] Ensure required imports (`yaml`, `json`, `Path`, `SecretStr`, `ConfigDict`) are present <!-- id: 10 -->

## Testing Phase

- [ ] Unit tests for `LLMConfig` serialization round-trip <!-- id: 11 -->
- [ ] Unit tests for `LoopConfig` serialization round-trip <!-- id: 12 -->
- [ ] Unit tests for `SkillsConfig` serialization round-trip <!-- id: 13 -->
- [ ] Unit tests for `SDKConfig` serialization round-trip <!-- id: 14 -->
- [ ] Unit tests for `SDKConfig.from_yaml()` loading <!-- id: 15 -->
- [ ] Unit tests for `SDKConfig.from_json()` loading <!-- id: 16 -->
- [ ] Run full `pytest` suite and fix breakages <!-- id: 17 -->

## Verification Phase

- [ ] Confirm `SDKConfig` has no `memory`, `session`, or `environment` fields <!-- id: 18 -->
- [ ] Confirm `LoopConfig` has no `type` field <!-- id: 19 -->
- [ ] Confirm all config classes are frozen <!-- id: 20 -->
- [ ] Confirm `from_env()` is updated if present (spec mentions it) <!-- id: 21 -->

## Documentation Phase

- [ ] Update module docstrings if needed <!-- id: 22 -->

## Review and Merge

- [ ] Create pull request <!-- id: 23 -->
- [ ] Address review feedback <!-- id: 24 -->
- [ ] Merge to main branch <!-- id: 25 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement-plan` to execute these tasks*
*Last updated: 2026-04-29*
