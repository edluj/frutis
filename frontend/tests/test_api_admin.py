"""Roles y permisos (HU-34), bitácora (HU-35) y cajas y métodos de pago (HU-41) contra un middleware simulado."""
from datetime import date

import pytest

from app.datos import ErrorNegocio
from tests.test_api_caja_devoluciones import datos_con

ROLES = [{"id_rol": 1, "nombre": "Administrador", "usuarios": 1, "es_sistema": True},
         {"id_rol": 2, "nombre": "Cajero", "usuarios": 3, "es_sistema": False}]
PERMISOS = [{"modulo": "pos", "puede_ver": True, "puede_crear": True, "puede_editar": False, "puede_eliminar": False},
            {"modulo": "inventario", "puede_ver": True, "puede_crear": False, "puede_editar": False, "puede_eliminar": False}]


def test_roles_y_matriz_del_cajero():
    datos, _ = datos_con({"GET /admin/roles": (200, ROLES), "GET /admin/roles/2/permisos": (200, PERMISOS)})
    assert [(r["nombre"], r["usuarios"], r["fijo"]) for r in datos.roles()] == [("Administrador", 1, True), ("Cajero", 3, False)]
    p = datos.permisos_de("Cajero")
    assert p["matriz"]["pos"] == (1, 1, 0, 0) and p["matriz"]["finanzas"] == (0, 0, 0, 0)
    assert p["especiales"] == {"credito": True, "devoluciones": False, "cortes": False}


def test_guardar_permisos_manda_solo_los_modulos_con_algo():
    datos, mw = datos_con({"GET /admin/roles": (200, ROLES), "PUT /admin/roles/2/permisos": (204, None)})
    matriz = {"pos": (1, 1, 0, 0), "finanzas": (0, 0, 0, 0), "reportes": (1, 0, 0, 0)}
    datos.guardar_permisos("Cajero", matriz, {"credito": True})
    assert mw.recibido["PUT /admin/roles/2/permisos"] == {"permisos": [
        {"modulo": "pos", "puede_ver": True, "puede_crear": True, "puede_editar": False, "puede_eliminar": False},
        {"modulo": "reportes", "puede_ver": True, "puede_crear": False, "puede_editar": False, "puede_eliminar": False}]}


def test_bitacora_con_textos_de_pantalla_y_filtros():
    registros = [
        {"fecha": "2026-11-27T09:36:00", "usuario": "compras1", "modulo": "auth", "accion": "login_fallido",
         "detalle": "Contraseña incorrecta", "ip": "127.0.0.1"},
        {"fecha": "2026-11-27T09:30:00", "usuario": "admin", "modulo": "admin", "accion": "usuario_alta",
         "detalle": "lgomez · rol Cajero", "ip": None}]
    datos, mw = datos_con({"GET /admin/auditoria": (200, registros)})
    todas = datos.lista_auditoria()
    assert [(a["modulo"], a["accion"], a["tono"]) for a in todas] == [
        ("Acceso", "Inicio de sesión fallido", "rojo"), ("Administración", "Usuario registrado", "gris")]
    assert todas[1]["ip"] == "—"
    filtradas = datos.lista_auditoria("admin", "Todos", "Todas", date(2026, 11, 1), None)
    assert mw.recibido["GET /admin/auditoria"] == {"desde": "2026-11-01"}
    assert [a["usuario"] for a in filtradas] == ["admin"]


def test_cajas_y_metodos():
    datos, mw = datos_con({
        "GET /admin/cajas": (200, [{"terminal": "POS-01", "abierta": True, "cajero": "Cajero de prueba",
                                    "ultima_apertura": "2026-11-04T10:41:44"}]),
        "GET /admin/metodos-pago": (200, [{"id_metodo": 6, "nombre": "Cheque", "clave_sat": "02", "es_efectivo": False,
                                           "es_credito": False, "activo": False}]),
        "PUT /admin/metodos-pago/6": (204, None)})
    c = datos.configuracion_cajas()
    assert c["cajas"][0]["estado"] == "Abierta · Cajero de prueba" and c["metodos"][0]["nombre"] == "Cheque"
    datos.activar_metodo(6, True)
    assert mw.recibido["PUT /admin/metodos-pago/6"] == {"activo": True}


@pytest.mark.parametrize(("llamada", "texto"), [
    (lambda d: d.agregar_caja("Caja 3", "POS-03", "192.168.1.13"), "Las terminales se registran solas"),
    (lambda d: d.guardar_dispositivos({}), "SC-05")])
def test_cajas_y_dispositivos_explican_por_que_no_se_guardan(llamada, texto):
    datos, _ = datos_con({})
    with pytest.raises(ErrorNegocio, match=texto):
        llamada(datos)
