"""Target 1.2: Create a LanguageModel with all OpenAI-compatible params."""

from tinycua_sdk import LanguageModel

m = LanguageModel(
    provider="openai",
    model_name="gpt-4o",
    api_key="${OPENAI_API_KEY}",
    temperature=0.5,
    max_tokens=8192,
    top_p=0.9,
    frequency_penalty=0.1,
    presence_penalty=0.1,
    response_format={"type": "json_object"},
    system_prompt="You are terse.",
)

assert m.provider == "openai"
assert m.model_name == "gpt-4o"
assert m.temperature == 0.5
assert m.max_tokens == 8192
assert m.top_p == 0.9
assert m.frequency_penalty == 0.1
assert m.presence_penalty == 0.1
assert m.response_format == {"type": "json_object"}
print("PASS")
