"""Base class for all TINYCUA state objects with serialization helpers."""

from __future__ import annotations

__all__ = ["StateObject"]

import dataclasses
import json
import types
import typing
from typing import Any, Self


class StateObject:
    """Base class providing serialization for all state object dataclasses.

    Subclasses must be @dataclass-decorated classes. Provides:
    - to_dict() / from_dict() round-trip using dataclasses.asdict() and
      automatic nested deserialization via type introspection.
    - to_json() / from_json() round-trip wrapping dict serialization.
    """

    def to_dict(self) -> dict[str, Any]:
        """Serialize this object to a JSON-serializable dict."""
        return dataclasses.asdict(self)  # type: ignore[call-overload]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Deserialize from a dict, auto-converting nested state objects."""
        hints = typing.get_type_hints(cls)
        field_types = {f.name: f.type for f in dataclasses.fields(cls)}  # type: ignore[arg-type]
        kwargs: dict[str, Any] = {}

        for field in dataclasses.fields(cls):  # type: ignore[arg-type]
            if field.name not in data:
                if field.default is not dataclasses.MISSING:
                    continue  # Use default
                if field.default_factory is not dataclasses.MISSING:
                    continue  # Use default_factory
                raise ValueError(f"Missing required field '{field.name}' in {cls.__name__}")

            raw_value = data[field.name]
            if raw_value is None:
                kwargs[field.name] = None
                continue

            resolved_type = hints.get(field.name, field_types.get(field.name))
            if resolved_type is None:
                kwargs[field.name] = raw_value
                continue

            kwargs[field.name] = cls._convert_value(raw_value, resolved_type)

        return cls(**kwargs)  # type: ignore[call-arg,return-value]

    def to_json(self, **json_kwargs: Any) -> str:
        """Serialize this object to a JSON string."""
        return json.dumps(self.to_dict(), **json_kwargs)

    @classmethod
    def from_json(cls, json_str: str) -> Self:
        """Deserialize from a JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)

    @staticmethod
    def _validate_enum(value: str, allowed: set[str], field_name: str) -> None:
        """Validate that *value* is one of the *allowed* values for *field_name*.

        Raises:
            ValueError: With a consistent message on failure.
        """
        if value not in allowed:
            allowed_str = ", ".join(sorted(allowed))
            raise ValueError(
                f"Invalid value '{value}' for field '{field_name}': "
                f"expected one of {allowed_str}"
            )

    @classmethod
    def _convert_value(cls, value: Any, target_type: Any) -> Any:
        """Recursively convert a raw value to the target type.

        Handles StateObject subclasses, Optional[StateObject], list[T],
        dict, and basic types.
        """
        origin = typing.get_origin(target_type)
        args = typing.get_args(target_type)

        # Handle Optional[X] -> Union[X, None]
        if origin is typing.Union or origin is types.UnionType:  # type: ignore[attr-defined]
            non_none_args = [a for a in args if a is not type(None)]
            if non_none_args:
                return cls._convert_value(value, non_none_args[0])
            return value

        # Handle list[T]
        if origin is list:
            if args and isinstance(value, list):
                item_type = args[0]
                return [cls._convert_value(item, item_type) for item in value]
            return value

        # Handle dict[str, V]
        if origin is dict:
            return value

        # Handle nested StateObject
        if isinstance(value, dict) and cls._is_state_object_type(target_type):
            return target_type.from_dict(value)  # type: ignore[union-attr]

        return value

    @staticmethod
    def _is_state_object_type(tp: Any) -> bool:
        """Check if a type is a StateObject subclass."""
        if isinstance(tp, type):
            return issubclass(tp, StateObject)
        return False



