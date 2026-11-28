"""Finanzas: clientes de crédito (HU-39), lista del POS (HU-38a), cobros (HU-38b), gastos (HU-26), dashboard (HU-27) y flujo (HU-37)."""
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import MagicMock

import pymysql
import pytest
from sqlalchemy.exc import OperationalError

from app.repositories import auditoria, usuarios
from app.repositories import finanzas as repo
from app.security.tokens import crear_token
from app.services import finanzas as servicio
from tests.conftest import CAJERO

CONTADOR = {**CAJERO, "id_usuario": 4, "usuario": "contador1", "id_rol": 4, "rol": "Contador"}
PERMISOS = {
    2: [{"modulo": "pos", "puede_ver": 1, "puede_crear": 1, "puede_editar": 0, "puede_eliminar": 0}],
    4: [{"modulo": "finanzas", "puede_ver": 1, "puede_crear": 1, "puede_editar": 1, "puede_eliminar": 1},
        {"modulo": "pos", "puede_ver": 1, "puede_crear": 0, "puede_editar": 0, "puede_eliminar": 0}],
}
CLIENTE = {"id_cliente_credito": 1, "nombre": "Fonda Doña Lupe", "telefono": "5555550202", "correo": None,
           "limite_credito": Decimal("1000.00"), "dias_credito": 15, "activo": 1, "rfc_fiscal": None,
           "debe": Decimal("68.00"), "vencido": 0}
ALTA = {"nombre": "Cocina Económica Rosy", "telefono": "55 3388 1200", "limite_credito": "3000.00",
        "dias_credito": 15, "correo": "", "rfc_fiscal": ""}


@pytest.fixture
def contador(cliente, monkeypatch):
    monkeypatch.setattr(usuarios, "buscar_activo", lambda c, i: {2: CAJERO, 4: CONTADOR}.get(i))
    monkeypatch.setattr(usuarios, "permisos_del_rol", lambda c, r: PERMISOS.get(r, []))
    monkeypatch.setattr(repo, "cliente", lambda c, i, bloquear=False: CLIENTE if i == 1 else None)
    return {"Authorization": f"Bearer {crear_token(4, 0)}"}


def test_alta_de_cliente_de_credito(cliente, contador, monkeypatch):
    insertar = MagicMock(return_value=1)
    monkeypatch.setattr(repo, "insertar_cliente", insertar)
    r = cliente.post("/finanzas/clientes-credito", json=ALTA, headers=contador)
    assert r.status_code == 201
    valores = insertar.call_args.args[1]
    assert valores["limite_credito"] == Decimal("3000.00") and valores["correo"] is None and valores["id_cliente"] is None
    assert auditoria.registrar.call_args.args[1:3] == ("finanzas", "cliente_credito_alta")


@pytest.mark.parametrize("cambio", [{"limite_credito": "0"}, {"dias_credito": 0}, {"telefono": "x"},
                                    {"nombre": "<script>"}, {"rfc_fiscal": "MAL"}])
def test_cliente_invalido_422(cliente, contador, cambio):
    assert cliente.post("/finanzas/clientes-credito", json={**ALTA, **cambio}, headers=contador).status_code == 422


def test_rfc_fiscal_inexistente_marca_el_campo(cliente, contador, monkeypatch):
    monkeypatch.setattr(repo, "id_fiscal", lambda c, rfc: None)
    r = cliente.post("/finanzas/clientes-credito", json={**ALTA, "rfc_fiscal": "LUGO750312HM4"}, headers=contador)
    assert r.status_code == 409 and r.json()["campo"] == "fiscal"


def test_suspender_cliente(cliente, contador, monkeypatch):
    actualizar = MagicMock()
    monkeypatch.setattr(repo, "actualizar_cliente", actualizar)
    r = cliente.put("/finanzas/clientes-credito/1", json={**ALTA, "activo": False}, headers=contador)
    assert r.status_code == 200 and actualizar.call_args.args[2]["activo"] is False
    assert "Suspendido" in auditoria.registrar.call_args.args[3]


