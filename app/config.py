from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from typing import Optional
import os


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # ignore unknown Railway env vars
    )

    # Application
    APP_NAME: str = "LIFEOS"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    SECRET_KEY: str = "change-me-in-production-use-long-random-string"

    # Database (Railway injects DATABASE_URL automatically when Postgres is linked)
    DATABASE_URL: str = "sqlite:///./lifeos.db"

    # Admin
    ADMIN_PASSWORD: str = "change-me-admin-password"

    # Security
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 10080
    SESSION_COOKIE_NAME: str = "lifeos_session"
    SESSION_MAX_AGE: int = 1209600

    # CORS
    ALLOWED_ORIGINS: str = "*"

    # File uploads
    MAX_UPLOAD_SIZE: int = 2097152
    ALLOWED_AVATAR_TYPES: str = "image/jpeg,image/png,image/webp"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
