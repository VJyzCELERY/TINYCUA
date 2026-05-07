"""Target 6.2: Verify to_json redacts api_key when requested."""

from tinycua_sdk import Agent, LanguageModel


a = Agent(
    llm_model=LanguageModel(api_key="secret123"),
)

json_redacted = a.to_json(redact_sensitive=True)
assert "secret123" not in json_redacted
assert "***" in json_redacted or "redact" in json_redacted.lower()

json_full = a.to_json(redact_sensitive=False)
assert "secret123" in json_full

print("PASS")
