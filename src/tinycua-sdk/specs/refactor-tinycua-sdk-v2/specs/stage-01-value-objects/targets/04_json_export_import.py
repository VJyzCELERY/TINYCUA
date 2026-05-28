"""Target 1.4: Verify to_json/from_json round-trip."""

from tinycua_sdk import LanguageModel

original = LanguageModel(
    model_name="json-test",
    temperature=0.7,
    max_tokens=256,
)

json_str = original.to_json()
restored = LanguageModel.from_json(json_str)

assert restored.model_name == original.model_name
assert restored.temperature == original.temperature
assert restored.max_tokens == original.max_tokens
print("PASS")
