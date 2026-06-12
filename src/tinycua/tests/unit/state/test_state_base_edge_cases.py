"""Edge case tests for StateObject base class that need raw None annotations.

This file MUST NOT have 'from __future__ import annotations' because we
need f.type to return None (not the string 'None') for fields annotated
with 'None'. This allows testing the resolved_type is None path in
StateObject.from_dict() when the field's annotation is removed from
__annotations__ after class creation.
"""

import dataclasses

from tinycua.state.base import StateObject


@dataclasses.dataclass
class _TestAnnotNoneRemoved(StateObject):
    name: str
    extra: None = None


# Simulate annotation removal after class creation;
# this makes typing.get_type_hints() miss this field.
del _TestAnnotNoneRemoved.__annotations__["extra"]


class TestBaseEdgeCasesAnnotNone:
    """Tests for from_dict when resolved_type becomes None.

    Covers the fallthrough path at base.py lines 45-46 where
    hints.get(field.name) returns None (key missing) and
    field_types.get(field.name) also returns None (annotation is
    the bare None singleton).
    """

    def test_from_dict_resolved_type_none(self):
        """from_dict passes raw value when resolved_type is None."""
        obj = _TestAnnotNoneRemoved.from_dict(
            {"name": "test", "extra": "passthrough"},
        )
        assert obj.name == "test"
        assert obj.extra == "passthrough"

    def test_from_dict_resolved_type_none_with_none_value(self):
        """from_dict passes None raw value when resolved_type is None."""
        obj = _TestAnnotNoneRemoved.from_dict(
            {"name": "test", "extra": None},
        )
        assert obj.name == "test"
        assert obj.extra is None
