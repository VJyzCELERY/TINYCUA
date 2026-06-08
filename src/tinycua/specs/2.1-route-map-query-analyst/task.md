# Tasks: RouteMap and Top-Level QueryAnalyst

Implementation tasks for RouteMap and Top-Level QueryAnalyst. Check off items as completed.

## TDD Phase (Tests First)

- [x] Write integration tests (defined in implementation-plan.md) <!-- id: 0 -->
  - [x] Create tests/integration/test_query_analyst_integration.py
  - [x] test_route_map_dispatches_to_handler
  - [x] test_query_analyst_classifies_worker
  - [x] test_query_analyst_mandatory_passthrough_precheck
  - [x] test_query_analyst_e2e_worker_route
  - [x] test_query_analyst_e2e_uncertain
  - [x] test_query_analyst_e2e_passthrough
  - [x] test_query_analyst_e2e_worker_reuse
  - [x] test_query_analyst_e2e_invalid_label_retry
  - [x] test_query_analyst_e2e_deduplication
  - [x] test_query_analyst_queue_bootstrap
- [x] Run integration tests — expect RED (failures) since no implementation yet <!-- id: 1 -->

## Implementation Phase

- [x] Create classification models <!-- id: 2 -->
  - [x] Create MandatoryPassthrough dataclass
  - [x] Create QueryAnalystResponse dataclass
  - [x] Add classification constants (passthrough, worker, uncertain)
  - [x] Add Route dataclass
- [x] Create RouteMap class <!-- id: 3 -->
  - [x] Implement register() method
  - [x] Implement dispatch() method with error handling
- [x] Create TinyCUAQueryAnalystNode <!-- id: 4 -->
  - [x] Initialize with classification labels
  - [x] Implement mandatory_passthrough precheck
  - [x] Implement find_existing_worker() helper
  - [x] Implement route_passthrough handler
  - [x] Implement route_worker handler with reuse/spawn logic
  - [x] Implement route_uncertain handler
  - [x] Implement on_complete for RouteMap dispatch
- [x] Update DecisionNode base class <!-- id: 5 -->
  - [x] Add optional route_map attribute
  - [x] Update __init__ to accept route_map parameter
- [x] Update TinyCUALoop queue bootstrap <!-- id: 6 -->
  - [x] Replace StubNode with QueryAnalyst at queue front
  - [x] Add QueryAnalyst deduplication check

## Testing Phase

- [x] Run integration tests — expect GREEN (all pass) <!-- id: 7 -->
- [x] Write unit tests for RouteMap <!-- id: 8 -->
  - [x] test_route_map_register
  - [x] test_route_map_dispatch_unknown_label
  - [x] test_route_map_dispatch_calls_handler
- [x] Write unit tests for QueryAnalyst <!-- id: 9 -->
  - [x] test_query_analyst_init
  - [x] test_query_analyst_classifies_passthrough
  - [x] test_query_analyst_classifies_uncertain
  - [x] test_query_analyst_stale_passthrough
  - [x] test_query_analyst_worker_reuse
  - [x] test_query_analyst_worker_spawn
  - [x] test_query_analyst_invalid_label_retry
  - [x] test_query_analyst_deduplication
  - [x] test_query_analyst_preserves_input_query
  - [x] test_query_analyst_check_mandatory_passthrough
  - [x] test_query_analyst_find_existing_worker
  - [x] test_query_analyst_route_passthrough
  - [x] test_query_analyst_route_worker
  - [x] test_query_analyst_route_uncertain
- [x] Write unit tests for MandatoryPassthrough <!-- id: 10 -->
  - [x] test_mandatory_passthrough_creation
  - [x] test_mandatory_passthrough_stale_guard
- [x] Run full test suite: `cd src/tinycua && uv run pytest` <!-- id: 11 -->

## Verification Phase

- [x] Verify queue bootstrap with QueryAnalyst at front <!-- id: 12 -->
- [x] Verify worker reuse logic with various queue states <!-- id: 13 -->
- [x] Verify mandatory_passthrough precheck behavior <!-- id: 14 -->
- [x] Test with mock LLM endpoint <!-- id: 15 -->

## Documentation Phase

- [x] Update API documentation for new classes <!-- id: 16 -->
- [x] Update design.md with implementation notes <!-- id: 17 -->
- [x] Update changelog <!-- id: 18 -->
- [x] Update spec.md success criteria checkboxes as tasks complete <!-- id: 19 -->

## Review and Merge

- [x] Create pull request <!-- id: 20 -->
- [x] Address review feedback <!-- id: 21 -->
- [ ] Merge to main branch <!-- id: 22 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-06-08 (ISSUE-001 fixed — test enumeration aligned with implementation plan)*
