"""Tool.invoke() type coercion for local-model string args.

Local models routinely emit ints/bools/numbers as strings (``"7"`` for an
``integer`` param). Without coercion this crashes typed tools
(``'<' not supported between str and int``). These tests pin coercion for
every supported scalar/array/object type plus passthrough and error cases.
"""

# NOTE: deliberately NO `from __future__ import annotations` — PEP 563 would
# turn `n: int` into the string "int", which the @tool decorator's annotation
# introspection would then misclassify. Real tool modules keep real type
# objects as annotations.

import pytest

from tinycua_sdk.tools.decorators import Tool, _coerce_arg, tool


# --- _coerce_arg unit cases ----------------------------------------------


def test_coerce_integer_from_string() -> None:
    assert _coerce_arg("7", {"type": "integer"}) == 7
    assert _coerce_arg(" 8 ", {"type": "integer"}) == 8
    assert _coerce_arg(7.0, {"type": "integer"}) == 7
    assert _coerce_arg(True, {"type": "integer"}) == 1


def test_coerce_number_from_string() -> None:
    assert _coerce_arg("3.5", {"type": "number"}) == 3.5
    assert _coerce_arg(7, {"type": "number"}) == 7.0


def test_coerce_boolean_from_string() -> None:
    assert _coerce_arg("true", {"type": "boolean"}) is True
    assert _coerce_arg("True", {"type": "boolean"}) is True
    assert _coerce_arg("1", {"type": "boolean"}) is True
    assert _coerce_arg("false", {"type": "boolean"}) is False
    assert _coerce_arg("0", {"type": "boolean"}) is False
    assert _coerce_arg(1, {"type": "boolean"}) is True
    assert _coerce_arg(0, {"type": "boolean"}) is False


def test_coerce_string_from_scalar() -> None:
    assert _coerce_arg(7, {"type": "string"}) == "7"
    assert _coerce_arg(3.5, {"type": "string"}) == "3.5"
    assert _coerce_arg(True, {"type": "string"}) == "True"
    assert _coerce_arg("already", {"type": "string"}) == "already"


def test_coerce_array_from_json_string() -> None:
    assert _coerce_arg('["a", "b"]', {"type": "array"}) == ["a", "b"]
    assert _coerce_arg(["x"], {"type": "array"}) == ["x"]


def test_coerce_object_from_json_string() -> None:
    assert _coerce_arg('{"x": 1}', {"type": "object"}) == {"x": 1}
    assert _coerce_arg({"y": 2}, {"type": "object"}) == {"y": 2}


def test_coerce_none_passthrough() -> None:
    assert _coerce_arg(None, {"type": "integer"}) is None


def test_coerce_unknown_type_passthrough() -> None:
    assert _coerce_arg("x", {"type": "weird"}) == "x"


def test_coerce_nullable_union_picks_non_null() -> None:
    assert _coerce_arg("5", {"type": ["integer", "null"]}) == 5
    assert _coerce_arg(None, {"type": ["integer", "null"]}) is None


def test_coerce_uncoercible_integer_passes_through() -> None:
    """An uncoercible value is returned unchanged so the tool can report it."""
    assert _coerce_arg("abc", {"type": "integer"}) == "abc"


def test_coerce_uncoercible_boolean_passes_through() -> None:
    assert _coerce_arg("maybe", {"type": "boolean"}) == "maybe"


# --- Tool.invoke() integration ------------------------------------------


def _int_tool() -> Tool:
    @tool
    def add_one(n: int) -> int:
        """Add one to n."""
        return n + 1

    return add_one


def test_invoke_coercion_applied_for_string_int() -> None:
    """A string arg is coerced to int before the function runs."""
    t = _int_tool()
    assert t.invoke(n="41") == 42
    assert t.invoke(n=40) == 41  # already-correct type passes through


def test_invoke_skips_coercion_when_no_schema() -> None:
    """A Tool built without a properties schema passes args through."""
    bare = Tool(name="echo", description="echo", parameters={}, _callable=lambda **kw: kw)
    assert bare.invoke(x="7") == {"x": "7"}


def test_invoke_coercion_uncoercible_passes_through() -> None:
    """An uncoercible arg passes through; the tool reports its own error."""
    t = _int_tool()
    # "not-a-number" can't coerce to int → passed as-is → add_one raises.
    with pytest.raises(TypeError):
        t.invoke(n="not-a-number")