"""Authentication endpoints with JWT-based auth."""
from datetime import datetime, timedelta
from typing import Optional
import bcrypt
import jwt as pyjwt
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.api.database import get_db
from backend.models.schema import User

router = APIRouter()


SECRET_KEY = "your-secret-key-change-in-production"  # Change in production!
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))


def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


async def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create a JWT refresh token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def verify_current_user(token: str, db: Session):
    """Verify the current user from JWT token and return user data."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired. Please login again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Fetch user from database
    db_user = db.query(User).filter(User.username == username).first()
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return {"username": db_user.username, "email": db_user.email, "id": db_user.id}


@router.post("/register")
async def register(
    email: str,
    username: str,
    password: str,
    full_name: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Register a new user."""
    # Check if user already exists
    existing_user = db.query(User).filter(
        (User.email == email) | (User.username == username)
    ).first()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email or username already registered",
        )

    # Hash password
    hashed_password = get_password_hash(password)

    # Create new user
    db_user = User(
        email=email,
        username=username,
        full_name=full_name,
        hashed_password=hashed_password,
    )

    try:
        db.add(db_user)
        db.commit()
        db.refresh(db_user)

        # Generate access and refresh tokens
        access_token = await create_access_token(data={"sub": username})
        refresh_token = await create_refresh_token(data={"sub": username})

        return {
            "message": "Registration successful",
            "user_id": db_user.id,
            "username": db_user.username,
            "email": db_user.email,
            "access_token": access_token,
            "token_type": "bearer",
            "refresh_token": refresh_token,
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/login")
async def login(
    email: str,
    password: str,
    db: Session = Depends(get_db),
):
    """Login and get access/refresh tokens."""
    # Find user by email
    db_user = db.query(User).filter(User.email == email).first()

    if not db_user or not verify_password(password, db_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Generate tokens
    access_token = await create_access_token(data={"sub": db_user.username})
    refresh_token = await create_refresh_token(data={"sub": db_user.username})

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "refresh_token": refresh_token,
        "username": db_user.username,
        "email": db_user.email,
        "user_id": db_user.id,
    }


@router.post("/logout")
async def logout():
    """Logout user (in stateless JWT auth, this is mostly informational)."""
    return {"message": "Logged out successfully"}


@router.get("/me")
async def get_current_user_info(user_data: dict = Depends(verify_current_user)):
    """Get current user info."""
    return user_data


@router.post("/refresh")
async def refresh_token_endpoint(
    refresh_token: str,
    db: Session = Depends(get_db),
):
    """Refresh access token using refresh token."""
    try:
        # Decode and verify the refresh token (same verification as access token)
        payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])

        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            )

        # Get user from database to verify they still exist
        db_user = db.query(User).filter(User.username == username).first()
        if not db_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User no longer exists",
            )

        # Create new access token
        new_access_token = await create_access_token(data={"sub": username})

        return {
            "access_token": new_access_token,
            "token_type": "bearer",
        }
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token expired",
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )
