# Tasks: RouteMap and Top-Level QueryAnalyst

Implementation tasks for RouteMap and Top-Level QueryAnalyst. Check off items as completed.

## TDD Phase (Tests First)

- [ ] Write integration tests (defined in implementation-plan.md) <!-- id: 0 -->
  - [ ] Create tests/integration/test_query_analyst_integration.py
  - [ ] test_route_map_dispatches_to_handler
  - [ ] test_query_analyst_classifies_worker
  - [ ] test_query_analyst_mandatory_passthrough_precheck
  - [ ] test_query_analyst_e2e_worker_route
  - [ ] test_query_analyst_e2e_uncertain
  - [ ] test_query_analyst_e2e_passthrough
  - [ ] test_query_analyst_e2e_worker_reuse
  - [ ] test_query_analyst_e2e_invalid_label_retry
  - [ ] test_query_analyst_e2e_deduplication
  - [ ] test_query_analyst_queue_bootstrap
- [ ] Run integration tests — expect RED (failures) since no implementation yet <!-- id: 1 -->

## Implementation Phase

- [ ] Create classification models <!-- id: 2 -->
  - [ ] Create MandatoryPassthrough dataclass
  - [ ] Create QueryAnalystResponse dataclass
  - [ ] Add classification constants (passthrough, worker, uncertain)
  - [ ] Add Route dataclass
- [ ] Create RouteMap class <!-- id: 3 -->
  - [ ] Implement register() method
  - [ ] Implement dispatch() method with error handling
- [ ] Create TinyCUAQueryAnalystNode <!-- id: 4 -->
  - [ ] Initialize with classification labels
  - [ ] Implement mandatory_passthrough precheck
  - [ ] Implement find_existing_worker() helper
  - [ ] Implement route_passthrough handler
  - [ ] Implement route_worker handler with reuse/spawn logic
  - [ ] Implement route_uncertain handler
  - [ ] Implement on_complete for RouteMap dispatch
- [ ] Update DecisionNode base class <!-- id: 5 -->
  - [ ] Add optional route_map attribute
  - [ ] Update __init__ to accept route_map parameter
- [ ] Update TinyCUALoop queue bootstrap <!-- id: 6 -->
  - [ ] Replace StubNode with QueryAnalyst at queue front
  - [ ] Add QueryAnalyst deduplication check

## Testing Phase

- [ ] Run integration tests — expect GREEN (all pass) <!-- id: 7 -->
- [ ] Write unit tests for RouteMap <!-- id: 8 -->
  - [ ] test_route_map_register
  - [ ] test_route_map_dispatch_unknown_label
  - [ ] test_route_map_dispatch_calls_handler
- [ ] Write unit tests for QueryAnalyst <!-- id: 9 -->
  - [ ] test_query_analyst_init
  - [ ] test_query_analyst_classifies_passthrough
  - [ ] test_query_analyst_classifies_uncertain
  - [ ] test_query_analyst_stale_passthrough
  - [ ] test_query_analyst_worker_reuse
  - [ ] test_query_analyst_worker_spawn
  - [ ] test_query_analyst_invalid_label_retry
  - [ ] test_query_analyst_deduplication
  - [ ] test_query_analyst_preserves_input_query
  - [ ] test_query_analyst_check_mandatory_passthrough
  - [ ] test_query_analyst_find_existing_worker
  - [ ] test_query_analyst_route_passthrough
  - [ ] test_query_analyst_route_worker
  - [ ] test_query_analyst_route_uncertain
- [ ] Write unit tests for MandatoryPassthrough <!-- id: 10 -->
  - [ ] test_mandatory_passthrough_creation
  - [ ] test_mandatory_passthrough_stale_guard
- [ ] Run full test suite: `cd src/tinycua && uv run pytest` <!-- id: 11 -->

## Verification Phase

- [ ] Verify queue bootstrap with QueryAnalyst at front <!-- id: 12 -->
- [ ] Verify worker reuse logic with various queue states <!-- id: 13 -->
- [ ] Verify mandatory_passthrough precheck behavior <!-- id: 14 -->
- [ ] Test with mock LLM endpoint <!-- id: 15 -->

## Documentation Phase

- [ ] Update API documentation for new classes <!-- id: 16 -->
- [ ] Update design.md with implementation notes <!-- id: 17 -->
- [ ] Update changelog <!-- id: 18 -->
- [ ] Update spec.md success criteria checkboxes as tasks complete <!-- id: 19 -->

## Review and Merge

- [ ] Create pull request <!-- id: 20 -->
- [ ] Address review feedback <!-- id: 21 -->
- [ ] Merge to main branch <!-- id: 22 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-06-08 (ISSUE-001 fixed — test enumeration aligned with implementation plan)*