def test_editar_cliente_inexistente_404(cliente, contador):
    assert cliente.put("/finanzas/clientes-credito/9", json=ALTA, headers=contador).status_code == 404


def test_cajero_no_administra_clientes_pero_los_ve_en_el_pos(cliente, contador, cabeceras, monkeypatch):
    listar = MagicMock(return_value=[CLIENTE])
    monkeypatch.setattr(repo, "listar_clientes", listar)
    assert cliente.get("/finanzas/clientes-credito", headers=cabeceras).status_code == 403
    r = cliente.get("/pos/clientes-credito", headers=cabeceras)
    assert r.status_code == 200
    assert listar.call_args.args[1:] == (None, True)
    [c] = r.json()
    assert c["disponible"] == "932.00" and c["vence"] == (date.today() + timedelta(days=15)).isoformat()


def test_contador_sin_permiso_de_cobro_no_usa_la_lista_del_pos(cliente, contador):
    assert cliente.get("/pos/clientes-credito", headers=contador).status_code == 403


def test_disponible_nunca_es_negativo(cliente, contador, cabeceras, monkeypatch):
    excedido = {**CLIENTE, "debe": Decimal("1200.00"), "vencido": 1}
    monkeypatch.setattr(repo, "listar_clientes", lambda c, b, a: [excedido])
    [c] = cliente.get("/pos/clientes-credito", headers=cabeceras).json()
    assert c["disponible"] == "0.00" and c["vencido"] is True


# ---------------------------------------------------------------- cobros, gastos, dashboard y flujo

COBRO = {"monto": "50.00", "metodo": "Efectivo", "id_caja": 1}


@pytest.fixture
def cobro(monkeypatch):
    monkeypatch.setattr(repo, "id_cxc", lambda c, t: 3 if t == "V00000010" else None)
    monkeypatch.setattr(repo, "id_metodo", lambda c, n: {"Efectivo": 1, "Transferencia": 4, "Tarjeta de débito": 2}.get(n))
    sp = MagicMock(return_value=Decimal("60.00"))
    monkeypatch.setattr(repo, "registrar_cobro", sp)
    return sp


def test_cobro_en_efectivo_entra_a_la_caja(cliente, contador, cobro):
    r = cliente.post("/finanzas/cuentas-por-cobrar/V00000010/cobros", json=COBRO, headers=contador)
    assert r.status_code == 201 and r.json() == {"saldo": "60.00"}
    assert cobro.call_args.args[1:] == (3, Decimal("50.00"), 1, 1, 4)


def test_cobro_con_tarjeta_no_usa_caja_y_es_debito(cliente, contador, cobro):
    cliente.post("/finanzas/cuentas-por-cobrar/V00000010/cobros", json={**COBRO, "metodo": "Tarjeta"}, headers=contador)
    assert cobro.call_args.args[3:5] == (2, None)


def test_error_del_procedimiento_marca_el_monto(cliente, contador, cobro, conn):
    cobro.side_effect = OperationalError("CALL", {}, pymysql.err.OperationalError(1644, "El cobro no puede ser mayor al saldo."))
    r = cliente.post("/finanzas/cuentas-por-cobrar/V00000010/cobros", json=COBRO, headers=contador)
    assert r.status_code == 409 and r.json() == {"detail": "El cobro no puede ser mayor al saldo.", "campo": "monto"}
    conn.rollback.assert_called()


def test_cobro_de_ticket_sin_credito_404(cliente, contador, cobro):
    assert cliente.post("/finanzas/cuentas-por-cobrar/V00000001/cobros", json=COBRO, headers=contador).status_code == 404


def test_cajero_no_registra_cobros_ni_gastos(cliente, contador, cabeceras, cobro):
    assert cliente.post("/finanzas/cuentas-por-cobrar/V00000010/cobros", json=COBRO, headers=cabeceras).status_code == 403
    assert cliente.get("/finanzas/dashboard", params={"anio": 2026, "mes": 11}, headers=cabeceras).status_code == 403


GASTO = {"fecha": "2026-11-20", "concepto": "Luz", "detalle": "Bimestre oct-nov", "metodo": "Transferencia", "monto": "1250.00"}


