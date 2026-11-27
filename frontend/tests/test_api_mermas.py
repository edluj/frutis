"""Mermas por lote (HU-17) contra un middleware simulado (rutas de middleware/README.md)."""
from datetime import date
from decimal import Decimal

import pytest

from app.datos import ErrorNegocio
from tests.test_api_caja_devoluciones import datos_con

HOY = date.today()
MERMA = {"fecha": HOY.isoformat(), "id_producto": 1, "producto": "Manzana roja", "unidad_venta": "kg",
         "lote": "L-00000002", "cantidad": "1.500", "motivo": "plaga", "costo": "48.00", "usuario": "compras1",
         "observaciones": None}
VIEJA = {**MERMA, "fecha": "2025-01-10", "cantidad": "9.000", "costo": "300.00"}


def test_lotes_del_producto():
    datos, _ = datos_con({"GET /inventario/productos/1/lotes": (200, [
        {"folio": "L-00000002", "queda": "10.000", "caducidad": HOY.isoformat(), "costo": "32.00"}])})
    assert datos.lotes_de_producto(1) == [
        {"lote": "L-00000002", "queda": Decimal("10.000"), "caducidad": HOY, "costo": Decimal("32.00")}]


def test_lista_de_mermas_traduce_el_motivo_y_suma_solo_el_mes_actual():
    datos, mw = datos_con({"GET /inventario/mermas": (200, [MERMA, VIEJA])})
    r = datos.lista_mermas("Plaga u hongo")
    assert mw.recibido["GET /inventario/mermas"] == {"motivo": "plaga"}
    assert r["filas"][0]["motivo"] == "Plaga u hongo" and r["filas"][0]["obs"] == ""
    assert r["kilos_mes"] == Decimal("1.500") and r["costo_mes"] == Decimal("48.00")
    datos.lista_mermas("Todos")
    assert mw.recibido["GET /inventario/mermas"] == {}


def test_registrar_merma_manda_el_motivo_de_la_base():
    datos, mw = datos_con({"POST /inventario/mermas": (201, {"costo": "40.16"})})
    costo = datos.registrar_merma(1, "L-00000002", Decimal("1.255"), "Devolución en mal estado", "")
    assert costo == Decimal("40.16")
    assert mw.recibido["POST /inventario/mermas"] == {"id_producto": 1, "folio_lote": "L-00000002", "cantidad": "1.255",
                                                      "motivo": "devolucion", "observaciones": None}


def test_merma_mayor_a_la_existencia():
    datos, _ = datos_con({"POST /inventario/mermas": (409, {"detail": "La cantidad supera la existencia del lote.",
                                                            "campo": "cantidad"})})
    with pytest.raises(ErrorNegocio) as exc:
        datos.registrar_merma(1, "L-00000002", Decimal("99"), "Golpe", "")
    assert exc.value.campo == "cantidad"
