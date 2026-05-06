"""Target 1.1: Create a minimal LanguageModel with defaults."""

from tinycua_sdk import LanguageModel

m = LanguageModel(model_name="qwen/qwen3.5-9b")

assert m.provider == "openai-compatible"
assert m.model_name == "qwen/qwen3.5-9b"
assert m.temperature == 1.0
assert m.max_tokens is None
print("PASS")
