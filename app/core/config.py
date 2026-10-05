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

    @property
    def is_development(self) -> bool:
        return self.APP_ENV == "development"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.FRONTEND_CORS_ORIGINS.split(",") if origin.strip()]

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        if self.APP_ENV == "production":
            if self.JWT_SECRET == "change_this_to_a_long_random_secret" or not self.JWT_SECRET:
                raise ValueError("JWT_SECRET must be configured with a secure random key in production")
            if not self.SECRET_ENCRYPTION_KEY:
                raise ValueError("SECRET_ENCRYPTION_KEY must be configured in production")
        return self


settings = Settings()
