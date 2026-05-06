"""Target 1.6: Verify @tool-decorated function can be invoked."""

from tinycua_sdk import tool


@tool
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b


result = add.invoke(a=2, b=3)
assert result == 5

# Test with keyword args
result2 = add.invoke(a=10, b=20)
assert result2 == 30

print("PASS")
