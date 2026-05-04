"""Type-to-JSON-Schema conversion helpers for tool parameter generation."""

from __future__ import annotations

import enum
from typing import Any, get_args, get_origin


def generate_schema(type_hint: Any) -> dict[str, Any]:
    """Alias for type_to_json_schema."""
    return type_to_json_schema(type_hint)


def type_to_json_schema(type_hint: Any) -> dict[str, Any]:
    """Convert a Python type annotation to a JSON Schema dict.

    Supports: str, int, float, bool, list[T], dict[K, V], Optional[T],
    Union[T, ...], Enum subclasses, and Annotated[T, metadata].

    Args:
        type_hint: A Python type annotation (e.g. str, list[int],
            Optional[str], Annotated[str, "description"]).

    Returns:
        A JSON Schema dict describing the type.

    """
    # Handle Annotated — unwrap to get base type and extract description
    type_hint, description = _handle_annotated(type_hint)

    # Check for Enum subclass
    schema = _handle_enum(type_hint, description)
    if schema is not None:
        return schema

    # Check for Union (including Optional which is Union[T, None])
    schema = _handle_union(type_hint, description)
    if schema is not None:
        return schema

    # Check for list / List
    schema = _handle_list(type_hint, description)
    if schema is not None:
        return schema

    # Check for dict / Dict
    schema = _handle_dict(type_hint, description)
    if schema is not None:
        return schema

    # Primitive types
    schema = _handle_primitive(type_hint, description)
    if schema is not None:
        return schema

    # Fallback for unknown types
    schema = {"type": "string"}
    if description:
        schema["description"] = description
    return schema


def _handle_annotated(type_hint: Any) -> tuple[Any, str | None]:
    """Handle Annotated type hint.

    Args:
        type_hint: A Python type annotation.

    Returns:
        Tuple of (base_type, description).

    """
    description = None
    origin = get_origin(type_hint)

    # Check for Annotated (typing.Annotated or typing_extensions.Annotated)
    if origin is not None and _is_annotated_origin(origin):
        args = get_args(type_hint)
        if args:
            base_type = args[0]
            # Extract description from metadata
            for meta in args[1:]:
                if isinstance(meta, str):
                    description = meta
                    break
            type_hint = base_type

    return type_hint, description


def _handle_enum(type_hint: Any, description: str | None) -> dict[str, Any] | None:
    """Handle Enum type hint.

    Args:
        type_hint: A Python type annotation.
        description: Optional description from Annotated.

    Returns:
        JSON Schema dict for Enum, or None if not Enum.

    """
    if isinstance(type_hint, type) and issubclass(type_hint, enum.Enum):
        schema = {"type": "string", "enum": [e.value for e in type_hint]}
        if description:
            schema["description"] = description
        return schema
    return None


def _handle_union(type_hint: Any, description: str | None) -> dict[str, Any] | None:
    """Handle Union type hint.

    Args:
        type_hint: A Python type annotation.
        description: Optional description from Annotated.

    Returns:
        JSON Schema dict for Union, or None if not Union.

    """
    origin = get_origin(type_hint)
    if origin is not None and origin in _union_type():
        union_args = get_args(type_hint)
        # Filter out NoneType for Optional handling
        non_none_args = [a for a in union_args if a is not type(None)]

        if len(non_none_args) == 1:
            # Optional[T] — just return the inner type schema
            schema = type_to_json_schema(non_none_args[0])
            if description:
                schema["description"] = description
            return schema

        if len(non_none_args) > 1:
            # Union[T1, T2, ...] — generate anyOf
            schema = {
                "anyOf": [type_to_json_schema(a) for a in non_none_args],
            }
            if description:
                schema["description"] = description
            return schema
    return None


def _handle_list(type_hint: Any, description: str | None) -> dict[str, Any] | None:
    """Handle List type hint.

    Args:
        type_hint: A Python type annotation.
        description: Optional description from Annotated.

    Returns:
        JSON Schema dict for List, or None if not List.

    """
    origin = get_origin(type_hint)
    if origin in (list, _list_type()):
        args = get_args(type_hint)
        if args:
            item_schema = type_to_json_schema(args[0])
            schema = {"type": "array", "items": item_schema}
        else:
            schema = {"type": "array"}
        if description:
            schema["description"] = description
        return schema
    return None


def _handle_dict(type_hint: Any, description: str | None) -> dict[str, Any] | None:
    """Handle Dict type hint.

    Args:
        type_hint: A Python type annotation.
        description: Optional description from Annotated.

    Returns:
        JSON Schema dict for Dict, or None if not Dict.

    """
    origin = get_origin(type_hint)
    if origin in (dict, _dict_type()):
        schema = {"type": "object"}
        if description:
            schema["description"] = description
        return schema
    return None


def _handle_primitive(type_hint: Any, description: str | None) -> dict[str, Any] | None:
    """Handle primitive type hint.

    Args:
        type_hint: A Python type annotation.
        description: Optional description from Annotated.

    Returns:
        JSON Schema dict for primitive type, or None if not primitive.

    """
    primitive_map: dict[Any, str] = {
        str: "string",
        int: "number",
        float: "number",
        bool: "boolean",
    }

    if type_hint in primitive_map:
        schema = {"type": primitive_map[type_hint]}
        if description:
            schema["description"] = description
        return schema
    return None


def _is_annotated_origin(origin: Any) -> bool:
    """Check if origin is the Annotated type.

    Args:
        origin: The origin type from get_origin().

    Returns:
        True if origin represents Annotated.

    """
    try:
        from typing import Annotated

        return origin is Annotated
    except ImportError:
        return False


def _union_type() -> Any:
    """Get the Union type for comparison.

    Returns:
        The Union type from typing module.

    """
    from typing import Union
    from types import UnionType

    return Union, UnionType


def _list_type() -> Any:
    """Get the typing.List type for comparison.

    Returns:
        The List type from typing module.

    """
    from typing import List

    return List


def _dict_type() -> Any:
    """Get the typing.Dict type for comparison.

    Returns:
        The Dict type from typing module.

    """
    from typing import Dict

    return Dict
