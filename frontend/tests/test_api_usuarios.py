"""Administración de usuarios (HU-18) contra un middleware simulado (rutas de middleware/README.md)."""
from datetime import datetime

import pytest

from app.datos import ErrorNegocio
from tests.test_api_caja_devoluciones import datos_con

ROLES = [{"id_rol": 1, "nombre": "Administrador"}, {"id_rol": 2, "nombre": "Cajero"}]
USUARIO = {"id_usuario": 2, "nombre_completo": "Cajero de prueba", "usuario": "cajero1", "correo": "cajero1@frutis.test",
           "id_rol": 2, "rol": "Cajero", "ultimo_acceso": "2026-11-26T09:15:00", "activo": True}


def test_lista_de_usuarios_filtra_por_el_id_del_rol():
    datos, mw = datos_con({"GET /admin/roles": (200, ROLES), "GET /admin/usuarios": (200, [USUARIO])})
    assert datos.nombres_roles() == ["Administrador", "Cajero"]
    [u] = datos.lista_usuarios("caj", "Cajero")
    assert mw.recibido["GET /admin/usuarios"] == {"busqueda": "caj", "id_rol": "2"}
    assert u["id"] == 2 and u["nombre"] == "Cajero de prueba" and u["ultimo"] == datetime(2026, 11, 26, 9, 15)


def test_alta_manda_la_contrasena_y_editar_sin_ella_manda_nulo():
    datos, mw = datos_con({"GET /admin/roles": (200, ROLES), "POST /admin/usuarios": (201, USUARIO),
                           "PUT /admin/usuarios/2": (200, USUARIO)})
    datos.guardar_usuario(dict(nombre="Laura", usuario="lgomez", correo="l@frutis.test", password="Temporal2026",
                               rol="Cajero", activo=True))
    assert mw.recibido["POST /admin/usuarios"]["password"] == "Temporal2026"
    assert mw.recibido["POST /admin/usuarios"]["id_rol"] == 2
    datos.guardar_usuario(dict(id=2, nombre="Cajero", usuario="cajero1", correo="c@frutis.test", password="",
                               rol="Cajero", activo=False))
    assert mw.recibido["PUT /admin/usuarios/2"]["password"] is None
    assert mw.recibido["PUT /admin/usuarios/2"]["activo"] is False


def test_darse_de_baja_a_si_mismo_marca_estatus():
    datos, _ = datos_con({"GET /admin/roles": (200, ROLES), "PUT /admin/usuarios/1": (
        409, {"detail": "No puede darse de baja a sí mismo.", "campo": "estatus"})})
    with pytest.raises(ErrorNegocio) as exc:
        datos.guardar_usuario(dict(id=1, nombre="Admin", usuario="admin", correo="a@frutis.test", password="",
                                   rol="Administrador", activo=False))
    assert exc.value.campo == "estatus"
