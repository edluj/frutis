"""Apertura (HU-15), corte (HU-09) y devoluciones con autorización del Administrador (HU-30, SC-02)."""
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock

import jwt
import pymysql
import pytest
from sqlalchemy.exc import OperationalError

from app.config import get_settings
from app.repositories import auditoria, pos, usuarios
from app.security.tokens import crear_autorizacion, crear_token, leer_autorizacion
from tests.conftest import HASH, PASSWORD

AHORA = datetime(2026, 11, 24, 8, 0)
CAJA = {"id_caja": 1, "terminal": "POS-01", "fondo_inicial": Decimal("500.00"), "fecha_apertura": AHORA}
ADMIN = {
    "id_usuario": 1, "usuario": "admin", "nombre_completo": "Administrador de prueba", "password_hash": HASH,
    "id_rol": 1, "rol": "Administrador", "es_administrador": 1, "sesion_version": 0, "activo": 1, "bloqueado": 0,
}
CONTADOR = {**ADMIN, "id_usuario": 4, "usuario": "contador1", "rol": "Contador", "es_administrador": 0}


def _error_mysql(codigo, mensaje):
    return OperationalError("CALL", {}, pymysql.err.OperationalError(codigo, mensaje))


@pytest.fixture
def caja_propia(monkeypatch):
    monkeypatch.setattr(pos, "caja_es_de_usuario", lambda c, caja, usuario: True)


# ---------------------------------------------------------------- apertura

def test_apertura_usa_el_cajero_del_token(cliente, cabeceras, monkeypatch):
    sp = MagicMock(return_value=CAJA)
    monkeypatch.setattr(pos, "abrir_caja", sp)
    r = cliente.post("/pos/cajas", json={"terminal": "POS-01", "fondo_inicial": "500.00"}, headers=cabeceras)
    assert r.status_code == 201
    assert r.json()["id_caja"] == 1
    assert sp.call_args.args[1:] == ("POS-01", 2, Decimal("500.00"))
    assert auditoria.registrar.call_args.args[2] == "apertura"


@pytest.mark.parametrize(
    "cuerpo",
    [
        {"terminal": "POS-01", "fondo_inicial": "-1"},
        {"terminal": "POS-01", "fondo_inicial": "10.001"},
        {"terminal": "POS'; DROP TABLE cajas_pos; --", "fondo_inicial": "10"},
        {"terminal": "", "fondo_inicial": "10"},
        {"terminal": "POS-01", "fondo_inicial": "10", "id_usuario": 1},
    ],
)
def test_apertura_invalida_422(cliente, cabeceras, monkeypatch, cuerpo):
    sp = MagicMock()
    monkeypatch.setattr(pos, "abrir_caja", sp)
    assert cliente.post("/pos/cajas", json=cuerpo, headers=cabeceras).status_code == 422
    sp.assert_not_called()


def test_apertura_rechazada_conserva_el_mensaje(cliente, cabeceras, monkeypatch, conn):
    mensaje = "Ya hay una caja abierta en esta terminal."
    monkeypatch.setattr(pos, "abrir_caja", MagicMock(side_effect=_error_mysql(1644, mensaje)))
    r = cliente.post("/pos/cajas", json={"terminal": "POS-01", "fondo_inicial": "0"}, headers=cabeceras)
    assert r.status_code == 409
    assert r.json()["detail"] == mensaje
    conn.rollback.assert_called()
    assert auditoria.registrar.call_args.args[2] == "apertura_rechazada"


def test_apertura_error_interno_no_filtra_detalles(cliente, cabeceras, monkeypatch):
    monkeypatch.setattr(pos, "abrir_caja", MagicMock(side_effect=_error_mysql(1213, "Deadlock en cajas_pos")))
    r = cliente.post("/pos/cajas", json={"terminal": "POS-01", "fondo_inicial": "0"}, headers=cabeceras)
    assert r.status_code == 500
    assert r.json()["detail"] == "No se pudo abrir la caja, intente de nuevo."


# ---------------------------------------------------------------- corte

def test_resumen_sin_caja_404(cliente, cabeceras, monkeypatch):
    monkeypatch.setattr(pos, "caja_abierta_de", lambda c, u: None)
    assert cliente.get("/pos/cortes/actual", headers=cabeceras).status_code == 404


