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

    # Facturación CFDI con el PAC simulado (SC-05). El RFC por omisión es el de pruebas del SAT.
    emisor_rfc: str = "EKU9003173C9"
    emisor_nombre: str = "FRUTERIA FRUTIS PRUEBAS"
    emisor_regimen: str = "626"
    emisor_cp: str = "06000"
    timbres_contratados: int = Field(default=1000, ge=0)
    cfdi_dir: Path = Path(__file__).resolve().parents[1] / "cfdi"


@lru_cache
def get_settings() -> Settings:
    return Settings()
