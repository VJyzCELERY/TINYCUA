"""Conflict resolution for multi-device sync using last-write-wins."""

from datetime import datetime, timezone
from typing import Any


def _parse_datetime(value: str | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def resolve_conflict(
    local_item: dict[str, Any],
    remote_item: dict[str, Any],
) -> tuple[dict[str, Any], str]:
    """Resolve conflict using last-write-wins.

    Args:
        local_item: Local item with updated_at timestamp
        remote_item: Remote item with updated_at timestamp

    Returns:
        Tuple of (winning item, conflict_info)
    """
    local_updated = _parse_datetime(local_item.get("updated_at"))
    remote_updated = _parse_datetime(remote_item.get("updated_at"))

    if local_updated is None:
        local_updated = datetime.min.replace(tzinfo=timezone.utc)
    if remote_updated is None:
        remote_updated = datetime.min.replace(tzinfo=timezone.utc)

    if remote_updated > local_updated:
        return remote_item, "remote_wins"
    elif local_updated > remote_updated:
        return local_item, "local_wins"
    else:
        server_time = datetime.now(timezone.utc).isoformat()
        local_item["updated_at"] = server_time
        return local_item, "local_wins"


def detect_conflict(
    local_item: dict[str, Any],
    remote_item: dict[str, Any],
) -> bool:
    """Detect if there's a conflict between local and remote items.

    Args:
        local_item: Local item
        remote_item: Remote item

    Returns:
        True if conflict detected, False otherwise
    """
    local_updated = _parse_datetime(local_item.get("updated_at"))
    remote_updated = _parse_datetime(remote_item.get("updated_at"))

    if local_updated is None or remote_updated is None:
        return False

    if local_updated != remote_updated:
        return True

    conflict_fields = ["name", "content", "role"]
    for field in conflict_fields:
        local_val = local_item.get(field)
        remote_val = remote_item.get(field)
        if local_val != remote_val:
            return True

    return False
