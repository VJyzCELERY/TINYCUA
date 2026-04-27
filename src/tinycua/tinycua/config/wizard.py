"""Setup wizard for first-time TinyCUA users."""

from __future__ import annotations

import base64
import json
import logging
import os
import platform
import re
import secrets
import warnings
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from tinycua_sdk.core.config import SDKConfig

logger = logging.getLogger(__name__)


class WizardError(Exception):
    """Base exception for wizard errors."""
    pass


class WizardValidationError(WizardError):
    """Exception for validation errors."""
    pass


def is_first_startup(config_dir: str | Path | None = None) -> bool:
    """Check if this is the first startup (no config, db, or credentials exist).

    Args:
        config_dir: Optional config directory path. Defaults to ~/.tinycua.

    Returns:
        True if no configuration exists, False otherwise.
    """
    from tinycua.config.user_config import UserConfig

    config_path = config_dir or UserConfig.DEFAULT_CONFIG_DIR
    config_path = Path(config_path)

    config_file = config_path / "config.yaml"
    db_file = config_path / "data.db"
    credentials_file = config_path / "credentials.enc"
    return not (config_file.exists() or db_file.exists() or credentials_file.exists())


class SetupWizard:
    """Interactive setup wizard for first-time users."""

    DEFAULT_LLM_PROVIDER = "lmstudio"
    DEFAULT_LLM_MODEL = "qwen/qwen3.5-9b"
    DEFAULT_LLM_BASE_URL = "http://localhost:1234/v1"

    def __init__(self, config_dir: Path | None = None):
        """Initialize the wizard.

        Args:
            config_dir: Optional config directory. Defaults to ~/.tinycua.
        """
        from tinycua.config.user_config import UserConfig

        self.config_dir = config_dir or UserConfig.DEFAULT_CONFIG_DIR
        self.storage_mode: str | None = None
        self.username: str | None = None
        self.email: str | None = None
        self.password: str | None = None
        self.llm_provider: str | None = None
        self.llm_model: str | None = None
        self.llm_base_url: str | None = None
        self.llm_api_key: str | None = None
        self._completed = False

    def set_storage_mode(self, mode: str) -> None:
        """Set the storage mode.

        Args:
            mode: Either 'local' or 'remote'.

        Raises:
            WizardError: If mode is invalid.
        """
        if mode not in ("local", "remote"):
            raise WizardError("Storage mode must be 'local' or 'remote'")
        self.storage_mode = mode

    def set_account(
        self, username: str, email: str, password: str
    ) -> None:
        """Set account credentials.

        Args:
            username: Username for the account.
            email: Email address.
            password: Password for the account.
        """
        self.validate_account(username, email, password)
        self.username = username
        self.email = email
        self.password = password

    def _get_fernet_key(self) -> bytes:
        """Derive or retrieve a Fernet encryption key.

        Tries the OS keyring first, then falls back to a key file
        derived from system-specific information.

        Returns:
            URL-safe base64-encoded Fernet key.
        """
        try:
            import keyring
            from keyring.errors import KeyringError

            service = "tinycua"
            username = "credentials_key"
            stored_key = keyring.get_password(service, username)
            if stored_key is not None:
                return stored_key.encode()

            key = Fernet.generate_key()
            keyring.set_password(service, username, key.decode())
            return key
        except (ImportError, RuntimeError, OSError):
            logger.debug("Keyring unavailable, using fallback key derivation")
        except KeyringError as e:
            logger.warning("Keyring operation failed: %s", e)

        # Fallback: derive key from system info and store in key file
        key_file = self.config_dir / ".key"
        if key_file.exists():
            return key_file.read_bytes()

        # Use environment variable for headless environments, or generate a random password
        env_password = os.environ.get("TINYCUA_FERNET_KEY")
        if env_password:
            password = env_password.encode()
        else:
            password = secrets.token_bytes(32)
            logger.warning(
                "Keyring unavailable and TINYCUA_FERNET_KEY not set. "
                "Generated a random fallback key. Set TINYCUA_FERNET_KEY "
                "for stable headless operation."
            )

        salt = platform.node().encode()
        try:
            salt += os.getlogin().encode()
        except OSError:
            salt += b"unknown_user"
        salt += b"tinycua_salt_v1"
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt[:16],
            iterations=480000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password))
        self.config_dir.mkdir(parents=True, exist_ok=True)
        key_file.write_bytes(key)
        key_file.chmod(0o600)
        return key

    def save_credentials(self) -> None:
        """Save credentials to a secure file using Fernet encryption."""
        if not all([self.username, self.email, self.password]):
            return

        credentials_file = self.config_dir / "credentials.enc"
        self.config_dir.mkdir(parents=True, exist_ok=True)

        fernet = Fernet(self._get_fernet_key())
        data = json.dumps({
            "username": self.username,
            "email": self.email,
            "password": self.password,
        }).encode()

        encrypted = fernet.encrypt(data)
        credentials_file.write_bytes(encrypted)
        credentials_file.chmod(0o600)

    def load_credentials(self) -> bool:
        """Load credentials from file if it exists.

        Supports Fernet-encrypted credentials with a backward-compatible
        base64 fallback that emits a deprecation warning.

        Returns:
            True if credentials were loaded, False otherwise.
        """
        credentials_file = self.config_dir / "credentials.enc"
        if not credentials_file.exists():
            return False

        encrypted = credentials_file.read_bytes()

        # Try Fernet decryption first
        try:
            from cryptography.fernet import InvalidToken

            fernet = Fernet(self._get_fernet_key())
            data = fernet.decrypt(encrypted)
            creds = json.loads(data)
            self.username = creds["username"]
            self.email = creds["email"]
            self.password = creds["password"]
            return True
        except (InvalidToken, ValueError, TypeError, OSError):
            pass

        # Fallback: backward-compatible base64 read
        try:
            data = base64.b64decode(encrypted)
            creds = json.loads(data)
            self.username = creds["username"]
            self.email = creds["email"]
            self.password = creds["password"]
            warnings.warn(
                "Loaded credentials using legacy base64 encoding. "
                "Re-run the wizard to upgrade to Fernet encryption.",
                DeprecationWarning,
                stacklevel=2,
            )
            return True
        except (ValueError, TypeError, OSError):
            return False

    def validate_account(
        self,
        username: str,
        email: str,
        password: str,
        confirm_password: str | None = None,
    ) -> None:
        """Validate account credentials.

        Args:
            username: Username to validate.
            email: Email to validate.
            password: Password to validate.
            confirm_password: Optional confirmation password.

        Raises:
            WizardValidationError: If validation fails.
        """
        if not username or not username.strip():
            raise WizardValidationError("Username cannot be empty")

        if not email or not email.strip():
            raise WizardValidationError("Email cannot be empty")

        email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(email_pattern, email):
            raise WizardValidationError("Invalid email format")

        if not password or len(password) < 8:
            raise WizardValidationError("Password must be at least 8 characters")

        if not re.search(r"[A-Z]", password):
            raise WizardValidationError("Password must contain at least one uppercase letter")

        if not re.search(r"[a-z]", password):
            raise WizardValidationError("Password must contain at least one lowercase letter")

        if not re.search(r"\d", password):
            raise WizardValidationError("Password must contain at least one digit")

        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
            raise WizardValidationError("Password must contain at least one special character")

        if confirm_password is not None and password != confirm_password:
            raise WizardValidationError("Passwords do not match")

    def set_llm_config(
        self,
        provider: str,
        model: str,
        base_url: str,
        api_key: str | None = None,
    ) -> None:
        """Set LLM provider configuration.

        Args:
            provider: LLM provider name.
            model: Model identifier.
            base_url: Base URL for the API.
            api_key: Optional API key.
        """
        self.llm_provider = provider
        self.llm_model = model
        self.llm_base_url = base_url
        self.llm_api_key = api_key

    def complete(self) -> SDKConfig:
        """Complete the wizard and save configuration.

        Returns:
            The saved SDKConfig instance.

        Raises:
            WizardError: If wizard is not fully configured.
        """
        if self.storage_mode is None:
            raise WizardError("Storage mode not set")

        if self.username is None:
            raise WizardError("Account not configured")

        if self.llm_provider is None:
            raise WizardError("LLM provider not configured")

        config = self._build_config()
        self._save_config(config)
        self._completed = True
        return config

    def _build_config(self) -> SDKConfig:
        """Build the SDKConfig from wizard values.

        Returns:
            Configured SDKConfig instance.
        """
        llm_config: dict[str, Any] = {
            "provider": self.llm_provider or self.DEFAULT_LLM_PROVIDER,
            "model": self.llm_model or self.DEFAULT_LLM_MODEL,
            "base_url": self.llm_base_url or self.DEFAULT_LLM_BASE_URL,
        }

        if self.llm_api_key:
            from pydantic import SecretStr
            llm_config["api_key"] = SecretStr(self.llm_api_key)

        if self.storage_mode == "local":
            memory_url = f"sqlite:///{self.config_dir.as_posix()}/data.db"
        else:
            memory_url = "sqlite:///./tinycua.db"

        memory_config: dict[str, Any] = {
            "database_url": memory_url,
        }

        config_data: dict[str, Any] = {
            "llm": llm_config,
            "memory": memory_config,
        }

        return SDKConfig(**config_data)

    def _save_config(self, config: SDKConfig) -> None:
        """Save configuration to file.

        Args:
            config: SDKConfig to save.
        """
        import sqlite3

        from tinycua.config.user_config import UserConfig

        config_file = self.config_dir / "config.yaml"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        UserConfig.save(config, path=config_file)
        self.save_credentials()

        if self.storage_mode == "local":
            db_path = self.config_dir / "data.db"
            if not db_path.exists():
                conn = sqlite3.connect(db_path)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS sessions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id TEXT UNIQUE NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS messages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id TEXT NOT NULL,
                        role TEXT NOT NULL,
                        content TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                    )
                """)
                conn.commit()
                conn.close()


def is_lmstudio_available() -> bool:
    """Check if LM Studio is running and available.

    Returns:
        True if LM Studio is available, False otherwise.
    """
    try:
        import requests
        response = requests.get("http://localhost:1234/v1/models", timeout=2)
        return response.status_code == 200
    except (requests.ConnectionError, requests.Timeout):
        return False


def test_connection(url: str) -> bool:
    """Test connection to a remote backend.

    Args:
        url: The backend URL to test.

    Returns:
        True if connection successful, False otherwise.
    """
    import requests

    # Try health endpoint first
    try:
        response = requests.get(f"{url.rstrip('/')}/health", timeout=5)
        if response.status_code == 200:
            return True
    except (requests.ConnectionError, requests.Timeout):
        pass

    # Fallback to base URL
    try:
        response = requests.get(url, timeout=5)
        return response.status_code in (200, 404)
    except (requests.ConnectionError, requests.Timeout):
        return False


def show_welcome() -> None:
    """Display welcome message for first-time users."""
    print("\n" + "=" * 50)
    print("  Welcome to TinyCUA!")
    print("=" * 50)
    print("\nThis appears to be your first time running TinyCUA.")
    print("Let's get you set up with a quick configuration wizard.")
    print()


def prompt_storage_mode() -> str:
    """Prompt user to select storage mode.

    Returns:
        Either 'local' or 'remote'
    """
    print("\n--- Select Storage Mode ---")
    print("1. Local - Store data in ~/.tinycua/ (recommended)")
    print("2. Remote - Connect to a backend server")
    print()

    while True:
        choice = input("Choose (1/2): ").strip()
        if choice == "1":
            return "local"
        elif choice == "2":
            return "remote"
        print("Please enter 1 or 2.")


def prompt_account_creation() -> dict[str, str]:
    """Prompt user for account creation.

    Returns:
        Dictionary with username, email, and password.
    """
    print("\n--- Create Your Account ---")

    while True:
        username = input("Username: ").strip()
        if username:
            break
        print("Username cannot be empty.")

    while True:
        email = input("Email: ").strip()
        if email:
            break
        print("Email cannot be empty.")

    while True:
        password = input("Password (min 8 characters): ").strip()
        if len(password) >= 8:
            break
        print("Password must be at least 8 characters.")

    while True:
        confirm = input("Confirm password: ").strip()
        if confirm == password:
            break
        print("Passwords do not match.")

    return {"username": username, "email": email, "password": password}


def prompt_llm_configuration() -> dict[str, str]:
    """Prompt user for LLM provider configuration.

    Returns:
        Dictionary with provider, model, base_url, and api_key.
    """
    print("\n--- Configure LLM Provider ---")
    print("Default: LM Studio at http://localhost:1234/v1")
    print("Default model: qwen/qwen3.5-9b")
    print()

    provider = input(f"Provider [{SetupWizard.DEFAULT_LLM_PROVIDER}]: ").strip()
    if not provider:
        provider = SetupWizard.DEFAULT_LLM_PROVIDER

    model = input(f"Model [{SetupWizard.DEFAULT_LLM_MODEL}]: ").strip()
    if not model:
        model = SetupWizard.DEFAULT_LLM_MODEL

    base_url = input(f"Base URL [{SetupWizard.DEFAULT_LLM_BASE_URL}]: ").strip()
    if not base_url:
        base_url = SetupWizard.DEFAULT_LLM_BASE_URL

    api_key = input("API Key (optional, press Enter to skip): ").strip()

    result = {
        "provider": provider,
        "model": model,
        "base_url": base_url,
    }
    if api_key:
        result["api_key"] = api_key

    return result


def run_wizard() -> SDKConfig:
    """Run the complete setup wizard.

    Returns:
        The completed SDKConfig instance.
    """
    from tinycua.config.user_config import UserConfig

    config_dir = UserConfig.ensure_config_dir()
    wizard = SetupWizard(config_dir=config_dir)

    show_welcome()

    mode = prompt_storage_mode()
    wizard.set_storage_mode(mode)

    account = prompt_account_creation()
    wizard.set_account(
        account["username"],
        account["email"],
        account["password"],
    )

    llm_config = prompt_llm_configuration()
    wizard.set_llm_config(
        provider=llm_config["provider"],
        model=llm_config["model"],
        base_url=llm_config["base_url"],
        api_key=llm_config.get("api_key"),
    )

    config = wizard.complete()

    config_path = config_dir / "config.yaml"
    print("\n" + "=" * 50)
    print("  Setup Complete!")
    print("=" * 50)
    print(f"\nConfiguration saved to: {config_path}")
    if mode == "local":
        db_path = config_dir / "data.db"
        print(f"Database saved to: {db_path}")
    print("\nRun 'tinycua repl' to begin.")

    return config
