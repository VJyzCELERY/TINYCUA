"""Target 1.7: Verify manual Tool construction works."""

from tinycua_sdk import Tool


dynamic = Tool(
    name="reverse_string",
    description="Reverse a string.",
    parameters={
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    },
)

schema = dynamic.to_config()
assert schema["function"]["name"] == "reverse_string"
assert schema["function"]["description"] == "Reverse a string."
print("PASS")