def test_gasto_guarda_el_detalle_en_el_concepto(cliente, contador, monkeypatch):
    monkeypatch.setattr(repo, "id_metodo", lambda c, n: 4)
    registrar = MagicMock()
    monkeypatch.setattr(repo, "registrar_gasto", registrar)
    assert cliente.post("/finanzas/gastos", json=GASTO, headers=contador).status_code == 201
    assert registrar.call_args.args[1:] == (date(2026, 11, 20), "Luz · Bimestre oct-nov", Decimal("1250.00"), 4, 4)


@pytest.mark.parametrize("cambio", [{"concepto": "Viajes"}, {"monto": "0"}, {"metodo": "Cheque"}, {"detalle": "<b>"}])
def test_gasto_invalido_422(cliente, contador, cambio):
    assert cliente.post("/finanzas/gastos", json={**GASTO, **cambio}, headers=contador).status_code == 422


def test_gasto_con_fecha_futura(cliente, contador, monkeypatch):
    monkeypatch.setattr(repo, "id_metodo", lambda c, n: 4)
    futura = {**GASTO, "fecha": "2100-01-01"}
    assert cliente.post("/finanzas/gastos", json=futura, headers=contador).json()["campo"] == "fecha"


def _ev(dia, clase, monto, concepto=""):
    return {"fecha": date(2026, 11, dia), "clase": clase, "concepto": concepto, "monto": Decimal(monto)}


EVENTOS = [_ev(2, "venta_cobrada", "1000"), _ev(3, "venta_credito", "500"), _ev(4, "devolucion_pagada", "100"),
           _ev(9, "cobro", "200"), _ev(10, "compra_credito", "600"), _ev(16, "compra_contado", "150"),
           _ev(25, "gasto", "80", "Luz"), _ev(25, "gasto", "20", "Agua"), _ev(26, "gasto", "300", "Renta"),
           _ev(27, "pago_proveedor", "250")]


def test_dashboard_devengado(monkeypatch):
    monkeypatch.setattr(repo, "eventos", lambda c, d, h: EVENTOS if d == date(2026, 11, 1) else [])
    d = servicio.dashboard(MagicMock(), 2026, 11)
    assert (d.ingresos, d.compras, d.gastos, d.egresos, d.utilidad) == (Decimal("1400"), Decimal("750"), Decimal("400"),
                                                                       Decimal("1150"), Decimal("250"))
    assert d.tickets == 2 and d.margen == Decimal("17.9")
    assert [(c.concepto, c.importe) for c in d.conceptos] == [("Compras a proveedores", Decimal("750")),
                                                             ("Renta", Decimal("300")), ("Luz, agua y gas", Decimal("100"))]
    assert [(s.ingresos, s.egresos) for s in d.semanas] == [(Decimal("1400"), Decimal("0")), (Decimal("0"), Decimal("600")),
                                                           (Decimal("0"), Decimal("150")), (Decimal("0"), Decimal("400"))]


def test_flujo_en_efectivo(monkeypatch):
    previos = [_ev(1, "venta_cobrada", "50")]
    monkeypatch.setattr(repo, "eventos", lambda c, d, h: previos if d is None else EVENTOS)
    f = servicio.flujo(MagicMock(), 2026, 11)
    assert (f.inicial, f.ventas, f.cobros, f.pagos_proveedores, f.gastos, f.credito) == (
        Decimal("50"), Decimal("900"), Decimal("200"), Decimal("400"), Decimal("400"), Decimal("500"))
    assert [s.semana for s in f.semanas] == ["1 al 7 nov", "8 al 14 nov", "15 al 21 nov", "22 al 30 nov"]
    assert [(s.entradas, s.salidas) for s in f.semanas] == [(Decimal("900"), Decimal("0")), (Decimal("200"), Decimal("0")),
                                                           (Decimal("0"), Decimal("150")), (Decimal("0"), Decimal("650"))]


def test_periodo_invalido_422(cliente, contador):
    assert cliente.get("/finanzas/flujo", params={"anio": 2026, "mes": 13}, headers=contador).status_code == 422