def test_resumen_del_corte(cliente, cabeceras, monkeypatch):
    monkeypatch.setattr(pos, "caja_abierta_de", lambda c, u: CAJA)
    monkeypatch.setattr(pos, "resumen_corte", lambda c, caja: {
        "ventas": [{"metodo": "Efectivo", "es_efectivo": 1, "es_credito": 0, "tickets": 3, "importe": Decimal("300.00")}],
        "cobros_efectivo": {"cantidad": 1, "importe": Decimal("10.00")},
        "devoluciones_efectivo": {"cantidad": 1, "importe": Decimal("20.00")},
        "efectivo_esperado": Decimal("790.00"),
    })
    r = cliente.get("/pos/cortes/actual", headers=cabeceras)
    assert r.status_code == 200
    assert r.json()["efectivo_esperado"] == "790.00"
    assert r.json()["ventas"][0]["es_efectivo"] is True


def test_corte_correcto(cliente, cabeceras, monkeypatch, caja_propia):
    sp = MagicMock(return_value={"efectivo_esperado": Decimal("578.00"), "diferencia": Decimal("-8.00")})
    monkeypatch.setattr(pos, "cerrar_caja", sp)
    cuerpo = {"id_caja": 1, "efectivo_contado": "570", "observaciones": "Faltan $8: cambio mal entregado\nticket 42"}
    r = cliente.post("/pos/cortes", json=cuerpo, headers=cabeceras)
    assert r.status_code == 201
    assert r.json() == {"id_caja": 1, "efectivo_esperado": "578.00", "efectivo_contado": "570.00", "diferencia": "-8.00"}
    assert sp.call_args.args[1:3] == (1, 2)
    assert auditoria.registrar.call_args.args[2] == "corte"


def test_corte_sin_observaciones_manda_null(cliente, cabeceras, monkeypatch, caja_propia):
    sp = MagicMock(return_value={"efectivo_esperado": Decimal("500.00"), "diferencia": Decimal("0.00")})
    monkeypatch.setattr(pos, "cerrar_caja", sp)
    r = cliente.post("/pos/cortes", json={"id_caja": 1, "efectivo_contado": "500.00", "observaciones": "   "},
                     headers=cabeceras)
    assert r.status_code == 201
    assert sp.call_args.args[4] is None


def test_corte_de_caja_ajena_403(cliente, cabeceras, monkeypatch):
    monkeypatch.setattr(pos, "caja_es_de_usuario", lambda c, caja, usuario: False)
    sp = MagicMock()
    monkeypatch.setattr(pos, "cerrar_caja", sp)
    r = cliente.post("/pos/cortes", json={"id_caja": 7, "efectivo_contado": "1"}, headers=cabeceras)
    assert r.status_code == 403
    sp.assert_not_called()


@pytest.mark.parametrize("texto", ["<script>alert(1)</script>", "faltó'; DROP TABLE cajas_pos; --", 'dijo "x"'])
def test_corte_rechaza_inyeccion_en_observaciones(cliente, cabeceras, monkeypatch, caja_propia, texto):
    sp = MagicMock()
    monkeypatch.setattr(pos, "cerrar_caja", sp)
    r = cliente.post("/pos/cortes", json={"id_caja": 1, "efectivo_contado": "1", "observaciones": texto},
                     headers=cabeceras)
    assert r.status_code == 422
    sp.assert_not_called()


def test_corte_rechazado_conserva_el_mensaje(cliente, cabeceras, monkeypatch, caja_propia):
    mensaje = "Escriba las observaciones: hay diferencia en el arqueo."
    monkeypatch.setattr(pos, "cerrar_caja", MagicMock(side_effect=_error_mysql(1644, mensaje)))
    r = cliente.post("/pos/cortes", json={"id_caja": 1, "efectivo_contado": "1"}, headers=cabeceras)
    assert r.status_code == 409
    assert r.json()["detail"] == mensaje
    assert auditoria.registrar.call_args.args[2] == "corte_rechazado"


def test_ultimo_corte(cliente, cabeceras, monkeypatch):
    monkeypatch.setattr(pos, "ultimo_corte", lambda c, t: None)
    assert cliente.get("/pos/cortes/ultimo", params={"terminal": "POS-01"}, headers=cabeceras).status_code == 404
    assert cliente.get("/pos/cortes/ultimo", params={"terminal": "<b>"}, headers=cabeceras).status_code == 422


