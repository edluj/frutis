"""Cuentas por pagar, pagos y estado de cuenta del proveedor (HU-25) contra un middleware simulado."""
from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.datos import ErrorNegocio
from tests.test_api_caja_devoluciones import datos_con
from tests.test_api_compras import PROVEEDOR

HOY = date.today()
VENCIDA = {"lote": "L-00000002", "id_proveedor": 1, "proveedor": "Hortalizas del Valle",
           "vence": (HOY - timedelta(days=9)).isoformat(), "total": "1020.00", "saldo": "1020.00"}
PROXIMA = {**VENCIDA, "lote": "L-00000003", "vence": (HOY + timedelta(days=2)).isoformat(), "total": "516.50", "saldo": "216.50"}
PAGADA = {**VENCIDA, "lote": "L-00000001", "saldo": "0.00"}


def test_cuentas_por_pagar_estatus_y_totales():
    datos, mw = datos_con({"GET /compras/cuentas-por-pagar": (200, [VENCIDA, PROXIMA, PAGADA])})
    r = datos.cuentas_por_pagar(1)
    assert mw.recibido["GET /compras/cuentas-por-pagar"] == {"id_proveedor": "1"}
    assert [(f["lote"], f["estatus"]) for f in r["filas"]] == [("L-00000002", "Vencida · 9 días"), ("L-00000003", "Vence en 2 días")]
    assert (r["total"], r["vencido"], r["proximo"], r["lotes"]) == (Decimal("1236.50"), Decimal("1020.00"), Decimal("216.50"), 2)
    assert [f["lote"] for f in datos.cuentas_por_pagar(None, "Pagadas")["filas"]] == ["L-00000001"]


def test_pagar_lote():
    datos, mw = datos_con({"POST /compras/cuentas-por-pagar/L-00000003/pagos": (201, {"saldo": "216.50"})})
    assert datos.pagar_lote("L-00000003", Decimal("300.00"), "Cheque", "") == Decimal("216.50")
    assert mw.recibido["POST /compras/cuentas-por-pagar/L-00000003/pagos"] == {"monto": "300.00", "metodo": "Cheque",
                                                                                "referencia": None}


def test_pago_mayor_al_saldo_marca_el_monto():
    datos, _ = datos_con({"POST /compras/cuentas-por-pagar/L-00000003/pagos": (
        409, {"detail": "El pago no puede ser mayor al saldo.", "campo": "monto"})})
    with pytest.raises(ErrorNegocio) as exc:
        datos.pagar_lote("L-00000003", Decimal("999"), "Efectivo", "")
    assert exc.value.campo == "monto"


def test_estado_de_cuenta_con_saldo_inicial_y_del_periodo():
    antes, dentro = (HOY - timedelta(days=40)).isoformat(), (HOY - timedelta(days=5)).isoformat()
    datos, _ = datos_con({
        "GET /compras/proveedores": (200, [PROVEEDOR]),
        "GET /compras/cuentas-por-pagar": (200, [VENCIDA]),
        "GET /compras/proveedores/1/estado-de-cuenta": (200, [
            {"fecha": antes, "movimiento": "Compra lote L-1", "referencia": "Factura —", "cargo": "560.00", "abono": "0"},
            {"fecha": antes, "movimiento": "Pago lote L-1", "referencia": "Contado", "cargo": "0", "abono": "560.00"},
            {"fecha": dentro, "movimiento": "Compra lote L-2", "referencia": "Factura A-1", "cargo": "1020.00", "abono": "0"},
            {"fecha": dentro, "movimiento": "Pago lote L-2", "referencia": "SPEI 1", "cargo": "0", "abono": "300.00"}])})
    e = datos.estado_cuenta_proveedor(1, HOY - timedelta(days=30), HOY)
    assert e["inicial"] == Decimal("0") and [m["saldo"] for m in e["movimientos"]] == [Decimal("1020.00"), Decimal("720.00")]
    assert (e["compras"], e["pagos"], e["saldo"], e["vencido"]) == (Decimal("1020.00"), Decimal("300.00"), Decimal("720.00"),
                                                                     Decimal("1020.00"))
