"""Unit tests for StateObject base class."""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import pytest


def test_to_dict_returns_all_fields() -> None:
    """to_dict() returns a dictionary with all dataclass fields."""
    from tinycua.models import StateObject

    @dataclass
    class SampleState(StateObject):
        name: str = "test"
        count: int = 0
        tags: list[str] = field(default_factory=list)

    obj = SampleState(name="hello", count=5, tags=["a", "b"])
    result = obj.to_dict()

    assert result == {"name": "hello", "count": 5, "tags": ["a", "b"]}


def test_to_dict_handles_nested_state_object() -> None:
    """to_dict() recursively serializes nested StateObject instances."""
    from tinycua.models import StateObject

    @dataclass
    class Inner(StateObject):
        value: str = ""

    @dataclass
    class Outer(StateObject):
        inner: Inner = field(default_factory=Inner)
        label: str = ""

    obj = Outer(inner=Inner(value="nested"), label="outer")
    result = obj.to_dict()

    assert result == {"inner": {"value": "nested"}, "label": "outer"}


def test_from_dict_reconstructs_object() -> None:
    """from_dict() reconstructs a typed object from a dictionary."""
    from tinycua.models import StateObject

    @dataclass
    class SampleState(StateObject):
        name: str = ""
        count: int = 0

    data = {"name": "hello", "count": 42}
    obj = SampleState.from_dict(data)

    assert obj.name == "hello"
    assert obj.count == 42


def test_from_dict_handles_nested_state_object() -> None:
    """from_dict() recursively deserializes nested StateObject instances."""
    from tinycua.models import StateObject

    @dataclass
    class Inner(StateObject):
        value: str = ""

    @dataclass
    class Outer(StateObject):
        inner: Inner = field(default_factory=Inner)
        label: str = ""

    data = {"inner": {"value": "nested"}, "label": "outer"}
    obj = Outer.from_dict(data)

    assert isinstance(obj.inner, Inner)
    assert obj.inner.value == "nested"
    assert obj.label == "outer"


def test_round_trip_dict() -> None:
    """Object survives to_dict() -> from_dict() round-trip."""
    from tinycua.models import StateObject

    @dataclass
    class SampleState(StateObject):
        name: str = ""
        items: list[int] = field(default_factory=list)

    original = SampleState(name="test", items=[1, 2, 3])
    restored = SampleState.from_dict(original.to_dict())

    assert restored.name == original.name
    assert restored.items == original.items


def test_to_json_returns_valid_json() -> None:
    """to_json() returns a valid JSON string."""
    from tinycua.models import StateObject

    @dataclass
    class SampleState(StateObject):
        name: str = ""
        count: int = 0

    obj = SampleState(name="test", count=5)
    json_str = obj.to_json()

    # Verify it's valid JSON
    parsed = json.loads(json_str)
    assert parsed == {"name": "test", "count": 5}


def test_from_json_reconstructs_object() -> None:
    """from_json() reconstructs a typed object from a JSON string."""
    from tinycua.models import StateObject

    @dataclass
    class SampleState(StateObject):
        name: str = ""
        count: int = 0

    json_str = '{"name": "hello", "count": 42}'
    obj = SampleState.from_json(json_str)

    assert obj.name == "hello"
    assert obj.count == 42


def test_round_trip_json() -> None:
    """Object survives to_json() -> from_json() round-trip."""
    from tinycua.models import StateObject

    @dataclass
    class SampleState(StateObject):
        name: str = ""
        items: list[int] = field(default_factory=list)

    original = SampleState(name="test", items=[1, 2, 3])
    restored = SampleState.from_json(original.to_json())

    assert restored.name == original.name
    assert restored.items == original.items


def test_from_dict_missing_required_field_raises() -> None:
    """from_dict() raises ValueError for missing required fields."""
    from tinycua.models import StateObject

    @dataclass
    class SampleState(StateObject):
        required_field: str = ""

    with pytest.raises(ValueError, match="required_field"):
        SampleState.from_dict({})


def test_from_json_invalid_json_raises() -> None:
    """from_json() raises json.JSONDecodeError for invalid JSON."""
    from tinycua.models import StateObject

    @dataclass
    class SampleState(StateObject):
        name: str = ""

    with pytest.raises(json.JSONDecodeError):
        SampleState.from_json("not valid json")


def test_round_trip_nested_json() -> None:
    """Nested StateObject survives to_json() -> from_json() round-trip."""
    from tinycua.models import StateObject

    @dataclass
    class Inner(StateObject):
        value: str = ""

    @dataclass
    class Outer(StateObject):
        inner: Inner = field(default_factory=Inner)
        label: str = ""

    original = Outer(inner=Inner(value="nested"), label="outer")
    restored = Outer.from_json(original.to_json())

    assert isinstance(restored.inner, Inner)
    assert restored.inner.value == "nested"
    assert restored.label == "outer"
