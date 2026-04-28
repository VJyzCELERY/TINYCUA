"""Tests for Fernet credential encryption."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

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

    def test_load_missing_credentials(self, tmp_path: Path) -> None:
        """Test loading when credentials file does not exist."""
        wizard = SetupWizard(config_dir=tmp_path)
        assert wizard.load_credentials() is False
