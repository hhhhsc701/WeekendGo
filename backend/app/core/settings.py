from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = Field(default="development", alias="APP_ENV")
    database_path: Path = Field(default=Path("data/weekendgo.sqlite3"), alias="DATABASE_PATH")
    mcp_config_path: Path = Field(default=Path("config/mcp_config.yaml"), alias="MCP_CONFIG_PATH")
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_base_url: str | None = Field(default=None, alias="OPENAI_BASE_URL")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")
    cors_origins: list[str] = Field(default=["http://localhost:3000"])


@lru_cache
def get_settings() -> Settings:
    return Settings()
