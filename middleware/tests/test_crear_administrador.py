"""Comando para crear el primer Administrador de una instalación de producción."""
from unittest.mock import MagicMock

import pytest

from app import crear_administrador as comando
from app.repositories import admin as repo
from app.repositories import auditoria
from app.security.passwords import verificar_password


@pytest.fixture
def conn(monkeypatch):
    c = MagicMock()
    c.execute.return_value.scalar.return_value = 1  # id del rol Administrador
    monkeypatch.setattr(repo, "en_uso", lambda c, col, v, e: False)
    monkeypatch.setattr(repo, "insertar_usuario", MagicMock(return_value=7))
    monkeypatch.setattr(auditoria, "registrar", MagicMock())
    return c


def test_crea_el_administrador_con_el_hash_del_login(conn):
    assert comando.crear_administrador(conn, "Dueña Frutis", "duena", "duena@frutis.mx", "Segura2026!") == 7
    datos, hash_ = repo.insertar_usuario.call_args.args[1:]
    assert datos["id_rol"] == 1 and datos["usuario"] == "duena" and verificar_password("Segura2026!", hash_)
    assert "Segura2026!" not in str(auditoria.registrar.call_args)
    conn.commit.assert_called_once()


@pytest.mark.parametrize(("args", "mensaje"), [
    (("Dueña", "duena", "duena@frutis.mx", "corta"), "al menos 8"),
    (("Dueña", "du ena", "duena@frutis.mx", "Segura2026!"), "usuario"),
    (("Dueña", "duena", "sin-arroba", "Segura2026!"), "correo"),
])
def test_rechaza_datos_invalidos(conn, args, mensaje):
    with pytest.raises(comando.NoSePuede, match=mensaje):
        comando.crear_administrador(conn, *args)
    repo.insertar_usuario.assert_not_called()


def test_usuario_repetido(conn, monkeypatch):
    monkeypatch.setattr(repo, "en_uso", lambda c, col, v, e: col == "usuario")
    with pytest.raises(comando.NoSePuede, match="Ya existe un usuario con ese usuario"):
        comando.crear_administrador(conn, "Dueña", "admin", "duena@frutis.mx", "Segura2026!")


def test_sin_catalogos_no_hay_rol(conn):
    conn.execute.return_value.scalar.return_value = None
    with pytest.raises(comando.NoSePuede, match="catálogos"):
        comando.crear_administrador(conn, "Dueña", "duena", "duena@frutis.mx", "Segura2026!")
