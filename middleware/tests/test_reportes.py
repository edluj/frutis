"""Reportes (HU-28, HU-29) y resumen del día."""
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from app.repositories import compras, finanzas, inventario, pos, usuarios
from app.repositories import reportes as repo
from app.security.dependencias import UsuarioActual
from app.security.tokens import crear_token
from app.services import reportes as servicio
from tests.conftest import CAJERO

CONTADOR = {**CAJERO, "id_usuario": 4, "usuario": "contador1", "id_rol": 4, "rol": "Contador"}
P = lambda m: {"modulo": m, "puede_ver": 1, "puede_crear": 0, "puede_editar": 0, "puede_eliminar": 0}  # noqa: E731
PERMISOS = {2: [P("pos"), P("inventario")], 4: [P("finanzas"), P("reportes")]}
HOY = date.today()


@pytest.fixture
def contador(cliente, monkeypatch):
    monkeypatch.setattr(usuarios, "buscar_activo", lambda c, i: {2: CAJERO, 4: CONTADOR}.get(i))
    monkeypatch.setattr(usuarios, "permisos_del_rol", lambda c, r: PERMISOS.get(r, []))
    return {"Authorization": f"Bearer {crear_token(4, 0)}"}


def test_reportes_requieren_permiso_de_reportes(cliente, contador, cabeceras):
    assert cliente.get("/reportes/3", params={"desde": "2026-11-01", "hasta": "2026-11-30"}, headers=cabeceras).status_code == 403
    assert cliente.get("/reportes/cajeros", headers=cabeceras).status_code == 403


@pytest.mark.parametrize("params", [{"desde": "2026-11-30", "hasta": "2026-11-01"}, {"desde": "x", "hasta": "2026-11-01"}])
def test_rango_invalido(cliente, contador, params):
    assert cliente.get("/reportes/3", params=params, headers=contador).status_code in (409, 422)


def test_numero_de_reporte_fuera_de_rango(cliente, contador):
    assert cliente.get("/reportes/13", params={"desde": "2026-11-01", "hasta": "2026-11-30"}, headers=contador).status_code == 422


def test_top_productos_con_porcentaje_y_barras(cliente, contador, monkeypatch):
    monkeypatch.setattr(repo, "ventas_por_producto", lambda c, d, h: [
        {"nombre": "Plátano", "unidad_venta": "kg", "cantidad": Decimal("7.000"), "importe": Decimal("150.00")},
        {"nombre": "Piña", "unidad_venta": "pieza", "cantidad": Decimal("2.000"), "importe": Decimal("50.00")}])
    r = cliente.get("/reportes/3", params={"desde": "2026-11-01", "hasta": "2026-11-30"}, headers=contador).json()
    assert r["filas"] == [["Plátano", "7.0 kg", "150.00", "75.0"], ["Piña", "2 pza", "50.00", "25.0"]]
    assert r["total"] == ["Total", "", "200.00", "100"]
    assert [(b["nombre"], b["fraccion"]) for b in r["barras"]] == [("Plátano", 1.0), ("Piña", 1 / 3)]
    assert r["columnas"][1] == {"nombre": "Cantidad", "alineacion": "der", "tipo": "texto"}


def test_horas_pico_no_pierde_ventas_fuera_de_horario(monkeypatch):
    monkeypatch.setattr(repo, "tickets_por_hora", lambda c, d, h: [{"hora": 10, "tickets": 3}, {"hora": 22, "tickets": 1}])
    r = servicio.reporte(MagicMock(), 9, HOY, HOY, None)
    assert r.filas[-1][:2] == ["Otras horas", 1] and r.total[1] == 4


def test_utilidad_descuenta_mermas(monkeypatch):
    d = HOY.replace(day=1)
    monkeypatch.setattr(finanzas, "eventos", lambda c, a, b: [
        {"fecha": d, "clase": "venta_cobrada", "concepto": "", "monto": Decimal("1000")},
        {"fecha": d, "clase": "compra_credito", "concepto": "", "monto": Decimal("600")},
        {"fecha": d, "clase": "gasto", "concepto": "Luz", "monto": Decimal("100")}])
    monkeypatch.setattr(repo, "costo_mermas", lambda c, a, b: Decimal("40"))
    r = servicio.reporte(MagicMock(), 11, d, HOY, None)
    assert r.total == ["Utilidad neta real", Decimal("260")]


def _resumen(monkeypatch, permisos):
    monkeypatch.setattr(usuarios, "permisos_del_rol", lambda c, r: [P(m) for m in permisos])
    monkeypatch.setattr(repo, "ventas_de_hoy", lambda c, u: {"tickets": 2, "importe": Decimal("90.00")})
    monkeypatch.setattr(pos, "caja_abierta_de", lambda c, u: {"terminal": "POS-01", "fecha_apertura": datetime(2026, 11, 27, 8, 5)})
    monkeypatch.setattr(inventario, "lotes_por_caducar", lambda c, d, p, pr: [])
    monkeypatch.setattr(inventario, "existencias", lambda c: [])
    monkeypatch.setattr(compras, "cuentas_por_pagar", lambda c, p: [])
    monkeypatch.setattr(finanzas, "cuentas_por_cobrar", lambda c, i: [
        {"cliente": "Fonda", "saldo": Decimal("110.00"), "vence": date(2020, 1, 1)}])
    return servicio.resumen(MagicMock(), UsuarioActual(2, "cajero1", "Cajero de prueba", 2, "Cajero"))


def test_el_cajero_no_ve_lo_que_deben_los_clientes(monkeypatch):
    r = _resumen(monkeypatch, ["pos", "inventario"])
    assert r.por_cobrar is None and r.por_cobrar_detalle == "Sin acceso a finanzas"
    assert r.caja_detalle == "POS-01 · desde las 08:05 · Cajero de prueba" and r.caducar == 0
    assert not any("Cobro vencido" in a.texto for a in r.alertas)


def test_con_finanzas_ve_cobros_vencidos(monkeypatch):
    r = _resumen(monkeypatch, ["finanzas", "reportes"])
    assert r.por_cobrar == Decimal("110.00") and r.caducar is None
    assert r.alertas[0].texto.startswith("Cobro vencido: Fonda debe $110.00")


def test_resumen_solo_requiere_sesion(cliente, contador, cabeceras, monkeypatch):
    listo = _resumen(monkeypatch, ["pos"])
    monkeypatch.setattr(servicio, "resumen", lambda c, u: listo)
    assert cliente.get("/reportes/resumen-del-dia", headers=cabeceras).status_code == 200
    assert cliente.get("/reportes/resumen-del-dia").status_code == 401
