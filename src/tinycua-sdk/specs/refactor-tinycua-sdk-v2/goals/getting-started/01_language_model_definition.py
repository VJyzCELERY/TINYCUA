"""01 - Language Model Definition

Shows how to configure a LanguageModel with full OpenAI-compatible parameters.
The LanguageModel is a pure value object — no I/O, just configuration.
"""

from tinycua_sdk import LanguageModel

# ---------------------------------------------------------------------------
# 1. Minimal configuration (uses sensible defaults)
# ---------------------------------------------------------------------------
minimal_model = LanguageModel()
# Defaults:
#   provider="openai-compatible"
#   model_name="gpt-4o-mini"
#   base_url=None        # Will use provider default
#   api_key=""
#   temperature=1.0
#   max_tokens=None      # Let the provider decide
#   top_p=1.0
#   frequency_penalty=0.0
#   presence_penalty=0.0
#   response_format=None
#   system_prompt="You are a helpful assistant."

# ---------------------------------------------------------------------------
# 2. Local endpoint (e.g., LM Studio, Ollama, llama.cpp)
# ---------------------------------------------------------------------------
local_model = LanguageModel(
    provider="openai-compatible",
    model_name="qwen/qwen3.5-9b",
    base_url="http://localhost:1234/v1",
    api_key="dummy",  # Some local servers expect a non-empty key
    temperature=0.7,
    max_tokens=4096,
)

# ---------------------------------------------------------------------------
# 3. Cloud provider (OpenAI)
# ---------------------------------------------------------------------------
openai_model = LanguageModel(
    provider="openai",
    model_name="gpt-4o",
    api_key="${OPENAI_API_KEY}",  # Env var substitution supported
    temperature=0.5,
    max_tokens=8192,
    top_p=0.9,
    frequency_penalty=0.1,
    presence_penalty=0.1,
    response_format={"type": "json_object"},  # Structured output
    system_prompt="You are a terse, expert coding assistant.",
)

# ---------------------------------------------------------------------------
# 4. Serialization — share or persist the config
# ---------------------------------------------------------------------------
config_dict = local_model.to_dict()
json_string = local_model.to_json()

# Rehydrate later
reloaded = LanguageModel.from_dict(config_dict)

if __name__ == "__main__":
    print("Minimal model:", minimal_model.model_name)
    print("Local model base_url:", local_model.base_url)
    print("OpenAI model temperature:", openai_model.temperature)
    print("JSON export length:", len(json_string))
