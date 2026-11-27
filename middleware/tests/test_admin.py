"""Administración de usuarios (HU-18)."""
from unittest.mock import MagicMock

import pytest

from app.repositories import admin as repo
from app.repositories import auditoria, usuarios
from app.security.passwords import verificar_password
from app.security.tokens import crear_token
from tests.conftest import CAJERO

ADMIN = {**CAJERO, "id_usuario": 1, "usuario": "admin", "id_rol": 1, "rol": "Administrador"}
PERMISOS = {1: [{"modulo": "admin", "puede_ver": 1, "puede_crear": 1, "puede_editar": 1, "puede_eliminar": 1}]}
ROLES = {1: {"id_rol": 1, "nombre": "Administrador", "activo": 1, "es_sistema": 1},
         2: {"id_rol": 2, "nombre": "Cajero", "activo": 1, "es_sistema": 0},
         5: {"id_rol": 5, "nombre": "Inactivo", "activo": 0, "es_sistema": 0}}
FILAS = {1: {"id_usuario": 1, "nombre_completo": "Administrador de prueba", "usuario": "admin", "correo": "admin@frutis.test",
             "id_rol": 1, "rol": "Administrador", "ultimo_acceso": None, "activo": 1},
         2: {"id_usuario": 2, "nombre_completo": "Cajero de prueba", "usuario": "cajero1", "correo": "cajero1@frutis.test",
             "id_rol": 2, "rol": "Cajero", "ultimo_acceso": None, "activo": 1}}
ALTA = {"nombre_completo": "Laura Gómez", "usuario": "lgomez", "correo": "laura@frutis.test", "id_rol": 2,
        "password": "Temporal2026"}
EDITA_CAJERO = {"nombre_completo": "Cajero de prueba", "usuario": "cajero1", "correo": "cajero1@frutis.test", "id_rol": 2}
EDITA_ADMIN = {"nombre_completo": "Administrador de prueba", "usuario": "admin", "correo": "admin@frutis.test", "id_rol": 1}


@pytest.fixture
def admin(cliente, monkeypatch):
    monkeypatch.setattr(usuarios, "buscar_activo", lambda c, i: {1: ADMIN, 2: CAJERO}.get(i))
    monkeypatch.setattr(usuarios, "permisos_del_rol", lambda c, r: PERMISOS.get(r, []))
    monkeypatch.setattr(repo, "rol", lambda c, i: ROLES.get(i))
    monkeypatch.setattr(repo, "usuario", lambda c, i, bloquear=False: FILAS.get(i))
    monkeypatch.setattr(repo, "en_uso", lambda c, col, v, e: False)
    return {"Authorization": f"Bearer {crear_token(1, 0)}"}


@pytest.fixture
def escritura(monkeypatch):
    mocks = {"insertar_usuario": MagicMock(return_value=2), "actualizar_usuario": MagicMock(),
             "cambiar_password": MagicMock()}
    for nombre, mock in mocks.items():
        monkeypatch.setattr(repo, nombre, mock)
    mocks["cerrar_sesiones"] = MagicMock()
    monkeypatch.setattr(usuarios, "cerrar_sesiones", mocks["cerrar_sesiones"])
    return mocks


def test_solo_administracion_gestiona_usuarios(cliente, admin, cabeceras):
    assert cliente.get("/admin/usuarios", headers=cabeceras).status_code == 403
    assert cliente.post("/admin/usuarios", json=ALTA, headers=cabeceras).status_code == 403


def test_alta_guarda_el_hash_y_nunca_devuelve_la_contrasena(cliente, admin, escritura):
    r = cliente.post("/admin/usuarios", json=ALTA, headers=admin)
    assert r.status_code == 201
    datos, hash_guardado = escritura["insertar_usuario"].call_args.args[1:]
    assert "password" not in datos and hash_guardado.startswith("pbkdf2_sha256$")
    assert verificar_password("Temporal2026", hash_guardado)
    assert "Temporal2026" not in r.text and "password" not in r.text
    assert "Temporal2026" not in str(auditoria.registrar.call_args)


