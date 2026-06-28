"""
Configuration settings for Notion-like Web Application.
Contains database, security, and application-wide settings. """
import os
from datetime import timedelta
from functools import lru_cache


class Settings:
    """Application configuration class."""
    
    # Database Configuration
    DATABASE_URL: str = "sqlite:///./notion.db"
    SQLALCHEMY_DATABASE_URI: str = DATABASE_URL.replace("sqlite://", "postgresql+asyncpg://") if os.getenv("DATABASE_TYPE") == "postgres" else DATABASE_URL
    
    # Security Settings
    SECRET_KEY: str = os.environ.get(
        "SECRET_KEY",
        "change-me-in-production-secure-random-key-here-minimum-32-chars-long"
    )
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # CORS Settings
    CORS_ORIGINS: list[str] = os.environ.get(
        "CORS_ORIGIS",
        "http://localhost:3000,http://127.0.0.1:3000"
    ).split(",") if os.getenv("CORS_ORIGIS") else []
    
    # Application Settings
    APP_NAME: str = "Notion-like App"
    API_VERSION: str = "v1"
    DEBUG: bool = True  # Set to False in production
    
    # File Upload Settings
    UPLOAD_DIR: str = os.path.join(os.path.dirname(__file__), "../uploads/images")
    MAX_UPLOAD_SIZE_MB: int = 10
    ALLOWED_EXTENSIONS: set[str] = {"png", "jpg", "jpeg", "gif", "webp", "svg", "pdf"}
    
    # Pagination Settings
    PAGE_LIMIT: int = 20
    BLOCK_PAGE_LIMIT: int = 50
    SEARCH_RESULTS_LIMIT: int = 100
    
    @classmethod
    def create(cls) -> "Settings":
        """Create and return a new settings instance."""
        cls.DATABASE_URL = os.environ.get(
            "DATABASE_URL",
            f"sqlite:///{os.path.join(os.getcwd(), 'notion.db')}"
        )
        cls.SECRET_KEY = os.environ.get("SECRET_KEY", cls.SECRET_KEY)
        return cls()


# Global settings instance (singleton pattern via lru_cache for thread safety)
@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings.create()
