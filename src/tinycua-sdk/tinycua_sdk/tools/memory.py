"""Memory storage backend with DB-first + local fallback."""

import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class MemoryBackend(ABC):
    """Abstract base for memory storage backends."""

    @abstractmethod
    def get(self, key: str) -> tuple[str | None, bool]:
        """Get a value by key."""
        pass

    @abstractmethod
    def set(self, key: str, value: str) -> dict[str, Any]:
        """Set a key-value pair."""
        pass

    @abstractmethod
    def delete(self, key: str) -> dict[str, Any]:
        """Delete a key."""
        pass

    @abstractmethod
    def list_keys(self) -> list[str]:
        """List all keys."""
        pass

    @abstractmethod
    def clear(self) -> dict[str, Any]:
        """Clear all memory."""
        pass


class LocalMemoryBackend(MemoryBackend):
    """Local memory storage using JSON files."""

    def __init__(self, storage_path: str | None = None):
        """Initialize local memory storage.

        Args:
            storage_path: Custom storage path. Defaults to ~/.tinycua/memory.json

        """
        self.storage_path = Path(storage_path or self._default_storage_path())
        self._ensure_storage_dir()

    def _default_storage_path(self) -> str:
        """Get default storage path."""
        home = Path.home()
        tinycua_dir = home / ".tinycua" / "memory.json"
        return str(tinycua_dir)

    def _ensure_storage_dir(self) -> None:
        """Ensure storage directory exists."""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

    def _read_memory(self) -> dict[str, Any]:
        """Read memory from file."""
        if not self.storage_path.exists():
            return {}
        with open(self.storage_path, "r") as f:
            return json.load(f)

    def _write_memory(self, memory: dict[str, Any]) -> None:
        """Write memory to file."""
        with open(self.storage_path, "w") as f:
            json.dump(memory, f, indent=2)

    def get(self, key: str) -> tuple[str | None, bool]:
        """Get a value by key."""
        memory = self._read_memory()
        value = memory.get(key)
        return value, key in memory

    def set(self, key: str, value: str) -> dict[str, Any]:
        """Set a key-value pair."""
        memory = self._read_memory()
        memory[key] = value
        self._write_memory(memory)
        return {"success": True, "key": key, "value": value}

    def delete(self, key: str) -> dict[str, Any]:
        """Delete a key."""
        memory = self._read_memory()
        if key in memory:
            del memory[key]
            self._write_memory(memory)
            return {"success": True, "key": key}
        return {"success": False, "key": key, "error": "Key not found"}

    def list_keys(self) -> list[str]:
        """List all memory keys."""
        memory = self._read_memory()
        return list(memory.keys())

    def clear(self) -> dict[str, Any]:
        """Clear all memory."""
        self._write_memory({})
        return {"success": True}


