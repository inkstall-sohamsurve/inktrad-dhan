"""
Configuration settings for the Inktrad backend.
Loads environment variables and provides application settings.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # MongoDB Configuration
    MONGODB_URL: str = "mongodb://localhost:27017"
    DATABASE_NAME: str = "inktrad_db"
    
    # JWT Configuration
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours
    
    # Encryption Key for DHAN Credentials
    ENCRYPTION_KEY: str
    
    # DHAN Master Account (for WebSocket feed)
    DHAN_MASTER_CLIENT_ID: str
    DHAN_MASTER_ACCESS_TOKEN: str
    
    # Server Configuration
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    RELOAD: bool = False
    
    # CORS Origins
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173"
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True
    )
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins from comma-separated string."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]


# Global settings instance
settings = Settings()
