"""Tests for Fernet credential encryption and backward-compatible base64 fallback."""

from __future__ import annotations

import base64
import json
import warnings
from pathlib import Path
from unittest.mock import patch

import pytest

from cryptography.fernet import Fernet

from tinycua.config.wizard import SetupWizard


class TestCredentialsEncryption:
    """Tests for Fernet credential encryption roundtrip."""

    def test_fernet_roundtrip(self, tmp_path: Path) -> None:
        """Test that credentials can be encrypted and decrypted with Fernet."""
        key = Fernet.generate_key()
        wizard = SetupWizard(config_dir=tmp_path)

        with patch.object(wizard, "_get_fernet_key", return_value=key):
            wizard.set_account("testuser", "test@example.com", "Secret123!")
            wizard.save_credentials()

            # Verify file exists
            creds_file = tmp_path / "credentials.enc"
            assert creds_file.exists()

            # Verify content is valid Fernet token
            raw = creds_file.read_bytes()
            fernet = Fernet(key)
            decrypted = fernet.decrypt(raw)
            data = json.loads(decrypted)
            assert data["username"] == "testuser"
            assert data["email"] == "test@example.com"
            assert data["password"] == "Secret123!"

    def test_load_credentials_fernet(self, tmp_path: Path) -> None:
        """Test loading Fernet-encrypted credentials."""
        key = Fernet.generate_key()
        wizard = SetupWizard(config_dir=tmp_path)

        with patch.object(wizard, "_get_fernet_key", return_value=key):
            wizard.set_account("testuser", "test@example.com", "Secret123!")
            wizard.save_credentials()

            # Create fresh wizard instance to load
            wizard2 = SetupWizard(config_dir=tmp_path)
            with patch.object(wizard2, "_get_fernet_key", return_value=key):
                assert wizard2.load_credentials() is True
                assert wizard2.username == "testuser"
                assert wizard2.email == "test@example.com"
                assert wizard2.password == "Secret123!"

    def test_base64_fallback_with_warning(self, tmp_path: Path) -> None:
        """Test backward-compatible base64 fallback emits deprecation warning."""
        wizard = SetupWizard(config_dir=tmp_path)
        wizard.set_account("legacyuser", "legacy@example.com", "Legacy123!")

        # Save with base64 instead of Fernet
        creds_file = tmp_path / "credentials.enc"
        data = json.dumps({
            "username": wizard.username,
            "email": wizard.email,
            "password": wizard.password,
        }).encode()
        creds_file.write_bytes(base64.b64encode(data))

        wizard2 = SetupWizard(config_dir=tmp_path)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = wizard2.load_credentials()
            assert result is True
            assert wizard2.username == "legacyuser"
            assert wizard2.email == "legacy@example.com"
            assert wizard2.password == "Legacy123!"
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "legacy base64" in str(w[0].message).lower()

    def test_load_missing_credentials(self, tmp_path: Path) -> None:
        """Test loading when credentials file does not exist."""
        wizard = SetupWizard(config_dir=tmp_path)
        assert wizard.load_credentials() is False
