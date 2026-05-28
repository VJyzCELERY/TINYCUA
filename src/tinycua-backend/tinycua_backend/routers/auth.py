"""Authentication routes for registration and login."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from tinycua_backend.auth import create_jwt_token, hash_api_key
from tinycua_backend.database import get_db
from tinycua_backend.models.tenant import Tenant
from tinycua_backend.models.user import User

router = APIRouter(prefix="/v1/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    """Request model for registration."""

    email: str
    password: str
    tenant_name: str | None = None


class LoginRequest(BaseModel):
    """Request model for login."""

    email: str
    password: str


class TokenResponse(BaseModel):
    """Response model for auth tokens."""

    access_token: str
    token_type: str = "bearer"
    tenant_id: str
    user_id: str


@router.post(
    "/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED
)
async def register(
    request: RegisterRequest, db: Session = Depends(get_db)
) -> TokenResponse:
    """Register a new user and tenant.

    Args:
        request: Registration request
        db: Database session

    Returns:
        JWT token
    """
    # Check if user exists
    existing_user = db.query(User).filter(User.email == request.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User already exists",
        )

    # Create tenant
    tenant = Tenant(name=request.tenant_name or f"Tenant for {request.email}")
    db.add(tenant)
    db.flush()

    # Create user
    user = User(
        tenant_id=str(tenant.id),
        email=request.email,
        password_hash=hash_api_key(request.password),
    )
    db.add(user)
    db.flush()

    # Create API key
    from tinycua_backend.models.api_key import APIKey

    api_key = APIKey(
        tenant_id=str(tenant.id),
        name="Default API Key",
        key_hash=hash_api_key(f"tcu_{request.password}"),
        scopes=[],
        is_active=True,
    )
    db.add(api_key)
    db.commit()

    # Generate JWT token
    token = create_jwt_token(str(user.id), str(tenant.id))

    return TokenResponse(
        access_token=token,
        tenant_id=str(tenant.id),
        user_id=str(user.id),
    )


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """Login with email and password.

    Args:
        request: Login request
        db: Database session

    Returns:
        JWT token
    """
    user = db.query(User).filter(User.email == request.email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    expected_hash = hash_api_key(request.password)
    if user.password_hash != expected_hash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    token = create_jwt_token(str(user.id), str(user.tenant_id))

    return TokenResponse(
        access_token=token,
        tenant_id=str(user.tenant_id),
        user_id=str(user.id),
    )
