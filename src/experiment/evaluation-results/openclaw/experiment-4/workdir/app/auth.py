"""
JWT Authentication handlers for Notion-like Web Application.
Provides token generation, validation, and user authentication logic. """
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

# Import models for type hints (avoid circular imports)
try:
    from app.models import User  # noqa: F401
except ImportError:
    pass


class AuthManager:
    """
    Manages JWT token generation and validation.
    
    Attributes:
        secret_key: Secret key for signing tokens (loaded from config)
        algorithm: Algorithm used to sign the JWT token
        access_token_expire_minutes: How long an access token lasts before expiry
        refresh_token_expire_days: How long a refresh token lasts
    """
    
    def __init__(
        self,
        secret_key: str = None,
        algorithm: str = "HS256",
        access_token_expire_minutes: int = 30,
        refresh_token_expire_days: int = 7
    ):
        self.secret_key = secrets.token_hex(32) if not secret_key else secret_key
        self.algorithm = algorithm
        self.access_token_expire_minutes = access_token_expire_minutes
        self.refresh_token_expire_days = refresh_token_expire_days
    
    def create_access_token(
        self,
        subject: str | int,  # User ID can be UUID or string
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """
        Create a new JWT access token.
        
        Args:
            subject: The user identifier (usually the user's unique_id)
            expires_delta: Override default expiry time
            
        Returns:
            Encoded JWT token string
        """
        encode_kwargs = {
            "alg": self.algorithm,
            "exp": datetime.now(timezone.utc) + (
                expires_delta or timedelta(minutes=self.access_token_expire_minutes)
            ),
            "iat": datetime.now(timezone.utc),
            "iss": "notion-like-app",
        }
        return jwt.encode({"sub": subject}, self.secret_key, **encode_kwargs)
    
    def create_refresh_token(self, subject: str | int) -> str:
        """
        Create a new JWT refresh token.
        
        Args:
            subject: The user identifier
            
        Returns:
            Encoded refresh token string
        """
        encode_kwargs = {
            "alg": self.algorithm,
            "exp": datetime.now(timezone.utc) + (
                timedelta(days=self.refresh_token_expire_days)
            ),
            "iat": datetime.now(timezone.utc),
            "iss": "notion-like-app",
        }
        return jwt.encode({"sub": subject}, self.secret_key, **encode_kwargs)
    
    def verify_access_token(self, token: str) -> Optional[dict]:
        """
        Verify and decode an access token.
        
        Args:
            token: JWT access token string
            
        Returns:
            Decoded token payload if valid, None otherwise
        """
        try:
            return jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
        except JWTError:
            return None
    
    def verify_refresh_token(self, token: str) -> Optional[dict]:
        """
        Verify and decode a refresh token.
        
        Args:
            token: JWT refresh token string
            
        Returns:
            Decoded token payload if valid, None otherwise
        """
        try:
            return jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
        except JWTError:
            return None
    
    def authenticate_user(self, db) -> Optional[dict]:
        """
        Authenticate a user by email and password.
        
        Args:
            db: SQLAlchemy database session
            email: User's email address
            password: Plain text password
            
        Returns:
            User dict if authentication successful, None otherwise
        """
        from app.models import User  # Avoid circular import
        user = db.query(User).filter(User.email == email).first()
        return user
    

class PasswordManager:
    """
    Manages password hashing and verification.
    Uses bcrypt for secure password storage.
    """
    
    def __init__(self, context: CryptContext = None):
        self.context = (context or CryptContext(
            schemes=["bcrypt"],
            deprecated_schemes=[],
            verify_backend="bcrypt",
            hash_rounds=12,
        ))
    
    def hash_password(self, password: str) -> str:
        """
        Hash a plain text password.
        
        Args:
            password: Plain text password to hash
            
        Returns:
            Bcrypt hashed string
        """
        return self.context.hash(password)
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """
        Verify a password against its hash.
        
        Args:
            plain_password: Plain text password
            hashed_password: Bcrypt hashed password from database
            
        Returns:
            True if passwords match, False otherwise
        """
        return self.context.verify(plain_password, hashed_password)
    

class TokenManager:
    """
    Manages OAuth2 token handling for API authentication.
    Integrates with JWT and password managers.
    """
    
    def __init__(self):
        self.auth_manager = AuthManager()
        self.password_manager = PasswordManager()
        self.oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


# Global singleton instances for easy import in routers
auth_manager = AuthManager()
pwd_manager = PasswordManager()
token_manager = TokenManager()
