"""Configuración del middleware; se lee de deploy/.env o del entorno (EC-15)."""
from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = Path(__file__).resolve().parents[2] / "deploy" / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FRUTIS_", env_file=ENV_FILE, extra="ignore")

    db_host: str = "127.0.0.1"
    db_port: int = 3306
    db_name: str = "frutis"
    db_user: str
    db_password: SecretStr

    bind_host: str = "127.0.0.1"
    port: int = 8443
    cert_path: str = ""
    key_path: str = ""
    jwt_secret: SecretStr = Field(min_length=32)
    session_minutes: int = Field(default=60, gt=0)


@lru_cache
def get_settings() -> Settings:
    return Settings()