# ---------------------------------------------------------------- ticket

def test_ticket_inexistente_404(cliente, cabeceras, monkeypatch):
    monkeypatch.setattr(pos, "ticket", lambda c, f: None)
    r = cliente.get("/pos/ventas/V00000099", headers=cabeceras)
    assert r.status_code == 404
    assert r.json()["detail"] == "No existe un ticket con ese número."


@pytest.mark.parametrize("folio", ["V1' OR '1'='1", "1", "V", "D00000001-1"])
def test_ticket_con_folio_invalido_422(cliente, cabeceras, monkeypatch, folio):
    busqueda = MagicMock()
    monkeypatch.setattr(pos, "ticket", busqueda)
    assert cliente.get(f"/pos/ventas/{folio}", headers=cabeceras).status_code == 422
    busqueda.assert_not_called()


# ---------------------------------------------------------------- autorización del Administrador

@pytest.fixture
def cuentas(monkeypatch):
    filas = {"admin": dict(ADMIN), "contador1": dict(CONTADOR)}
    monkeypatch.setattr(usuarios, "buscar_para_login", lambda c, u: filas.get(u))
    monkeypatch.setattr(usuarios, "registrar_intento_fallido", MagicMock())
    monkeypatch.setattr(usuarios, "limpiar_intentos", MagicMock())
    return filas


def _autorizar(cliente, cabeceras, usuario="admin", password=PASSWORD, folio="V00000001"):
    return cliente.post("/pos/devoluciones/autorizacion", headers=cabeceras,
                        json={"usuario": usuario, "password": password, "folio_venta": folio})


def test_autorizacion_correcta(cliente, cabeceras, cuentas):
    r = _autorizar(cliente, cabeceras)
    assert r.status_code == 200
    assert r.json()["autorizado_por"] == "Administrador de prueba"
    assert leer_autorizacion(r.json()["autorizacion"], 2, "V00000001") == (1, "admin")
    usuarios.limpiar_intentos.assert_called_once()
    assert auditoria.registrar.call_args.args[2] == "autorizacion"


def test_autorizacion_con_contrasena_incorrecta(cliente, cabeceras, cuentas):
    r = _autorizar(cliente, cabeceras, password="otra")
    # 403 y no 401: un 401 haría creer al cliente que la sesión del cajero expiró.
    assert r.status_code == 403
    assert r.json()["detail"] == "Contraseña del Administrador incorrecta."
    usuarios.registrar_intento_fallido.assert_called_once()
    assert auditoria.registrar.call_args.args[2] == "autorizacion_rechazada"


def test_autorizacion_de_usuario_inexistente(cliente, cabeceras, cuentas):
    r = _autorizar(cliente, cabeceras, usuario="nadie")
    assert r.status_code == 403
    assert r.json()["detail"] == "Contraseña del Administrador incorrecta."


def test_solo_un_administrador_autoriza(cliente, cabeceras, cuentas):
    r = _autorizar(cliente, cabeceras, usuario="contador1")
    assert r.status_code == 403
    assert r.json()["detail"] == "Solo un Administrador puede autorizar devoluciones."


def test_administrador_inactivo_no_autoriza(cliente, cabeceras, cuentas):
    cuentas["admin"]["activo"] = 0
    assert _autorizar(cliente, cabeceras).status_code == 403


def test_administrador_bloqueado_429(cliente, cabeceras, cuentas):
    cuentas["admin"]["bloqueado"] = 1
    assert _autorizar(cliente, cabeceras).status_code == 429


