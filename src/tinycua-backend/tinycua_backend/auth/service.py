"""Authentication service for user registration and login."""

import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from tinycua_backend.auth.core import (
    create_api_key,
    create_jwt_token,
    hash_api_key,
    hash_password,
    verify_password,
)
from tinycua_backend.auth.models import APIKey, User
from tinycua_backend.auth.schemas import TokenResponse
from tinycua_backend.tenant.models import Tenant


class AuthService:
    """Authentication service for user management."""

    def __init__(self, db: Session) -> None:
        """Initialize the auth service.

        Args:
            db: Database session
        """
        self._db = db

    def register(
        self,
        email: str,
        password: str,
        tenant_name: str | None = None,
    ) -> TokenResponse:
        """Register a new user with a new tenant.

        Args:
            email: User email address
            password: User password
            tenant_name: Name for the new tenant

        Returns:
            TokenResponse with access token and user info

        Raises:
            ValueError: If user already exists
        """
        tenant = Tenant(name=tenant_name or f"Tenant for {email}")
        self._db.add(tenant)
        self._db.flush()

        user = User(
            tenant_id=tenant.id,
            email=email,
            password_hash=hash_password(password),
        )
        self._db.add(user)

        try:
            self._db.flush()
        except IntegrityError:
            self._db.rollback()
            raise ValueError("User with this email already exists in this tenant")

        raw_key = create_api_key()
        api_key = APIKey(
            tenant_id=tenant.id,
            name="Default API Key",
            key_hash=hash_api_key(raw_key),
            key_prefix=raw_key[:8],
            scopes=[],
            is_active=True,
        )
        self._db.add(api_key)

        try:
            self._db.commit()
        except IntegrityError:
            self._db.rollback()
            raise ValueError("User with this email already exists in this tenant")

        self._db.refresh(user)
        token = create_jwt_token(str(user.id), str(tenant.id), user.email)

        return TokenResponse(
            access_token=token,
            tenant_id=str(tenant.id),
            user_id=str(user.id),
            api_key=raw_key,
        )

    def login(
        self,
        email: str,
        password: str,
        tenant_id: str,
    ) -> TokenResponse:
        """Login a user with email and password.

        Args:
            email: User email address
            password: User password
            tenant_id: Tenant ID

        Returns:
            TokenResponse with access token and user info

        Raises:
            ValueError: If credentials are invalid
        """
        try:
            tenant_uuid = uuid.UUID(tenant_id)
        except ValueError:
            raise ValueError("Invalid tenant ID format")

        user = (
            self._db.query(User)
            .filter(User.email == email, User.tenant_id == tenant_uuid)
            .first()
        )
        if not user:
            raise ValueError("Invalid credentials")

        if not user.password_hash or not verify_password(password, user.password_hash):
            raise ValueError("Invalid credentials")

        token = create_jwt_token(str(user.id), str(user.tenant_id), user.email)

        return TokenResponse(
            access_token=token,
            tenant_id=str(user.tenant_id),
            user_id=str(user.id),
        )
