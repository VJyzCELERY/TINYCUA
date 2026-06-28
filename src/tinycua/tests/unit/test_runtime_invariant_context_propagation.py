"""Node context is segmented, deduped, and internal-role safe (runtime invariant).

Spec: ./specs/tinycua-runtime-invariants/spec.md:182, 215-216, 228-229, 266, 275
Source: src/tinycua/docs/design/loops/node.md:66-73, 83-86, 216-220,
        src/tinycua/docs/design/loops/propagation.md:30-70, 79-109, 116-135

Internal handoffs/retries are assistant/internal records, never recreated as
external user messages. Forwarded context is selected handoff/output, not a
wholesale dump of prior messages. Duplicate origin records are deduped.
"""

from __future__ import annotations

from tinycua.loops.propagation import (
    PROPAGATION_PROFILES,
    PropagationRule,
    dedupe_records,
)
from tinycua.models.session_context_entry import SessionContextEntry


def _entry(
    record_id: str,
    *,
    origin_record_id: str | None = None,
    content: str = "",
    segment: str = "output",
) -> SessionContextEntry:
    """Build a minimal session context entry for propagation tests.

    ``role`` is a derived property: ``output`` segment -> ``assistant``,
    ``prior``/``input`` segment -> ``user``. Internal handoffs/retries use
    ``output`` so they persist as assistant-role records.
    """
    return SessionContextEntry(
        record_id=record_id,
        origin_record_id=origin_record_id,
        content=content,
        segment=segment,  # type: ignore[arg-type]
    )


def test_dedupe_filters_by_origin_record_id() -> None:
    """Spec: ./spec.md:229, ./spec.md:275.

    Source: propagation.md:30-70, propagation.md:94-109.
    Records whose origin_record_id already exists in destination are dropped.
    """
    destination = [_entry("d1", origin_record_id="origin-a")]
    source = [
        _entry("s1", origin_record_id="origin-a"),  # dup -> dropped
        _entry("s2", origin_record_id="origin-b"),  # new -> kept
    ]

    filtered = dedupe_records(source, destination)

    assert [e.record_id for e in filtered] == ["s2"]


def test_dedupe_falls_back_to_record_id_when_origin_missing() -> None:
    """Spec: ./spec.md:229, ./spec.md:275.

    Source: propagation.md:94-109.
    When origin_record_id is None, dedupe uses record_id.
    """
    destination = [_entry("d1")]
    source = [_entry("d1"), _entry("s2")]

    filtered = dedupe_records(source, destination)

    assert [e.record_id for e in filtered] == ["s2"]


def test_dedupe_keeps_all_when_destination_empty() -> None:
    """Spec: ./spec.md:229.

    Source: propagation.md:30-70.
    An empty destination means no dedupe; every source record is kept.
    """
    source = [
        _entry("s1", origin_record_id="o1"),
        _entry("s2", origin_record_id="o2"),
    ]

    filtered = dedupe_records(source, [])

    assert len(filtered) == 2


def test_internal_output_propagation_profile_dedupes() -> None:
    """Spec: ./spec.md:215-216, ./spec.md:228-229, ./spec.md:275.

    Source: propagation.md:30-70, propagation.md:116-135.
    The selected_internal_output profile used for transient routing-node
    output forwarding must dedupe so the next node does not see duplicates.
    """
    profile = PROPAGATION_PROFILES["selected_internal_output"]
    assert isinstance(profile, PropagationRule)
    assert profile.dedupe is True


def test_selected_propagation_mode_is_not_full_dump() -> None:
    """Spec: ./spec.md:189, ./spec.md:229, ./spec.md:275.

    Source: propagation.md:30-70, propagation.md:94-109.
    The selected mode forwards chosen output segments only, not the full
    prior context. This is a structural assertion: the profile mode must be
    "selected", never "full" for internal handoffs.
    """
    profile = PROPAGATION_PROFILES["selected_internal_output"]
    assert profile.session_context_mode == "selected"
    assert profile.session_context_mode != "full"


def test_no_propagation_profile_recreates_internal_handoff_as_user_role() -> None:
    """Spec: ./spec.md:182, ./spec.md:215-216, ./spec.md:266.

    Source: node.md:66-73, node.md:83-86, propagation.md:79-92.
    Propagation profiles transport SessionContextEntry records; role is set
    by the node layer (assistant/internal). This test guards the propagation
    layer: dedupe and forwarding must not rewrite the role field. We verify
    the dedupe function preserves the original role of every kept record.
    """
    source = [
        _entry("s1", origin_record_id="o1", segment="output", content="handoff"),
        _entry("s2", origin_record_id="o2", segment="output", content="retry"),
    ]

    filtered = dedupe_records(source, [])

    for record in filtered:
        # Internal handoff/retry segments are "output" -> assistant role.
        assert record.segment == "output"
        assert record.role == "assistant"
        assert record.role != "user"
