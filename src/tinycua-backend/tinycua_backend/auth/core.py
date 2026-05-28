"""Authentication module for tinycua-backend.

This module is a backward-compatible re-export shim.
Responsibilities have been split into focused submodules:
  - passwords.py: password hashing
  - jwt.py: JWT token creation and validation
  - api_keys.py: API key creation and verification
  - dependencies.py: FastAPI dependencies and CurrentTenant
"""

from tinycua_backend.auth.api_keys import (  # noqa: F401
    MAX_API_KEYS_PER_REQUEST,
    MIN_API_KEY_LENGTH,
    create_api_key,
    hash_api_key,
    verify_api_key,
)
from tinycua_backend.auth.dependencies import (  # noqa: F401
    CurrentTenant,
    get_current_tenant,
    get_or_create_system_tenant,
)
from tinycua_backend.auth.jwt import create_jwt_token, decode_jwt_token  # noqa: F401
from tinycua_backend.auth.passwords import hash_password, verify_password  # noqa: F401

# Re-export pwd_context for backward compatibility
from tinycua_backend.auth.passwords import pwd_context  # noqa: F401
