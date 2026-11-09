from decimal import Decimal
from unittest.mock import MagicMock

import pymysql
import pytest
from sqlalchemy.exc import OperationalError

from app.repositories import auditoria, pos

VENTA = {
    "id_caja": 1,
    "id_metodo": 1,
    "monto_recibido": "200.00",
    "carrito": [{"id_producto": 1, "cantidad": "1.255"}],
}
RESULTADO = {"id_venta": 9, "folio": "V00000009", "total": Decimal("56.48"), "cambio": Decimal("143.52")}


@pytest.fixture
def caja_propia(monkeypatch):
    monkeypatch.setattr(pos, "caja_es_de_usuario", lambda c, caja, usuario: True)


def _error_mysql(codigo, mensaje):
    return OperationalError("CALL", {}, pymysql.err.OperationalError(codigo, mensaje))


def test_venta_correcta_usa_el_cajero_del_token(cliente, cabeceras, monkeypatch, caja_propia):
    sp = MagicMock(return_value=RESULTADO)
    monkeypatch.setattr(pos, "registrar_venta", sp)
    r = cliente.post("/pos/ventas", json=VENTA, headers=cabeceras)
    assert r.status_code == 201
    assert r.json()["folio"] == "V00000009"
    assert r.json()["cambio"] == "143.52"
    argumentos = sp.call_args.args
    assert argumentos[2] == 2
    assert argumentos[6] == [{"id_producto": 1, "cantidad": 1.255}]


def test_rechaza_id_usuario_en_el_cuerpo(cliente, cabeceras, caja_propia):
    r = cliente.post("/pos/ventas", json={**VENTA, "id_usuario": 1}, headers=cabeceras)
    assert r.status_code == 422


@pytest.mark.parametrize(
    "carrito",
    [
        [],
        [{"id_producto": 1, "cantidad": "0"}],
        [{"id_producto": 1, "cantidad": "-1"}],
        [{"id_producto": 1, "cantidad": "1.2345"}],
        [{"id_producto": "1 OR 1=1", "cantidad": "1"}],
    ],
)
def test_carrito_invalido_422(cliente, cabeceras, caja_propia, carrito):
    r = cliente.post("/pos/ventas", json={**VENTA, "carrito": carrito}, headers=cabeceras)
    assert r.status_code == 422


def test_caja_ajena_403(cliente, cabeceras, monkeypatch):
    monkeypatch.setattr(pos, "caja_es_de_usuario", lambda c, caja, usuario: False)
    sp = MagicMock()
    monkeypatch.setattr(pos, "registrar_venta", sp)
    assert cliente.post("/pos/ventas", json=VENTA, headers=cabeceras).status_code == 403
    sp.assert_not_called()


def test_error_de_negocio_conserva_el_mensaje(cliente, cabeceras, monkeypatch, caja_propia, conn):
    mensaje = "Producto sin existencia suficiente: Manzana roja"
    monkeypatch.setattr(pos, "registrar_venta", MagicMock(side_effect=_error_mysql(1644, mensaje)))
    r = cliente.post("/pos/ventas", json=VENTA, headers=cabeceras)
    assert r.status_code == 409
    assert r.json()["detail"] == mensaje
    conn.rollback.assert_called()
    assert auditoria.registrar.call_args.args[2] == "venta_rechazada"


def test_error_interno_no_filtra_detalles(cliente, cabeceras, monkeypatch, caja_propia):
    monkeypatch.setattr(pos, "registrar_venta", MagicMock(side_effect=_error_mysql(1205, "lock wait tabla X")))
    r = cliente.post("/pos/ventas", json=VENTA, headers=cabeceras)
    assert r.status_code == 500
    assert r.json()["detail"] == "No se pudo registrar la venta, intente de nuevo."


def test_falla_de_bitacora_no_anula_la_venta(cliente, cabeceras, monkeypatch, caja_propia):
    monkeypatch.setattr(pos, "registrar_venta", MagicMock(return_value=RESULTADO))
    monkeypatch.setattr(auditoria, "registrar", MagicMock(side_effect=_error_mysql(2013, "se fue")))
    assert cliente.post("/pos/ventas", json=VENTA, headers=cabeceras).status_code == 201


def test_sin_caja_abierta_404(cliente, cabeceras, monkeypatch):
    monkeypatch.setattr(pos, "caja_abierta_de", lambda c, u: None)
    assert cliente.get("/pos/cajas/actual", headers=cabeceras).status_code == 404
