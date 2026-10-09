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
    SCHEDULER_RUN_ON_STARTUP: bool = False
    WORKER_EMBEDDED_ENABLED: bool = True

    # Ingestion Freshness & Limits
    RSS_MAX_ENTRIES_PER_FEED: int = 25
    RSS_MAX_AGE_DAYS: int = 3
    RSS_ONLY_YESTERDAY_AND_TODAY: bool = True
    RSS_TODAY_FRESHNESS_BONUS: float = 0.05
    INGESTION_TOP_K: int = 10
    MIN_CLIENT_WINNER_SCORE: float = 0.60
    SCRIPT_GROUNDING_THRESHOLD: float = 0.75

    # LLM Provider Configuration (gemini | openai | claude | anthropic)
    LLM_PROVIDER: Literal["gemini", "openai", "claude", "anthropic"] = "openai"
    GEMINI_API_KEY: str | None = None
    GEMINI_MODEL: str = "gemini-2.5-flash"
    OPENAI_API_KEY: str | None = None
    OPENAI_MODEL: str = "gpt-4o-mini"
    ANTHROPIC_API_KEY: str | None = None
    ANTHROPIC_MODEL: str = "claude-3-5-sonnet-20241022"
    CLAUDE_API_KEY: str | None = None
    CLAUDE_MODEL: str | None = None

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
    VIDEO_ENGINE: Literal["mock", "programmatic", "heygen", "did"] = "programmatic"
    VIDEO_ASPECT_RATIO: Literal["16:9", "9:16"] = "16:9"
    TTS_PROVIDER: Literal["mock", "edge_tts", "elevenlabs"] = "edge_tts"
    TTS_DEFAULT_VOICE: str = "en-US-ChristopherNeural"
    HEYGEN_API_KEY: str | None = None
    HEYGEN_TEST_MODE: bool = False
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

    @property
    def effective_claude_api_key(self) -> str | None:
        return self.ANTHROPIC_API_KEY or self.CLAUDE_API_KEY

    @property
    def effective_claude_model(self) -> str:
        return self.CLAUDE_MODEL or self.ANTHROPIC_MODEL or "claude-3-5-sonnet-20241022"

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
            if self.LLM_PROVIDER in ("claude", "anthropic") and not self.effective_claude_api_key:
                raise ValueError("ANTHROPIC_API_KEY or CLAUDE_API_KEY must be configured when LLM_PROVIDER is claude in production")
            if self.STORAGE_PROVIDER in ("s3", "r2") and (not self.S3_ACCESS_KEY_ID or not self.S3_SECRET_ACCESS_KEY):
                raise ValueError("S3_ACCESS_KEY_ID and S3_SECRET_ACCESS_KEY must be configured when using S3/R2 storage in production")
        return self


settings = Settings()
