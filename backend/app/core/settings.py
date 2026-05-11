from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = Field(default="development", alias="APP_ENV")
    database_path: Path = Field(default=Path("data/weekendgo.sqlite3"), alias="DATABASE_PATH")
    mcp_config_path: Path = Field(default=Path("config/mcp_config.yaml"), alias="MCP_CONFIG_PATH")
    backend_host: str = Field(default="0.0.0.0", alias="BACKEND_HOST")
    backend_port: int = Field(default=8000, alias="BACKEND_PORT")
    frontend_host: str = Field(default="0.0.0.0", alias="FRONTEND_HOST")
    frontend_port: int = Field(default=3000, alias="FRONTEND_PORT")
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_base_url: str | None = Field(default=None, alias="OPENAI_BASE_URL")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")
    cors_origins_raw: str = Field(default="http://localhost:3000", alias="CORS_ORIGINS")

    @property
    def cors_origins(self) -> list[str]:
        configured = [origin.strip() for origin in self.cors_origins_raw.split(",") if origin.strip()]
        frontend_port_origins = [
            f"http://localhost:{self.frontend_port}",
            f"http://127.0.0.1:{self.frontend_port}",
            f"http://0.0.0.0:{self.frontend_port}",
        ]
        return list(dict.fromkeys([*configured, *frontend_port_origins]))


@lru_cache
def get_settings() -> Settings:
    return Settings()
