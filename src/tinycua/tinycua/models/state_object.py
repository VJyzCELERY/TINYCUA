"""StateObject base class for TinyCUA model serialization."""

from __future__ import annotations

import builtins
import dataclasses
import json
import types
import typing
from dataclasses import dataclass, fields


# Registry for StateObject subclasses by name
_STATE_OBJECT_REGISTRY: dict[str, type[StateObject]] = {}


@dataclass
class StateObject:
    """Serialization base for TinyCUA model dataclasses.

    Provides dict/JSON serialization with recursive handling of nested
    StateObject instances. Subclasses inherit to_dict(), from_dict(),
    to_json(), and from_json() methods automatically.

    All StateObject subclasses are automatically registered for type
    resolution during deserialization.
    """

    def __init_subclass__(cls, **kwargs: typing.Any) -> None:
        """Register StateObject subclasses for type resolution."""
        super().__init_subclass__(**kwargs)
        # Register the class by name
        _STATE_OBJECT_REGISTRY[cls.__name__] = cls

    def to_dict(self) -> dict:
        """Serialize to dictionary.

        Nested StateObject instances are recursively converted via their
        own to_dict() method. Lists and dicts containing StateObject
        instances are also handled recursively.

        Returns:
            Dictionary representation of all dataclass fields.
        """
        return _state_object_to_dict(self)

    @classmethod
    def from_dict(cls, data: dict) -> typing.Self:
        """Reconstruct from dictionary.

        Nested dicts are recursively deserialized when the corresponding
        field type is a StateObject subclass. All fields must be present
        in the data — missing fields raise ValueError.

        Args:
            data: Dictionary representation of the object.

        Returns:
            Reconstructed typed object.

        Raises:
            ValueError: If a required field is missing from the data.
        """
        return typing.cast(typing.Self, _state_object_from_dict(cls, data))

    def to_json(self, **json_kwargs: typing.Any) -> str:
        """Serialize to JSON string via to_dict() then json.dumps().

        Args:
            **json_kwargs: Additional keyword arguments passed to json.dumps().

        Returns:
            JSON string representation.
        """
        return json.dumps(self.to_dict(), **json_kwargs)

    @classmethod
    def from_json(cls, json_str: str) -> typing.Self:
        """Reconstruct from JSON string via json.loads() then from_dict().

        Args:
            json_str: JSON string representation.

        Returns:
            Reconstructed typed object.

        Raises:
            json.JSONDecodeError: If the string is not valid JSON.
        """
        return cls.from_dict(json.loads(json_str))


def _state_object_to_dict(obj: StateObject) -> dict:
    """Recursively convert a StateObject to a dictionary.

    Handles nested StateObject instances, lists, and dicts.
    """
    result = {}
    for f in fields(obj):
        value = getattr(obj, f.name)
        result[f.name] = _convert_value_to_dict(value)
    return result


def _convert_value_to_dict(value: typing.Any) -> typing.Any:
    """Convert a value to its dictionary representation.

    Recursively handles StateObject instances, lists, and dicts.
    """
    if isinstance(value, StateObject):
        return _state_object_to_dict(value)
    if isinstance(value, list):
        return [_convert_value_to_dict(item) for item in value]
    if isinstance(value, dict):
        return {k: _convert_value_to_dict(v) for k, v in value.items()}
    return value


def _get_type_hints_safe(cls: type) -> dict[str, typing.Any]:
    """Get type hints for a class, handling forward references.

    Uses the class's module namespace to resolve forward references.
    Falls back to field types if resolution fails.
    """
    try:
        # Try to get type hints with the class's module namespace
        hints = typing.get_type_hints(cls)
        return hints
    except (NameError, TypeError, AttributeError):
        # Fallback: return field types as-is (may be strings)
        return {f.name: f.type for f in fields(cls)}


def _state_object_from_dict(
    cls: type[StateObject], data: dict
) -> StateObject:
    """Reconstruct a StateObject from a dictionary.

    Uses field type annotations to auto-convert nested StateObject subclasses.
    All fields must be present in the data.
    """
    field_map = {f.name: f for f in fields(cls)}
    type_hints = _get_type_hints_safe(cls)

    # Check for missing fields first
    for field_name in field_map:
        if field_name not in data:
            msg = f"Missing required field: {field_name}"
            raise ValueError(msg)

    kwargs = {}
    for field_name, field_obj in field_map.items():
        value = data[field_name]
        hint = type_hints.get(field_name)
        kwargs[field_name] = _convert_value_from_dict(value, hint, field_obj)

    return cls(**kwargs)  # kwargs guaranteed by for-loop over dataclass fields


def _convert_list_value(
    value: typing.Any, hint: typing.Any, field_obj: dataclasses.Field
) -> typing.Any:
    """Convert a list value using the inner type hint."""
    args = getattr(hint, "__args__", ())
    if args:
        inner_hint = args[0]
        if isinstance(inner_hint, str):
            inner_hint = _resolve_annotation(inner_hint)
        if isinstance(inner_hint, type) and issubclass(inner_hint, StateObject):
            return [_convert_value_from_dict(item, inner_hint, field_obj) for item in value]
    return value


def _convert_union_value(
    value: typing.Any, hint: typing.Any, field_obj: dataclasses.Field
) -> typing.Any:
    """Convert a value for a Union type hint by trying each arg."""
    args = getattr(hint, "__args__", ())

    for arg in args:
        if arg is type(None):
            continue
        if isinstance(arg, str):
            arg = _resolve_annotation(arg)
        if isinstance(arg, type) and isinstance(value, arg):
            return value

    for arg in args:
        if arg is type(None):
            continue
        if isinstance(arg, str):
            arg = _resolve_annotation(arg)
        if isinstance(arg, type) and issubclass(arg, StateObject):
            if isinstance(value, dict):
                return _state_object_from_dict(arg, value)
            return value

    return value


def _convert_value_from_dict(
    value: typing.Any, hint: typing.Any, field_obj: dataclasses.Field
) -> typing.Any:
    """Convert a dictionary value back to its typed representation.

    Recursively handles nested StateObject subclasses.
    """
    if value is None:
        return None

    if isinstance(hint, str):
        hint = _resolve_annotation(hint)

    origin = getattr(hint, "__origin__", None)

    if isinstance(hint, type) and issubclass(hint, StateObject):
        if isinstance(value, dict):
            return _state_object_from_dict(hint, value)
        return value

    if origin is list:
        return _convert_list_value(value, hint, field_obj)

    if origin is dict:
        return value

    if hint is not None and typing.get_origin(hint) in (
        typing.Union,
        getattr(types, "UnionType", None),
    ):
        return _convert_union_value(value, hint, field_obj)

    return value


def _resolve_annotation(hint_str: str) -> typing.Any:
    """Resolve a string annotation to its type.

    Uses the registry of StateObject subclasses for resolution.
    """
    # Simple name resolution for common types

    # Check builtins
    if hint_str in dir(builtins):
        return getattr(builtins, hint_str)

    # Check common typing constructs
    if hint_str == "StateObject":
        return StateObject

    # Check the registry for StateObject subclasses
    if hint_str in _STATE_OBJECT_REGISTRY:
        return _STATE_OBJECT_REGISTRY[hint_str]

    # For complex annotations, return None to skip conversion
    return None
