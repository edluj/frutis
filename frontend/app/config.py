"""Configuración de la terminal (nunca lleva credenciales de la base).

Se lee de `frutis.ini`, junto al ejecutable o en la carpeta desde la que se arranca, y las
variables de entorno `FRUTIS_*` tienen prioridad sobre el archivo.
"""
import configparser
import os
import sys
from dataclasses import dataclass
from pathlib import Path

ARCHIVO = "frutis.ini"
SECCION = "terminal"


@dataclass(frozen=True)
class Config:
    # Dirección del middleware en la LAN. Sin certificado el middleware solo escucha en 127.0.0.1.
    api_url: str
    # Autoridad certificadora local con la que se valida el certificado del servidor (fin de CERT_NONE).
    ca_path: str | None
    terminal: str
    demo: bool
    timeout: float


def carpeta_base() -> Path:
    """Carpeta del ejecutable empaquetado; en desarrollo, la carpeta frontend/."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def _leer_archivo() -> tuple[dict[str, str], Path | None]:
    for carpeta in (carpeta_base(), Path.cwd()):
        ruta = carpeta / ARCHIVO
        if ruta.is_file():
            ini = configparser.ConfigParser()
            ini.read(ruta, encoding="utf-8")
            return (dict(ini[SECCION]) if ini.has_section(SECCION) else {}), carpeta
    return {}, None


def cargar(demo_forzado: bool = False) -> Config:
    archivo, carpeta = _leer_archivo()

    def valor(clave: str, omision: str) -> str:
        return os.environ.get(f"FRUTIS_{clave.upper()}") or archivo.get(clave) or omision

    ca = valor("ca_path", "")
    # Una ruta relativa del archivo se toma desde la carpeta del propio frutis.ini.
    if ca and carpeta and not os.environ.get("FRUTIS_CA_PATH") and not Path(ca).is_absolute():
        ca = str(carpeta / ca)
    return Config(
        api_url=valor("api_url", "http://127.0.0.1:8443").rstrip("/"),
        ca_path=ca or None,
        terminal=valor("terminal", "POS-1"),
        demo=demo_forzado or valor("demo", "") == "1",
        timeout=float(valor("timeout", "5")),
    )