class RemoteMemoryBackend(MemoryBackend):
    """Remote memory storage via backend API."""

    def __init__(self, backend_url: str, api_key: str | None = None):
        """Initialize remote memory backend.

        Args:
            backend_url: URL of the backend API
            api_key: Optional API key for authentication

        """
        self.backend_url = backend_url.rstrip("/")
        self.api_key = api_key
        self._available = True

    def _check_available(self) -> bool:
        """Check if backend is available."""
        import httpx

        try:
            response = httpx.get(f"{self.backend_url}/health", timeout=2)
            return response.status_code == 200
        except (httpx.HTTPError, OSError, ValueError):
            return False

    def get(self, key: str) -> tuple[str | None, bool]:
        """Get a value by key."""
        import httpx

        try:
            response = httpx.get(
                f"{self.backend_url}/api/v1/memory/{key}",
                headers=self._get_headers(),
                timeout=5,
            )
            if response.status_code == 200:
                data = response.json()
                return data.get("value"), True
            elif response.status_code == 404:
                return None, False
            return None, False
        except (httpx.HTTPError, OSError, ValueError) as e:
            logger.warning("Remote memory unavailable, falling back: %s", e)
            self._available = False
            raise

    def set(self, key: str, value: str) -> dict[str, Any]:
        """Set a key-value pair."""
        import httpx

        try:
            response = httpx.post(
                f"{self.backend_url}/api/v1/memory",
                json={"key": key, "value": value},
                headers=self._get_headers(),
                timeout=5,
            )
            if response.status_code in (200, 201):
                return response.json()
            return {"success": False, "error": f"Status {response.status_code}"}
        except (httpx.HTTPError, OSError, ValueError) as e:
            logger.warning("Remote memory unavailable, falling back: %s", e)
            self._available = False
            raise

    def delete(self, key: str) -> dict[str, Any]:
        """Delete a key."""
        import httpx

        try:
            response = httpx.delete(
                f"{self.backend_url}/api/v1/memory/{key}",
                headers=self._get_headers(),
                timeout=5,
            )
            if response.status_code in (200, 204):
                return {"success": True, "key": key}
            return {"success": False, "error": f"Status {response.status_code}"}
        except (httpx.HTTPError, OSError, ValueError) as e:
            logger.warning("Remote memory unavailable, falling back: %s", e)
            self._available = False
            raise

    def list_keys(self) -> list[str]:
        """List all keys."""
        import httpx

        try:
            response = httpx.get(
                f"{self.backend_url}/api/v1/memory",
                headers=self._get_headers(),
                timeout=5,
            )
            if response.status_code == 200:
                data = response.json()
                return data.get("keys", [])
            return []
        except (httpx.HTTPError, OSError, ValueError) as e:
            logger.warning("Remote memory unavailable, falling back: %s", e)
            self._available = False
            raise

    def clear(self) -> dict[str, Any]:
        """Clear all memory."""
        import httpx

        try:
            response = httpx.delete(
                f"{self.backend_url}/api/v1/memory",
                headers=self._get_headers(),
                timeout=5,
            )
            if response.status_code in (200, 204):
                return {"success": True}
            return {"success": False, "error": f"Status {response.status_code}"}
        except (httpx.HTTPError, OSError, ValueError) as e:
            logger.warning("Remote memory unavailable, falling back: %s", e)
            self._available = False
            raise

    def _get_headers(self) -> dict[str, str]:
        """Get request headers."""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers


class HybridMemoryBackend(MemoryBackend):
    """Memory backend that tries remote first, falls back to local."""

    def __init__(
        self,
        backend_url: str | None = None,
        api_key: str | None = None,
        local_storage_path: str | None = None,
    ):
        """Initialize hybrid memory backend.

        Args:
            backend_url: URL of the backend API (optional)
            api_key: Optional API key for authentication
            local_storage_path: Fallback local storage path

        """
        self._remote: RemoteMemoryBackend | None = None
        self._local = LocalMemoryBackend(local_storage_path)
        self._backend_url = backend_url
        self._api_key = api_key

        if backend_url:
            try:
                self._remote = RemoteMemoryBackend(backend_url, api_key)
            except (httpx.HTTPError, OSError, ValueError):
                self._remote = None

    def _get_backend(self) -> MemoryBackend:
        """Get the active backend (remote or local)."""
        if self._remote is not None:
            try:
                self._remote.get("_health_check")
                return self._remote
            except (httpx.HTTPError, OSError, ValueError):
                pass
        return self._local

    def get(self, key: str) -> tuple[str | None, bool]:
        """Get a value by key."""
        backend = self._get_backend()
        return backend.get(key)

    def set(self, key: str, value: str) -> dict[str, Any]:
        """Set a key-value pair."""
        backend = self._get_backend()
        return backend.set(key, value)

    def delete(self, key: str) -> dict[str, Any]:
        """Delete a key."""
        backend = self._get_backend()
        return backend.delete(key)

    def list_keys(self) -> list[str]:
        """List all keys."""
        backend = self._get_backend()
        return backend.list_keys()

    def clear(self) -> dict[str, Any]:
        """Clear all memory."""
        backend = self._get_backend()
        return backend.clear()


def get_memory_backend(
    backend_url: str | None = None,
    api_key: str | None = None,
    local_only: bool = False,
) -> MemoryBackend:
    """Get appropriate memory backend.

    Args:
        backend_url: URL of the backend API
        api_key: Optional API key
        local_only: If True, only use local storage

    Returns:
        MemoryBackend instance

    """
    if local_only or not backend_url:
        return LocalMemoryBackend()

    return HybridMemoryBackend(backend_url, api_key)


# Alias for backwards compatibility
MemoryStorage = LocalMemoryBackend

__all__ = [
    "MemoryBackend",
    "LocalMemoryBackend",
    "RemoteMemoryBackend",
    "HybridMemoryBackend",
    "get_memory_backend",
    "MemoryStorage",
]
