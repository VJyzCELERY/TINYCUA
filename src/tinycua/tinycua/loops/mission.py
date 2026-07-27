"""Compact root-mission rendering for worker nodes."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tinycua.models.session import Session


def _string_list(value: object) -> list[str]:
    """Return stripped nonempty strings from an optional metadata list."""
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _render_mission_block(session: Session) -> str:
    """Render the immutable mission plus the one current-turn overlay."""
    store = session.task_store
    if store.root_task_id is None or store.root_task_id not in store.tasks:
        return ""
    root = store.tasks[store.root_task_id]
    mission = str(root.metadata.get("mission", "") or "").strip()
    mission_context = str(root.metadata.get("mission_context", "") or "").strip()
    key_points = _string_list(root.metadata.get("mission_key_points", []))
    constraints = _string_list(root.metadata.get("inherited_constraints", []))
    overlay = root.metadata.get("current_context_overlay", {})
    if not isinstance(overlay, dict):
        overlay = {}
    overlay_summary = str(overlay.get("context_summary", "") or "").strip()
    overlay_points = _string_list(overlay.get("key_points", []))
    overlay_gaps = _string_list(overlay.get("known_gaps", []))
    if not any(
        (
            mission,
            mission_context,
            key_points,
            constraints,
            overlay_summary,
            overlay_points,
            overlay_gaps,
        )
    ):
        return ""
    lines = [
        "## Current Mission — Context Only",
        "This is the overall workflow objective, not your assigned task. Use it "
        "only to understand the context for your delegated role.",
        "The original request and hard constraints control if generated task text, "
        "acceptance clauses, roadmap descriptions, or model assumptions conflict.",
    ]
    if mission_context:
        lines.append(mission_context)
    if key_points:
        lines.append("Key findings:")
        lines.extend(f"- {point}" for point in key_points)
    if mission:
        lines.append(f"Original request: {mission}")
    if constraints:
        lines.append("Hard constraints:")
        lines.extend(f"- {constraint}" for constraint in constraints)
    if overlay_summary or overlay_points or overlay_gaps:
        lines.append("## Current turn context")
        if overlay_summary:
            lines.append(overlay_summary)
        if overlay_points:
            lines.append("Relevant findings:")
            lines.extend(f"- {point}" for point in overlay_points)
        if overlay_gaps:
            lines.append("Known gaps:")
            lines.extend(f"- {gap}" for gap in overlay_gaps)
    return "\n".join(lines)
