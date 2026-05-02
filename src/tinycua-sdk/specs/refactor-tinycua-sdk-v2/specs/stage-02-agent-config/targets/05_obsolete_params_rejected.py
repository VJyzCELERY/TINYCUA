"""Target 2.5: Verify obsolete parameters raise TypeError."""

from tinycua_sdk import Agent


obsolete_params = [
    "system_prompt", "model", "provider", "base_url", "api_key",
    "mode", "backend_url", "session_id", "sub_agents", "max_depth",
]

for param in obsolete_params:
    try:
        Agent(**{param: "test"})
        assert False, f"{param} should raise TypeError"
    except TypeError as e:
        assert param in str(e) or "unexpected keyword argument" in str(e)

print("PASS")
