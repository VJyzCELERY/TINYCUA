"""Target 2.5: Verify obsolete parameters raise TypeError."""

from tinycua_sdk import Agent


obsolete_params = [
    "system_prompt", "model", "provider", "base_url", "api_key",
    "mode", "backend_url", "backend_api_key", "backend_headers",
    "agent_id", "planning_prompt", "short_term_memory", "long_term_memory",
    "session_id", "sub_agents", "max_depth", "strip_thinking", "backend",
]

for param in obsolete_params:
    try:
        Agent(**{param: "test"})
        assert False, f"{param} should raise TypeError"
    except TypeError as e:
        assert param in str(e) or "unexpected keyword argument" in str(e)

print("PASS")
