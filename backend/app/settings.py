from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_env: str = "dev"
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    database_url: str
    redis_url: str

    model_provider: str = "none"
    openai_base_url: str | None = None
    openai_api_key: str | None = None
    openai_model: str | None = None

    default_language: str = "ru"
    artifacts_dir: str = "./var/artifacts"

    # Comma-separated allowlist for CORS in dev, e.g. "http://localhost:5173,http://127.0.0.1:5173"
    cors_allow_origins: str | None = None

    google_service_account_file: str | None = None
    google_calendar_id: str | None = None

    # Google OAuth (user) integration for Drive/Docs
    google_oauth_client_id: str | None = None
    google_oauth_client_secret: str | None = None
    google_oauth_redirect_url: str | None = None
    frontend_base_url: str | None = None
    auth_state_secret: str | None = None

    # Local auth (email/password + seed phrase)
    auth_jwt_secret: str | None = None
    auth_jwt_ttl_seconds: int = 60 * 60 * 24 * 14  # 14 days
    auth_seed_secret: str | None = None


settings = Settings()  # type: ignore[call-arg]
