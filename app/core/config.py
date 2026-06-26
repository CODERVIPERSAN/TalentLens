from typing import List, Union

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "TalentLens"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    ENVIRONMENT: str = "development"

    API_V1_STR: str = "/api/v1"

    # Defaults to a local SQLite database so the app runs out of the box.
    # Override with a PostgreSQL URL in production, e.g.
    # postgresql://user:password@localhost:5432/talentlens
    DATABASE_URL: str = "sqlite+aiosqlite:///./talentlens.db"
    TEST_DATABASE_URL: str = ""

    # Optional: when empty, AI features fall back to deterministic local logic.
    OPENAI_API_KEY: str = ""

    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    REDIS_URL: str = "redis://localhost:6379/0"

    ALLOWED_ORIGINS: Union[str, List[str]] = [
        "http://localhost:3000",
        "http://localhost:8000",
    ]

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def _split_origins(cls, value: Union[str, List[str]]) -> List[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @property
    def openai_enabled(self) -> bool:
        key = self.OPENAI_API_KEY.strip()
        return bool(key) and key != "your_openai_api_key_here"


settings = Settings()
