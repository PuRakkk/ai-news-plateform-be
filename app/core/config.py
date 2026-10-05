from typing import Literal
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_ENV: Literal["development", "test", "production"] = "development"
    APP_TIMEZONE: str = "Asia/Phnom_Penh"
    DB_USER: str = "postgres"
    DB_PASSWORD: str = "postgres"
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "ai_news_db"

    ADMIN_AUTH_SECRET: str = "change_this_to_a_long_admin_secret"
    JWT_SECRET: str = "change_this_to_a_long_random_secret"
    JWT_EXPIRE_MINUTES: int = 1440
    AUTH_COOKIE_NAME: str = "ai_news_auth"
    AUTH_COOKIE_SECURE: bool = False
    FRONTEND_CORS_ORIGINS: str = "http://localhost:3000"
    SECRET_ENCRYPTION_KEY: str | None = None

    # Redis & Task Queue
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str | None = None
    REDIS_DB: int = 0

    # Scheduler Configuration
    SCHEDULER_ENABLED: bool = True
    SCHEDULER_CRON_HOUR: int = 7
    SCHEDULER_CRON_MINUTE: int = 0

    # LLM Provider Configuration (gemini | openai)
    LLM_PROVIDER: Literal["gemini", "openai"] = "gemini"
    GEMINI_API_KEY: str | None = None
    GEMINI_MODEL: str = "gemini-2.5-flash"
    OPENAI_API_KEY: str | None = None
    OPENAI_MODEL: str = "gpt-4o"

    # Media Storage Configuration (local | s3 | r2)
    STORAGE_PROVIDER: Literal["local", "s3", "r2"] = "local"
    STORAGE_LOCAL_DIR: str = "media"
    STORAGE_BASE_URL: str = "http://localhost:8000/media"
    S3_ENDPOINT_URL: str | None = None  # e.g., Cloudflare R2 endpoint URL
    S3_ACCESS_KEY_ID: str | None = None
    S3_SECRET_ACCESS_KEY: str | None = None
    S3_BUCKET_NAME: str = "ai-news-media"
    S3_PUBLIC_BASE_URL: str | None = None

    # Video & Voice Engine (mock | programmatic | heygen | did)
    VIDEO_ENGINE: Literal["mock", "programmatic", "heygen", "did"] = "mock"
    HEYGEN_API_KEY: str | None = None
    ELEVENLABS_API_KEY: str | None = None

    @property
    def is_development(self) -> bool:
        return self.APP_ENV == "development"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.FRONTEND_CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def redis_url(self) -> str:
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        if self.APP_ENV == "production":
            if self.JWT_SECRET == "change_this_to_a_long_random_secret" or not self.JWT_SECRET:
                raise ValueError("JWT_SECRET must be configured with a secure random key in production")
            if not self.SECRET_ENCRYPTION_KEY:
                raise ValueError("SECRET_ENCRYPTION_KEY must be configured in production")
            if self.LLM_PROVIDER == "gemini" and not self.GEMINI_API_KEY:
                raise ValueError("GEMINI_API_KEY must be configured when LLM_PROVIDER is gemini in production")
            if self.LLM_PROVIDER == "openai" and not self.OPENAI_API_KEY:
                raise ValueError("OPENAI_API_KEY must be configured when LLM_PROVIDER is openai in production")
            if self.STORAGE_PROVIDER in ("s3", "r2") and (not self.S3_ACCESS_KEY_ID or not self.S3_SECRET_ACCESS_KEY):
                raise ValueError("S3_ACCESS_KEY_ID and S3_SECRET_ACCESS_KEY must be configured when using S3/R2 storage in production")
        return self


settings = Settings()
