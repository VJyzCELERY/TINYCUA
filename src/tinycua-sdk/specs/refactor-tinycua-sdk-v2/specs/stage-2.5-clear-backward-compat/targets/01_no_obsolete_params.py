"""Target 2.5.1: Verify Agent constructor has no backward-compat validation."""

from tinycua_sdk import Agent


obsolete_names = [
    "system_prompt", "model", "provider", "base_url", "api_key",
    "mode", "backend_url", "backend_api_key", "backend_headers",
    "agent_id", "planning_prompt", "short_term_memory", "long_term_memory",
    "session_id", "sub_agents", "max_depth", "strip_thinking", "backend",
]

for param in obsolete_names:
    try:
        Agent(**{param: "test"})
        assert False, f"{param} should raise TypeError"
    except TypeError:
        pass  # Standard Python behavior — no custom message

print("PASS")
