"""Remote connection manager for TinyCUA."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import TYPE_CHECKING, Any, Optional
import httpx
from urllib.parse import urlparse

try:
    import keyring
    from keyring.errors import KeyringError
    HAS_KEYRING = True
except ImportError:
    HAS_KEYRING = False
    KeyringError = Exception  # type: ignore[misc,assignment]

if TYPE_CHECKING:
    from tinycua.clients import BackendClient
    from tinycua.remote.sync_engine import SyncEngine

logger = logging.getLogger(__name__)

KEYRING_SERVICE = "tinycua"


def validate_backend_url(url: str) -> tuple[bool, str]:
    """Validate Backend URL.

    Args:
        url: The URL to validate.

    Returns:
        tuple: (is_valid, error_message)
    """
    if not url:
        return False, "URL is required"

    try:
        parsed = urlparse(url)
        if not parsed.scheme:
            return False, "URL must include scheme (http/https)"
        if parsed.scheme not in ("http", "https"):
            return False, "URL scheme must be http or https"
        if not parsed.netloc:
            return False, "URL must include valid host"
        if parsed.scheme == "http" and not url.startswith("http://localhost"):
            return False, "HTTP is only allowed for localhost"
        return True, ""
    except (ValueError, TypeError) as e:
        return False, f"Invalid URL: {e}"


@dataclass
class RemoteConfig:
    """Configuration for remote backend connection."""

    backend_url: str
    email: str | None = None
    access_token: str | None = None
    refresh_token: str | None = None
    token_expires_at: datetime | None = None
    api_key: str | None = None


@dataclass
class ConnectionStatus:
    """Connection status information."""

    connected: bool = False
    mode: str = "local"
    last_sync: str | None = None
    error: str | None = None


class RemoteConnectionManager:
    """Manager for remote Backend connections.

    Handles connection lifecycle, authentication, and status tracking
    for remote Backend communication.
    """

    def __init__(
        self,
        backend_url: str | None = None,
        api_key: str | None = None,
        email: str | None = None,
        password: str | None = None,
        config: Optional[RemoteConfig] = None,
    ) -> None:
        """Initialize RemoteConnectionManager.

        Args:
            backend_url: Base URL of the backend server
            api_key: API key for authentication
            email: Email for login (alternative to api_key)
            password: Password for login (alternative to api_key)
            config: RemoteConfig object (alternative to individual params)
        """
        if config:
            self.config = config
        else:
            self.config = RemoteConfig(
                backend_url=backend_url or "",
                email=email,
                api_key=api_key,
            )

        if email and password and HAS_KEYRING:
            self._set_secure_password(email, password)

        self._client: Optional[BackendClient] = None
        self._connected: bool = False
        self._mode: str = "local"
        self._status = ConnectionStatus()
        self._api_key: Optional[str] = None
        self._sync_engine: Optional[Any] = None
        self._last_connection_attempt: float = 0
        self._min_connection_interval: float = 5.0
        self._token_expires_at: Optional[datetime] = None

    def _get_secure_password(self, email: str) -> Optional[str]:
        """Get password from secure storage (keyring).

        Args:
            email: Email associated with the password

        Returns:
            Password from keyring or None if not found.
        """
        if not HAS_KEYRING or not email:
            return None
        try:
            return keyring.get_password(KEYRING_SERVICE, email)
        except (KeyringError, OSError, ValueError) as e:
            logger.warning("Failed to retrieve password from keyring: %s", e)
            return None

    def _set_secure_password(self, email: str, password: str) -> bool:
        """Store password in secure storage (keyring).

        Args:
            email: Email associated with the password
            password: Password to store

        Returns:
            True if successful, False otherwise.
        """
        if not HAS_KEYRING or not email or not password:
            return False
        try:
            keyring.set_password(KEYRING_SERVICE, email, password)
            logger.info("Stored password securely for %s", email)
            return True
        except (KeyringError, OSError, ValueError) as e:
            logger.warning("Failed to store password in keyring: %s", e)
            return False

    @property
    def backend_url(self) -> str:
        """Get the backend URL.

        Returns:
            Backend URL string.
        """
        return self.config.backend_url

    @property
    def is_connected(self) -> bool:
        """Check if connected to remote backend.

        Returns:
            True if connected, False otherwise.
        """
        return self._connected

    @property
    def mode(self) -> str:
        """Get current mode (local or remote).

        Returns:
            Mode string.
        """
        return self._mode

    @property
    def status(self) -> ConnectionStatus:
        """Get current connection status.

        Returns:
            ConnectionStatus object.
        """
        return self._status

    def load_config(self, config: RemoteConfig | None = None) -> bool:
        """Load remote config from UserConfig.

        Args:
            config: Optional RemoteConfig object. If not provided, loads from UserConfig.

        Returns:
            True if config loaded successfully, False otherwise.
        """
        if config is not None:
            self.config = config
            logger.info("Loaded remote config for %s", config.backend_url)
            return True

        try:
            from tinycua.config import UserConfig

            user_config = UserConfig.load()
            if user_config.backend_url:
                api_key_value = None
                if user_config.llm and user_config.llm.api_key:
                    api_key_value = user_config.llm.api_key.get_secret_value()
                self.config = RemoteConfig(
                    backend_url=user_config.backend_url,
                    api_key=api_key_value,
                )
                self._api_key = api_key_value
                logger.info("Loaded remote config from UserConfig: %s", self.config.backend_url)
                return True
        except (OSError, ValueError, ImportError) as e:
            logger.warning("Failed to load remote config from UserConfig: %s", e)
        return False

    async def connect(
        self,
        email: str | None = None,
        password: str | None = None,
        api_key: str | None = None,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        timeout: float = 30.0,
    ) -> bool:
        """Connect to remote backend with auto-reconnect support.

        Args:
            email: Optional email for authentication
            password: Optional password for authentication
            api_key: Optional API key for authentication
            max_retries: Maximum number of connection attempts
            retry_delay: Delay between retries in seconds
            timeout: Connection timeout in seconds

        Returns:
            True if connection successful, False otherwise.
        """
        is_valid, error_msg = validate_backend_url(self.config.backend_url)
        if not is_valid:
            self._status = ConnectionStatus(
                connected=False,
                mode="local",
                error=f"Invalid backend URL: {error_msg}",
            )
            logger.error("Cannot connect: %s", error_msg)
            return False

        last_error = None
        from tinycua.clients import BackendClient

        email = email or self.config.email
        password = password or (self._get_secure_password(email) if email else None)
        api_key = api_key or self.config.api_key

        now = time.time()
        time_since_last_attempt = now - self._last_connection_attempt
        if time_since_last_attempt < self._min_connection_interval:
            wait_time = self._min_connection_interval - time_since_last_attempt
            logger.warning(
                "Rate limiting connection attempts. Waiting %.1fs before next attempt...",
                wait_time,
            )
            await asyncio.sleep(wait_time)
            now = time.time()

        self._last_connection_attempt = now

        if self._client is None:
            self._client = BackendClient(
                base_url=self.config.backend_url,
                api_key=api_key,
                email=email,
                password=password,
                timeout=int(timeout),
            )

        for attempt in range(max_retries):
            try:
                if email and password:
                    try:
                        await self._client.login(email=email, password=password)
                    except (ConnectionError, OSError, ValueError, httpx.HTTPStatusError) as e:
                        logger.warning("Login failed: %s", e)

                if await self._client.health_check():
                    self._connected = True
                    self._mode = "remote"
                    self._status = ConnectionStatus(connected=True, mode="remote")
                    logger.info("Connected to %s", self.config.backend_url)
                    return True

                if attempt < max_retries - 1:
                    delay = retry_delay * (2 ** attempt)
                    logger.warning(
                        "Connection attempt %d failed, retrying in %ds...",
                        attempt + 1,
                        delay,
                    )
                    await asyncio.sleep(delay)

            except (ConnectionError, OSError, ValueError, httpx.HTTPStatusError) as e:
                last_error = e
                delay = retry_delay * (2 ** attempt)
                logger.warning(
                    "Connection attempt %d failed: %s, retrying in %.1fs...",
                    attempt + 1,
                    e,
                    delay,
                )
                await asyncio.sleep(delay)

        logger.exception("Failed to connect to remote backend after all retries")
        self._connected = False
        self._mode = "local"
        error_msg = str(last_error) if last_error else "Connection failed"
        self._status = ConnectionStatus(
            connected=False,
            mode="local",
            error=error_msg,
        )
        return False

    async def disconnect(self) -> None:
        """Disconnect from remote backend."""
        if self._client is not None:
            try:
                await self._client.close()
            except (OSError, ValueError):
                pass
            self._client = None
        self._connected = False
        self._mode = "local"
        self._status = ConnectionStatus(connected=False, mode="local")
        logger.info("Disconnected from remote backend")

    async def test_connection(self, url: str | None = None) -> tuple[bool, str]:
        """Test connection to backend.

        Args:
            url: Optional URL to test. If None, uses stored config URL.

        Returns:
            Tuple of (success, error_message).
        """
        test_url = url or self.config.backend_url
        if not test_url:
            return False, "No URL provided"

        is_valid, error_msg = validate_backend_url(test_url)
        if not is_valid:
            return False, error_msg

        client = self._client
        if (
            client is None
            or (url is not None and getattr(client, "base_url", None) != test_url)
        ):
            from tinycua.clients import BackendClient

            if client is not None:
                try:
                    await client.close()
                except (OSError, ValueError):
                    pass
            email = self.config.email
            password = self._get_secure_password(email) if email else None
            self._client = BackendClient(
                base_url=test_url,
                api_key=self.config.api_key,
                email=email,
                password=password,
            )
            client = self._client

        try:
            success = await client.health_check()
            return (success, "") if success else (False, "Health check failed")
        except (ConnectionError, OSError, ValueError, httpx.HTTPStatusError) as e:
            error_msg = f"{type(e).__name__}: {e}"
            logger.exception("Connection test failed: %s", error_msg)
            return (False, error_msg)

    def get_client(self) -> Optional[BackendClient]:
        """Get the BackendClient instance.

        Returns:
            BackendClient instance or None if not connected.
        """
        return self._client

    def update_last_sync(self, timestamp: str) -> None:
        """Update the last sync timestamp in connection status.

        Args:
            timestamp: ISO format timestamp of last sync.
        """
        self._status.last_sync = timestamp
        logger.debug("Updated last_sync to %s", timestamp)

    def get_sync_engine(self) -> "SyncEngine":
        """Get the SyncEngine instance.

        Returns:
            SyncEngine instance or None if not initialized.
        """
        if self._sync_engine is None:
            from tinycua.remote.sync_engine import SyncEngine
            self._sync_engine = SyncEngine(connection_manager=self)
        return self._sync_engine

    async def refresh_token(self) -> bool:
        """Refresh authentication token.

        Returns:
            True if token refresh successful, False otherwise.
        """
        if not self._client or not self._connected:
            logger.warning("Cannot refresh token: not connected")
            return False

        try:
            if hasattr(self._client, "refresh_token"):
                result = await self._client.refresh_token()
                if hasattr(result, "expires_at"):
                    self._token_expires_at = result.expires_at
                else:
                    self._token_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
                logger.info("Token refreshed successfully")
                return True
            else:
                logger.debug("Token refresh not supported by backend client")
                return False
        except (ConnectionError, OSError, ValueError, httpx.HTTPStatusError) as e:
            logger.exception("Token refresh failed: %s: %s", type(e).__name__, e)
        return False

__all__ = ["RemoteConnectionManager", "RemoteConfig", "ConnectionStatus", "validate_backend_url"]
