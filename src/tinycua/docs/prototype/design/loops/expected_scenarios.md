# Expected Scenarios

**Status**: Code-only reconstruction

## Default factory scenario

`create_tinycua_agent().run(prompt)` appears to execute a bootstrapped terminal `ResponseNode` only. Evidence: `src/tinycua/tinycua/factory.py:45-55`, `src/tinycua/tests/integration/test_agent_factory.py:61-73`.

## Manually wired multi-node scenario

Tests show a manually assembled `QueryAnalyst -> InformationDigester -> Worker -> TaskCreate` pipeline. Evidence: `src/tinycua/tests/unit/test_pipeline_integration.py:200-285`.

## Streaming scenario

Streaming returns lifecycle events and SDK stream deltas through an async iterator. Evidence: `src/tinycua/tinycua/loops/tinycua_loop.py:403-589`, `src/tinycua/tests/integration/test_agent_factory.py:75-105`.

## CLI scenario

`tinycua run` executes in streaming mode to capture usage events and writes transcript artifacts. Evidence: `src/tinycua/tinycua/cli/run.py:212-243`.
