"""Proveedores (HU-23) y lotes de compra (HU-11) contra un middleware simulado (rutas de middleware/README.md)."""
from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.datos import ErrorNegocio
from tests.test_api_caja_devoluciones import datos_con

HOY = date.today()
PROVEEDOR = {"id_proveedor": 1, "razon_social": "Hortalizas del Valle", "rfc": "HVA010203AB1", "telefono": "5512345678",
             "correo": None, "direccion": None, "dias_credito": 15, "activo": True, "saldo": "1020.00"}
RESUMEN = {"folio": "L-00000002", "id_proveedor": 1, "proveedor": "Hortalizas del Valle", "entrada": "2026-11-20",
           "productos": 2, "total": "1020.00", "kilos": "18.000", "dias_credito": 15, "pago": "Vencido",
           "saldo": "1020.00", "caducidad": "2026-11-27"}
CONTADO = {**RESUMEN, "folio": "L-00000001", "total": "560.00", "kilos": "22.000", "dias_credito": 0,
           "pago": "Pagado", "saldo": "0.00"}
DETALLE = {
    "folio": "L-00000002", "proveedor": "Hortalizas del Valle", "entrada": HOY.isoformat(), "factura": None,
    "total": "1020.00", "dias_credito": 15, "vence": (HOY + timedelta(days=2)).isoformat(), "pagado": "0.00",
    "saldo": "1020.00", "pago": "Pendiente",
    "productos": [{"id_producto": 1, "nombre": "Manzana roja", "unidad_venta": "kg", "recibido": "10.000",
                   "costo": "32.00", "vendido": "6.000", "merma": "1.000", "existencia": "3.000",
                   "caducidad": HOY.isoformat(), "dias": 0}],
    "mermas": [{"fecha": HOY.isoformat(), "producto": "Manzana roja", "cantidad": "1.000", "motivo": "golpe",
                "costo": "32.00"}],
}


def test_proveedores_con_la_forma_de_la_pantalla():
    datos, mw = datos_con({"GET /compras/proveedores": (200, [PROVEEDOR])})
    [p] = datos.lista_proveedores("valle", "Inactivos")
    assert mw.recibido["GET /compras/proveedores"] == {"busqueda": "valle", "estatus": "inactivos"}
    assert p["id"] == 1 and p["correo"] == "" and p["saldo"] == Decimal("1020.00")


def test_baja_de_proveedor_con_saldo_marca_estatus():
    datos, mw = datos_con({"PUT /compras/proveedores/1": (409, {"detail": "No se puede dar de baja: tiene saldo por pagar.",
                                                                "campo": "estatus"})})
    with pytest.raises(ErrorNegocio) as exc:
        datos.guardar_proveedor(dict(id=1, razon_social="X", rfc="HVA010203AB1", telefono="5512345678", correo="",
                                     dias_credito=15, direccion="", activo=False))
    assert exc.value.campo == "estatus"
    assert mw.recibido["PUT /compras/proveedores/1"]["correo"] is None


def test_registrar_lote_manda_fechas_y_cantidades_como_texto():
    datos, mw = datos_con({"POST /compras/lotes": (201, {"folio": "L-00000009", "total": "836.50"})})
    folio = datos.registrar_lote(dict(id_proveedor=1, factura="", entrada=HOY, dias=None, renglones=[
        dict(id_producto=1, nombre="Manzana", unidad="kg", cantidad=Decimal("20.500"), costo=Decimal("30.00"),
             caducidad=HOY + timedelta(days=7))]))
    assert folio == "L-00000009"
    cuerpo = mw.recibido["POST /compras/lotes"]
    assert cuerpo["dias_credito"] == 0 and cuerpo["factura"] is None and cuerpo["entrada"] == HOY.isoformat()
    assert cuerpo["renglones"][0]["cantidad"] == "20.500"


def test_lista_de_lotes_calcula_los_indicadores():
    datos, mw = datos_con({"GET /compras/lotes": (200, [RESUMEN, CONTADO])})
    r = datos.lista_lotes(1, date(2026, 11, 1), None, "Todos")
    assert mw.recibido["GET /compras/lotes"] == {"id_proveedor": "1", "desde": "2026-11-01", "pago": "Todos"}
    assert [f["condicion"] for f in r["filas"]] == ["Crédito 15 días", "Contado"]
    assert r["filas"][0]["tono"] == "rojo"
    assert r["total"] == Decimal("1580.00") and r["pendientes"] == 1 and r["por_pagar"] == Decimal("1020.00")
    assert r["costo_promedio"] == Decimal("1580.00") / Decimal("40.000")


def test_detalle_de_lote():
    datos, _ = datos_con({"GET /compras/lotes/L-00000002": (200, DETALLE)})
    d = datos.detalle_lote("L-00000002")
    assert (d["estatus"], d["tono"]) == ("Vence en 2 días", "naranja")
    assert d["recibido"] == Decimal("10.000") and d["vendido"] == Decimal("6.000") and d["costo_merma"] == Decimal("32.00")
    assert d["mermas"][0]["motivo"] == "Golpe" and d["factura"] == ""


def test_siguiente_folio():
    datos, _ = datos_con({"GET /compras/lotes/siguiente-folio": (200, {"folio": "L-00000003"})})
    assert datos.siguiente_folio_lote() == "L-00000003"
