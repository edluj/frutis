"""Pruebas sin MySQL: la conexión y los repositorios se sustituyen."""
import os

os.environ["FRUTIS_DB_USER"] = "prueba"
os.environ["FRUTIS_DB_PASSWORD"] = "prueba"
os.environ["FRUTIS_JWT_SECRET"] = "secreto-solo-para-pruebas-0123456789"
os.environ["FRUTIS_SESSION_MINUTES"] = "60"

from unittest.mock import MagicMock  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db import get_conn  # noqa: E402
from app.main import app  # noqa: E402
from app.repositories import auditoria, usuarios  # noqa: E402
from app.security.passwords import hash_password  # noqa: E402
from app.security.tokens import crear_token  # noqa: E402

PASSWORD = "Frutis2026!"
HASH = hash_password(PASSWORD)
CAJERO = {
    "id_usuario": 2, "usuario": "cajero1", "nombre_completo": "Cajero de prueba",
    "password_hash": HASH, "id_rol": 2, "rol": "Cajero", "bloqueado": 0,
}
PERMISOS_CAJERO = [
    {"modulo": "pos", "puede_ver": 1, "puede_crear": 1, "puede_editar": 0, "puede_eliminar": 0},
]


@pytest.fixture
def conn():
    return MagicMock()


@pytest.fixture
def cliente(conn, monkeypatch):
    def _conn():
        yield conn

    app.dependency_overrides[get_conn] = _conn
    monkeypatch.setattr(usuarios, "buscar_activo", lambda c, i: CAJERO if i == 2 else None)
    monkeypatch.setattr(usuarios, "permisos_del_rol", lambda c, r: PERMISOS_CAJERO)
    monkeypatch.setattr(auditoria, "registrar", MagicMock())
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def cabeceras():
    return {"Authorization": f"Bearer {crear_token(2)}"}
