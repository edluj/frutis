"""Cobros (HU-38b), gastos (HU-26), dashboard (HU-27) y flujo (HU-37) contra un middleware simulado."""
from datetime import date, timedelta
from decimal import Decimal

import pytest

from app import formato
from app.datos import ErrorNegocio
from tests.test_api_caja_devoluciones import datos_con
from tests.test_api_credito import CLIENTE

HOY = date.today()
FLUJO = {"inicial": "-560.00", "ventas": "269.77", "cobros": "68.00", "pagos_proveedores": "608.00", "gastos": "0.00",
         "credito": "178.00", "semanas": [{"semana": "1 al 7 nov", "entradas": "302.00", "salidas": "0.00"}]}
CXC = [{"ticket": "V00000010", "id_cliente": 1, "cliente": "Fonda Doña Lupe", "venta": (HOY - timedelta(days=20)).isoformat(),
        "vence": (HOY - timedelta(days=5)).isoformat(), "total": "110.00", "saldo": "110.00"},
       {"ticket": "V00000005", "id_cliente": 1, "cliente": "Fonda Doña Lupe", "venta": HOY.isoformat(),
        "vence": (HOY + timedelta(days=15)).isoformat(), "total": "68.00", "saldo": "18.00"}]


def test_periodos_del_mes_actual_hacia_atras():
    assert formato.meses_recientes(3, date(2026, 1, 15)) == ["Enero 2026", "Diciembre 2025", "Noviembre 2025"]
    assert formato.periodo_a_mes("Noviembre 2026") == (2026, 11)


def test_cuentas_por_cobrar_con_estatus_y_cobrado_del_mes():
    datos, mw = datos_con({"GET /finanzas/cuentas-por-cobrar": (200, CXC), "GET /finanzas/flujo": (200, FLUJO)})
    r = datos.cuentas_por_cobrar()
    assert [(f["ticket"], f["estatus"]) for f in r["filas"]] == [("V00000010", "Vencida · 5 días"), ("V00000005", "Pago parcial")]
    assert (r["total"], r["vencido"], r["cobrado_mes"]) == (Decimal("128.00"), Decimal("110.00"), Decimal("68.00"))
    assert mw.recibido["GET /finanzas/flujo"] == {"anio": str(HOY.year), "mes": str(HOY.month)}


def test_cobro_en_efectivo_manda_el_id_de_la_caja_elegida():
    datos, mw = datos_con({"GET /finanzas/cajas-abiertas": (200, [{"id_caja": 7, "terminal": "POS-01"}]),
                           "POST /finanzas/cuentas-por-cobrar/V00000010/cobros": (201, {"saldo": "60.00"})})
    assert datos.cajas_abiertas() == ["POS-01 · abierta", "Sin caja (no entra al corte)"]
    assert datos.registrar_cobro("V00000010", Decimal("50.00"), "Efectivo", "POS-01 · abierta") == Decimal("60.00")
    assert mw.recibido["POST /finanzas/cuentas-por-cobrar/V00000010/cobros"] == {"monto": "50.00", "metodo": "Efectivo",
                                                                                  "id_caja": 7}
    datos.registrar_cobro("V00000010", Decimal("10.00"), "Efectivo", "Sin caja (no entra al corte)")
    assert mw.recibido["POST /finanzas/cuentas-por-cobrar/V00000010/cobros"]["id_caja"] is None


def test_cobro_mayor_al_saldo():
    datos, _ = datos_con({"POST /finanzas/cuentas-por-cobrar/V00000010/cobros": (
        409, {"detail": "El cobro no puede ser mayor al saldo.", "campo": "monto"})})
    with pytest.raises(ErrorNegocio) as exc:
        datos.registrar_cobro("V00000010", Decimal("999"), "Transferencia", None)
    assert exc.value.campo == "monto"


def test_estado_de_cuenta_del_cliente():
    datos, _ = datos_con({
        "GET /finanzas/clientes-credito": (200, [CLIENTE]),
        "GET /finanzas/cuentas-por-cobrar": (200, CXC[1:]), "GET /finanzas/flujo": (200, FLUJO),
        "GET /finanzas/clientes-credito/1/estado-de-cuenta": (200, [
            {"fecha": HOY.isoformat(), "movimiento": "Compra a crédito", "referencia": "Ticket V5", "cargo": "68.00", "abono": "0"},
            {"fecha": HOY.isoformat(), "movimiento": "Cobro en efectivo · POS-01", "referencia": "Ticket V5", "cargo": "0",
             "abono": "50.00"}])})
    e = datos.estado_cuenta_cliente(1, HOY - timedelta(days=30), HOY)
    assert [m["saldo"] for m in e["movimientos"]] == [Decimal("68.00"), Decimal("18.00")]
    assert e["disponible"] == Decimal("750.00") and e["vence"] == HOY + timedelta(days=15)


def test_gastos():
    datos, mw = datos_con({
        "GET /finanzas/gastos": (200, [{"fecha": "2026-11-20", "concepto": "Luz", "detalle": "Bimestre", "metodo": "Transferencia",
                                        "monto": "1250.00", "comprobante": False, "usuario": "contador1"}]),
        "POST /finanzas/gastos": (201, {"estado": "registrado"})})
    r = datos.lista_gastos("Luz", date(2026, 11, 1), None)
    assert mw.recibido["GET /finanzas/gastos"] == {"concepto": "Luz", "desde": "2026-11-01"}
    assert r["total"] == Decimal("1250.00") and r["filas"][0]["detalle"] == "Bimestre"
    datos.registrar_gasto(dict(fecha=date(2026, 11, 20), concepto="Renta", detalle="", metodo="Efectivo",
                               monto=Decimal("8000"), comprobante=True))
    assert mw.recibido["POST /finanzas/gastos"] == {"fecha": "2026-11-20", "concepto": "Renta", "detalle": None,
                                                    "metodo": "Efectivo", "monto": "8000"}


def test_dashboard_y_flujo_piden_el_mes_del_periodo():
    dashboard = {"ingresos": "447.77", "tickets": 5, "compras": "1628.00", "gastos": "0.00", "egresos": "1628.00",
                 "utilidad": "-1180.23", "margen": "-263.6", "margen_anterior": "0.0",
                 "semanas": [{"semana": "Sem 1", "ingresos": "302.00", "egresos": "1020.00"}],
                 "conceptos": [{"concepto": "Compras a proveedores", "importe": "1628.00", "pct": "100.0"}]}
    datos, mw = datos_con({"GET /finanzas/dashboard": (200, dashboard), "GET /finanzas/flujo": (200, FLUJO)})
    d = datos.dashboard("Noviembre 2026")
    assert mw.recibido["GET /finanzas/dashboard"] == {"anio": "2026", "mes": "11"}
    assert d["utilidad"] == Decimal("-1180.23") and d["semanas"] == [("Sem 1", 302.0, 1020.0)]
    f = datos.flujo("Octubre 2026")
    assert mw.recibido["GET /finanzas/flujo"] == {"anio": "2026", "mes": "10"}
    assert f["inicial"] == Decimal("-560.00") and f["semanas"] == [("1 al 7 nov", Decimal("302.00"), Decimal("0.00"))]