@pytest.mark.parametrize(("cambio", "campo"), [({"password": None}, "password"), ({"password": "corta"}, "password"),
                                               ({"id_rol": 5}, "rol"), ({"id_rol": 9}, "rol")])
def test_alta_rechazada(cliente, admin, escritura, cambio, campo):
    r = cliente.post("/admin/usuarios", json={**ALTA, **cambio}, headers=admin)
    assert r.json()["campo"] == campo
    escritura["insertar_usuario"].assert_not_called()


@pytest.mark.parametrize(("columna", "campo"), [("usuario", "usuario"), ("correo", "correo")])
def test_usuario_o_correo_repetido(cliente, admin, escritura, monkeypatch, columna, campo):
    monkeypatch.setattr(repo, "en_uso", lambda c, col, v, e: col == columna)
    r = cliente.post("/admin/usuarios", json=ALTA, headers=admin)
    assert r.status_code == 409 and r.json()["campo"] == campo


@pytest.mark.parametrize("cambio", [{"usuario": "a b"}, {"correo": "x"}, {"nombre_completo": "<b>"}, {"activo": "si"}])
def test_alta_invalida_422(cliente, admin, cambio):
    assert cliente.post("/admin/usuarios", json={**ALTA, **cambio}, headers=admin).status_code == 422


def test_no_puede_darse_de_baja_a_si_mismo(cliente, admin, escritura):
    r = cliente.put("/admin/usuarios/1", json={**EDITA_ADMIN, "activo": False}, headers=admin)
    assert r.status_code == 409 and r.json() == {"detail": "No puede darse de baja a sí mismo.", "campo": "estatus"}
    escritura["actualizar_usuario"].assert_not_called()


def test_no_puede_quitarse_el_rol_de_administrador(cliente, admin, escritura):
    r = cliente.put("/admin/usuarios/1", json={**EDITA_ADMIN, "id_rol": 2}, headers=admin)
    assert r.status_code == 409 and r.json()["campo"] == "rol"


def test_editar_sin_contrasena_no_la_cambia_ni_cierra_sesiones(cliente, admin, escritura):
    assert cliente.put("/admin/usuarios/2", json={**EDITA_CAJERO, "password": ""}, headers=admin).status_code == 200
    escritura["cambiar_password"].assert_not_called()
    escritura["cerrar_sesiones"].assert_not_called()


def test_contrasena_nueva_cierra_las_sesiones_del_usuario(cliente, admin, escritura):
    r = cliente.put("/admin/usuarios/2", json={**EDITA_CAJERO, "password": "Nueva2026!"}, headers=admin)
    assert r.status_code == 200
    assert verificar_password("Nueva2026!", escritura["cambiar_password"].call_args.args[2])
    escritura["cerrar_sesiones"].assert_called_once()
    assert "contraseña cambiada" in auditoria.registrar.call_args.args[3]


def test_desactivar_cierra_las_sesiones_y_audita_la_baja(cliente, admin, escritura):
    r = cliente.put("/admin/usuarios/2", json={**EDITA_CAJERO, "activo": False}, headers=admin)
    assert r.status_code == 200
    escritura["cerrar_sesiones"].assert_called_once()
    assert auditoria.registrar.call_args.args[2] == "usuario_baja"


def test_editar_usuario_inexistente_404(cliente, admin):
    assert cliente.put("/admin/usuarios/9", json=EDITA_CAJERO, headers=admin).status_code == 404


def test_roles_activos(cliente, admin, monkeypatch):
    monkeypatch.setattr(repo, "listar_roles", lambda c: [{"id_rol": 1, "nombre": "Administrador"}])
    assert cliente.get("/admin/roles", headers=admin).json() == [{"id_rol": 1, "nombre": "Administrador"}]
