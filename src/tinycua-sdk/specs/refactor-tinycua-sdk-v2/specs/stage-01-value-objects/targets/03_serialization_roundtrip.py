"""Target 1.3: Verify to_dict/from_dict round-trip preserves all data."""

from tinycua_sdk import LanguageModel

original = LanguageModel(
    model_name="test-model",
    temperature=0.3,
    max_tokens=512,
    top_p=0.8,
    frequency_penalty=0.2,
    presence_penalty=0.1,
    response_format={"type": "json_object"},
)

restored = LanguageModel.from_dict(original.to_dict())

assert restored.model_name == original.model_name
assert restored.temperature == original.temperature
assert restored.max_tokens == original.max_tokens
assert restored.top_p == original.top_p
assert restored.frequency_penalty == original.frequency_penalty
assert restored.presence_penalty == original.presence_penalty
assert restored.response_format == original.response_format
print("PASS")
