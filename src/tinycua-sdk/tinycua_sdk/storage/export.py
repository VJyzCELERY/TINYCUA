"""Export functionality for TinyCUA data."""

import io
import json
import os
import zipfile
from datetime import datetime
from typing import Any


CURRENT_VERSION = "1.0.0"


class Exporter:
    """Export TinyCUA data to JSON or ZIP format.

    Provides methods to export sessions, agents, and memory
    to various formats for backup or data migration.

    Usage:
        exporter = Exporter(storage)
        exporter.export_json("backup.json")
        exporter.export_zip("backup.zip")
    """

    def __init__(self, storage):
        """Initialize exporter.

        Args:
            storage: LocalStorage instance to export from
        """
        self.storage = storage

    def _sanitize_datetime(self, data: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Convert datetime objects to ISO format strings."""
        result = []
        for item in data:
            item_copy = dict(item)
            for k, v in item_copy.items():
                if isinstance(v, datetime):
                    item_copy[k] = v.isoformat()
            result.append(item_copy)
        return result

    def export_json(self) -> dict[str, Any]:
        """Export all data to JSON format.

        Returns:
            Dictionary with export metadata and data
        """
        data = self.storage.export_all()
        return {
            "version": CURRENT_VERSION,
            "exported_at": datetime.utcnow().isoformat(),
            "sessions": self._sanitize_datetime(data["sessions"]),
            "agents": self._sanitize_datetime(data["agents"]),
            "memory": self._sanitize_datetime(data["memory"]),
        }

    def export_zip(self) -> dict[str, Any]:
        """Export all data to ZIP format with MEMORY.md and USER.md.

        Creates a ZIP file containing:
        - data.json: Full export data
        - MEMORY.md: Memory entries in markdown format
        - USER.md: User/agent info if available

        Returns:
            Dictionary with export metadata (actual ZIP is streamed)
        """
        data = self.storage.export_all()

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            exported_at = datetime.utcnow().isoformat()
            data_copy = {
                "version": CURRENT_VERSION,
                "exported_at": exported_at,
                "sessions": [],
                "agents": [],
                "memory": [],
            }
            for s in data["sessions"]:
                s_copy = dict(s)
                for k, v in s_copy.items():
                    if isinstance(v, datetime):
                        s_copy[k] = v.isoformat()
                data_copy["sessions"].append(s_copy)
            for a in data["agents"]:
                a_copy = dict(a)
                for k, v in a_copy.items():
                    if isinstance(v, datetime):
                        a_copy[k] = v.isoformat()
                data_copy["agents"].append(a_copy)
            for m in data["memory"]:
                m_copy = dict(m)
                for k, v in m_copy.items():
                    if isinstance(v, datetime):
                        m_copy[k] = v.isoformat()
                data_copy["memory"].append(m_copy)

            zf.writestr("data.json", json.dumps(data_copy, indent=2))

            memory_md = self._generate_memory_md(data["memory"])
            zf.writestr("MEMORY.md", memory_md)

            user_md = self._generate_user_md(data["agents"])
            zf.writestr("USER.md", user_md)

        buffer.seek(0)
        return {
            "version": CURRENT_VERSION,
            "exported_at": datetime.utcnow().isoformat(),
            "zip_data": buffer.getvalue(),
            "size": len(buffer.getvalue()),
        }

    def _generate_memory_md(self, memory_list: list[dict[str, Any]]) -> str:
        """Generate MEMORY.md content.

        Args:
            memory_list: List of memory dictionaries

        Returns:
            Markdown formatted memory content
        """
        lines = ["# Memory Export", "", f"Exported: {datetime.utcnow().isoformat()}", ""]

        by_type = {}
        for mem in memory_list:
            mtype = mem.get("memory_type", "unknown")
            if mtype not in by_type:
                by_type[mtype] = []
            by_type[mtype].append(mem)

        for mtype, entries in by_type.items():
            lines.append(f"## {mtype.replace('_', ' ').title()}")
            lines.append("")
            for entry in entries:
                lines.append(f"### {entry.get('id', 'unknown')}")
                if entry.get("session_id"):
                    lines.append(f"- Session: {entry['session_id']}")
                if entry.get("agent_id"):
                    lines.append(f"- Agent: {entry['agent_id']}")
                lines.append(f"- Created: {entry.get('created_at', 'unknown')}")
                lines.append("")
                content = entry.get("content", "")
                if content:
                    lines.append("```")
                    lines.append(content[:500])
                    if len(content) > 500:
                        lines.append("... (truncated)")
                    lines.append("```")
                lines.append("")

        return "\n".join(lines)

    def _generate_user_md(self, agents_list: list[dict[str, Any]]) -> str:
        """Generate USER.md content.

        Args:
            agents_list: List of agent dictionaries

        Returns:
            Markdown formatted user/agent content
        """
        lines = ["# User/Agent Export", "", f"Exported: {datetime.utcnow().isoformat()}", ""]

        if not agents_list:
            lines.append("_No agents found._")
        else:
            lines.append(f"## Agents ({len(agents_list)})")
            lines.append("")
            for agent in agents_list:
                lines.append(f"### {agent.get('name', 'Unknown')}")
                lines.append(f"- ID: {agent.get('id', 'unknown')}")
                lines.append(f"- Created: {agent.get('created_at', 'unknown')}")
                lines.append("")

        return "\n".join(lines)

    def export_to_file(self, filepath: str) -> dict[str, Any]:
        """Export to file with auto-detect format.

        Args:
            filepath: Output file path (.json or .zip)

        Returns:
            Export metadata
        """
        ext = os.path.splitext(filepath)[1].lower()

        if ext == ".zip":
            result = self.export_zip()
            with open(filepath, "wb") as f:
                f.write(result["zip_data"])
            return {
                "version": result["version"],
                "exported_at": result["exported_at"],
                "format": "zip",
                "size": result["size"],
            }
        else:
            result = self.export_json()
            with open(filepath, "w") as f:
                json.dump(result, f, indent=2)
            return {
                "version": result["version"],
                "exported_at": result["exported_at"],
                "format": "json",
                "sessions": len(result["sessions"]),
                "agents": len(result["agents"]),
                "memory": len(result["memory"]),
            }


__all__ = ["Exporter", "CURRENT_VERSION"]
