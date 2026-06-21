"""Application Configuration"""


class Settings:
    """Application settings and configuration"""
    
    # Database
    DATABASE_URL = "sqlite:///./notion_clone.db"
    
    # Server
    HOST = "0.0.0.0"
    PORT = 8000
    
    # JWT Secret (generate a random one for production)
    SECRET_KEY = "your-secret-key-change-in-production"


settings = Settings()
