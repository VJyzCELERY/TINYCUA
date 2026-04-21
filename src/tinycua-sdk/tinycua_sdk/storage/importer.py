"""Import functionality for TinyCUA data."""

import io
import json
import zipfile
from typing import Any


CURRENT_VERSION = "1.0.0"
MIN_VERSION = "1.0.0"


class Importer:
    """Import TinyCUA data from JSON or ZIP format.

    Provides methods to import sessions, agents, and memory
    from backup files with validation and merge/replace modes.

    Usage:
        importer = Importer(storage)
        importer.import_json("backup.json")
        importer.import_zip("backup.zip")
    """

    def __init__(self, storage):
        """Initialize importer.

        Args:
            storage: LocalStorage instance to import to
        """
        self.storage = storage

    def validate_import(self, data: dict[str, Any]) -> dict[str, Any]:
        """Validate import data structure and version.

        Args:
            data: Import data dictionary

        Returns:
            Validation result with status and errors
        """
        errors = []
        warnings = []

        if "version" not in data:
            errors.append("Missing 'version' field")
        else:
            version = data.get("version", "")
            if version < MIN_VERSION:
                errors.append(f"Version {version} is below minimum {MIN_VERSION}")
            elif version != CURRENT_VERSION:
                warnings.append(f"Version {version} differs from current {CURRENT_VERSION}")

        if "sessions" in data and not isinstance(data["sessions"], list):
            errors.append("'sessions' must be a list")

        if "agents" in data and not isinstance(data["agents"], list):
            errors.append("'agents' must be a list")

        if "memory" in data and not isinstance(data["memory"], list):
            errors.append("'memory' must be a list")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "version": data.get("version"),
        }

    def import_json(self, data: dict[str, Any], mode: str = "merge") -> dict[str, Any]:
        """Import data from JSON format.

        Args:
            data: Import data dictionary
            mode: 'merge' to add to existing, 'replace' to clear first

        Returns:
            Import result summary
        """
        validation = self.validate_import(data)
        if not validation["valid"]:
            return {
                "success": False,
                "errors": validation["errors"],
            }

        result = self.storage.import_data(data, mode=mode)
        return {
            "success": True,
            "imported": result,
            "warnings": validation["warnings"],
        }

    def import_zip(self, zip_data: bytes, mode: str = "merge") -> dict[str, Any]:
        """Import data from ZIP format.

        Args:
            zip_data: ZIP file bytes
            mode: 'merge' to add to existing, 'replace' to clear first

        Returns:
            Import result summary
        """
        try:
            buffer = io.BytesIO(zip_data)
            with zipfile.ZipFile(buffer, "r") as zf:
                if "data.json" not in zf.namelist():
                    return {
                        "success": False,
                        "errors": ["ZIP does not contain data.json"],
                    }

                with zf.open("data.json") as f:
                    data = json.load(f)
        except zipfile.BadZipFile:
            return {
                "success": False,
                "errors": ["Invalid ZIP file"],
            }
        except json.JSONDecodeError as e:
            return {
                "success": False,
                "errors": [f"Invalid JSON in data.json: {e}"],
            }

        return self.import_json(data, mode=mode)

    def import_from_file(self, filepath: str, mode: str = "merge") -> dict[str, Any]:
        """Import from file with auto-detect format.

        Args:
            filepath: Input file path (.json or .zip)
            mode: 'merge' to add to existing, 'replace' to clear first

        Returns:
            Import result summary
        """
        import os

        ext = os.path.splitext(filepath)[1].lower()

        if ext == ".zip":
            with open(filepath, "rb") as f:
                zip_data = f.read()
            return self.import_zip(zip_data, mode=mode)
        else:
            with open(filepath, "r") as f:
                data = json.load(f)
            return self.import_json(data, mode=mode)


__all__ = ["Importer", "CURRENT_VERSION", "MIN_VERSION"]
