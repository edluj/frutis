"""Configuración de la terminal; se lee del entorno (nunca lleva credenciales de la base)."""
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    # Dirección del middleware en la LAN. Sin certificado el middleware solo escucha en 127.0.0.1.
    api_url: str
    # Autoridad certificadora local con la que se valida el certificado del servidor (fin de CERT_NONE).
    ca_path: str | None
    terminal: str
    demo: bool
    timeout: float


def cargar(demo_forzado: bool = False) -> Config:
    return Config(
        api_url=os.environ.get("FRUTIS_API_URL", "http://127.0.0.1:8443").rstrip("/"),
        ca_path=os.environ.get("FRUTIS_CA_PATH") or None,
        terminal=os.environ.get("FRUTIS_TERMINAL", "POS-1"),
        demo=demo_forzado or os.environ.get("FRUTIS_DEMO", "") == "1",
        timeout=float(os.environ.get("FRUTIS_TIMEOUT", "5")),
    )
