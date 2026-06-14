"""
ParamX Hunter - Application Configuration
Uses pydantic-settings for environment-based configuration
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    VERSION: str = "1.0.0"
    APP_NAME: str = "ParamX Hunter"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://paramx:paramx@localhost:5432/paramx"
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 40

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_CACHE_TTL: int = 3600  # 1 hour

    # JWT
    SECRET_KEY: str = "CHANGE-ME-IN-PRODUCTION-USE-256-BIT-RANDOM-KEY"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    # Crawling
    DEFAULT_CONCURRENCY: int = 50
    MAX_SCAN_CONCURRENCY: int = 200
    MAX_REQUESTS_PER_SCAN: int = 500_000

    # Auth
    REQUIRE_EMAIL_VERIFICATION: bool = False

    # Reporting
    REPORTS_DIR: str = "/tmp/paramx_reports"
    LOGO_PATH: str | None = None


settings = Settings()