def test_la_autorizacion_no_sirve_como_sesion(cliente, cuentas):
    token = crear_autorizacion(1, "admin", 2, "V00000001")
    r = cliente.get("/pos/cajas/actual", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


# ---------------------------------------------------------------- devolución

DEVOLUCION = {
    "id_caja": 1,
    "folio_venta": "V00000001",
    "motivo": "Producto en mal estado",
    "reembolso": "efectivo",
    "renglones": [{"id_producto": 1, "cantidad": "0.500", "estado": "danado"}],
}


def _devolucion(**cambios):
    return {**DEVOLUCION, "autorizacion": crear_autorizacion(1, "admin", 2, "V00000001"), **cambios}


def test_devolucion_correcta_usa_el_administrador_de_la_autorizacion(cliente, cabeceras, monkeypatch, caja_propia):
    sp = MagicMock(return_value={"folio": "D00000001-1", "total": Decimal("22.50")})
    monkeypatch.setattr(pos, "registrar_devolucion", sp)
    r = cliente.post("/pos/devoluciones", json=_devolucion(), headers=cabeceras)
    assert r.status_code == 201
    assert r.json() == {"folio": "D00000001-1", "total": "22.50", "reembolso": "efectivo"}
    _, folio, caja, cajero, admin, motivo, reembolso, renglones = sp.call_args.args
    assert (folio, caja, cajero, admin, reembolso) == ("V00000001", 1, 2, 1, "efectivo")
    assert renglones == [{"id_producto": 1, "cantidad": 0.5, "estado": "danado"}]
    assert "autorizó admin" in auditoria.registrar.call_args.args[3]


@pytest.mark.parametrize(
    "autorizacion",
    [
        crear_autorizacion(1, "admin", 2, "V00000002"),  # otro ticket
        crear_autorizacion(1, "admin", 3, "V00000001"),  # otro cajero
        crear_token(1, 0),  # token de sesión del Administrador
        "no-es-un-token",
    ],
)
def test_devolucion_con_autorizacion_ajena_403(cliente, cabeceras, monkeypatch, caja_propia, autorizacion):
    sp = MagicMock()
    monkeypatch.setattr(pos, "registrar_devolucion", sp)
    r = cliente.post("/pos/devoluciones", json=_devolucion(autorizacion=autorizacion), headers=cabeceras)
    assert r.status_code == 403
    assert "autorización del Administrador" in r.json()["detail"]
    sp.assert_not_called()


def test_devolucion_con_autorizacion_vencida_403(cliente, cabeceras, monkeypatch, caja_propia):
    pasado = datetime.now(UTC) - timedelta(minutes=10)
    vencida = jwt.encode(
        {"sub": "1", "usr": "admin", "tipo": "autorizacion_devolucion", "para": 2, "folio": "V00000001",
         "iat": pasado, "exp": pasado + timedelta(minutes=5)},
        get_settings().jwt_secret.get_secret_value(), algorithm="HS256",
    )
    monkeypatch.setattr(pos, "registrar_devolucion", MagicMock())
    assert cliente.post("/pos/devoluciones", json=_devolucion(autorizacion=vencida), headers=cabeceras).status_code == 403


@pytest.mark.parametrize(
    "cambios",
    [
        {"reembolso": "vales"},
        {"renglones": []},
        {"renglones": [{"id_producto": 1, "cantidad": "1", "estado": "roto"}]},
        {"renglones": [{"id_producto": 1, "cantidad": "0", "estado": "bueno"}]},
        {"motivo": "<script>x</script>"},
        {"folio_venta": "V1 OR 1=1"},
        {"id_autoriza": 1},
    ],
)
def test_devolucion_invalida_422(cliente, cabeceras, monkeypatch, caja_propia, cambios):
    sp = MagicMock()
    monkeypatch.setattr(pos, "registrar_devolucion", sp)
    assert cliente.post("/pos/devoluciones", json=_devolucion(**cambios), headers=cabeceras).status_code == 422
    sp.assert_not_called()


def test_devolucion_en_caja_ajena_403(cliente, cabeceras, monkeypatch):
    monkeypatch.setattr(pos, "caja_es_de_usuario", lambda c, caja, usuario: False)
    sp = MagicMock()
    monkeypatch.setattr(pos, "registrar_devolucion", sp)
    assert cliente.post("/pos/devoluciones", json=_devolucion(), headers=cabeceras).status_code == 403
    sp.assert_not_called()


def test_devolucion_rechazada_por_la_base(cliente, cabeceras, monkeypatch, caja_propia):
    mensaje = "La cantidad a devolver de Manzana roja no es válida."
    monkeypatch.setattr(pos, "registrar_devolucion", MagicMock(side_effect=_error_mysql(1644, mensaje)))
    r = cliente.post("/pos/devoluciones", json=_devolucion(), headers=cabeceras)
    assert r.status_code == 409
    assert r.json()["detail"] == mensaje
    assert auditoria.registrar.call_args.args[2] == "devolucion_rechazada"
