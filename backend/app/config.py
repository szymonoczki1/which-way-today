from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/config.py -> parents[2] is the repo root, so .env.example /
# .env are read from one place regardless of whether uvicorn/pytest/docker
# is invoked from the repo root or from backend/.
REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    database_url: str = "sqlite:///./whichway.db"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    # Optional: without a (non-empty) key, recommendations are rule-based.
    openai_api_key: str | None = None
    # Change if this model is retired; failures fall back to rules anyway.
    openai_model: str = "gpt-4o-mini"

    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    @field_validator("openai_model", mode="before")
    @classmethod
    def _default_model_when_blank(cls, value: object) -> object:
        # docker compose passes an unset OPENAI_MODEL as "".
        return value if isinstance(value, str) and value.strip() else "gpt-4o-mini"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
