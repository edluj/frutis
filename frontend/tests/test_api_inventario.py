"""Existencias, caducidades y movimientos (HU-24) y ajuste de precios (HU-31) contra un middleware simulado."""
from datetime import date, timedelta
from decimal import Decimal

from tests.test_api_caja_devoluciones import datos_con
from tests.test_api_catalogo import PRODUCTO

HOY = date.today()
MANZANA = {**PRODUCTO, "id_producto": 1, "nombre": "Manzana roja", "unidad_venta": "kg", "precio_venta": "45.00",
           "costo_actual": "32.00", "existencia": "23.250", "stock_minimo": "10.000", "estado": "Normal"}
LOTE = {"caducidad": (HOY + timedelta(days=1)).isoformat(), "dias": 1, "id_producto": 1, "producto": "Manzana roja",
        "unidad_venta": "kg", "lote": "L-00000002", "proveedor": "Distribuidora", "recibido": "10.000",
        "queda": "7.750", "costo": "248.00"}


def test_existencias_calcula_alcance_bajos_y_por_caducar():
    datos, mw = datos_con({
        "GET /inventario/existencias": (200, [
            {"id_producto": 1, "id_categoria": 1, "nombre": "Manzana roja", "unidad_venta": "kg", "existencia": "9.000",
             "stock_minimo": "10.000", "venta_diaria": "1.500", "lotes": 2, "valor": "280.00"},
            {"id_producto": 4, "id_categoria": 1, "nombre": "Piña", "unidad_venta": "pieza", "existencia": "0.000",
             "stock_minimo": "4.000", "venta_diaria": "0.000", "lotes": 0, "valor": "0.00"}]),
        "GET /inventario/lotes": (200, [LOTE])})
    r = datos.existencias("", None, "Bajo el mínimo")
    assert mw.recibido["GET /inventario/lotes"] == {"dias": "3"}
    assert [f["nombre"] for f in r["filas"]] == ["Manzana roja", "Piña"]
    assert r["filas"][0]["alcanza"] == Decimal("6") and r["filas"][1]["unidad"] == "pza" and r["filas"][1]["alcanza"] is None
    assert (len(r["bajos"]), len(r["sin"]), r["caducar"], r["valor"]) == (1, 1, 1, Decimal("280.00"))


def test_lotes_por_caducar_con_tono_y_texto():
    datos, _ = datos_con({"GET /inventario/lotes": (200, [LOTE])})
    [l] = datos.lotes_caducidad(1, 7)
    assert (l["tono"], l["queda_txt"], l["caducidad"]) == ("rojo", "7.8 kg", HOY + timedelta(days=1))


def test_movimientos_reconstruyen_la_existencia():
    ayer = HOY - timedelta(days=1)
    datos, _ = datos_con({
        "GET /inventario/productos": (200, [MANZANA]),
        "GET /inventario/productos/1/movimientos": (200, [
            {"fecha": HOY.isoformat(), "tipo": "Merma", "cantidad": "-1.250", "referencia": "Golpe · lote L-1", "usuario": "c"},
            {"fecha": ayer.isoformat(), "tipo": "Venta", "cantidad": "-3.000", "referencia": "1 tickets", "usuario": "POS-01"},
            {"fecha": ayer.isoformat(), "tipo": "Entrada", "cantidad": "27.500", "referencia": "Lote L-1", "usuario": "c"}])})
    m = datos.movimientos(1, ayer, HOY)
    assert [x["existencia"] for x in m["movimientos"]] == [Decimal("23.250"), Decimal("24.500"), Decimal("27.500")]
    assert (m["entradas"], m["ventas"], m["mermas"]) == (Decimal("27.500"), Decimal("3.000"), Decimal("1.250"))
    assert m["importe_ventas"] == Decimal("135.00") and m["costo_mermas"] == Decimal("40.00")
    solo_hoy = datos.movimientos(1, HOY, HOY, "Mermas")
    assert [x["tipo"] for x in solo_hoy["movimientos"]] == ["Merma"]


def test_previsualizar_no_llama_al_servidor_y_aplicar_manda_los_cambios():
    datos, mw = datos_con({"GET /inventario/productos": (200, [MANZANA]),
                           "POST /inventario/precios": (200, {"productos": 1})})
    [f] = datos.previsualizar_precios("Todos los productos", None, None, "Porcentaje de aumento", Decimal("10"))
    assert f["nuevo"] == Decimal("49.50") and not f["perdida"]
    assert list(mw.recibido) == ["GET /inventario/productos"]
    datos.aplicar_precios([f], "Temporada alta")
    assert mw.recibido["POST /inventario/precios"] == {
        "motivo": "Temporada alta", "cambios": [{"id_producto": 1, "precio_nuevo": "49.50"}]}


def test_historial_de_precios():
    datos, _ = datos_con({
        "GET /inventario/productos": (200, [MANZANA]),
        "GET /inventario/productos/1/precios": (200, [
            {"fecha": "2026-11-26T22:58:34", "anterior": "45.00", "nuevo": "46.00", "usuario": "compras1",
             "motivo": "Ajuste individual"}])})
    h = datos.historial(1)
    assert h["cambios"][0]["nuevo"] == Decimal("46.00")
    assert h["puntos"] == [("26 nov", Decimal("46.00"), Decimal("32.00")), ("Hoy", Decimal("45.00"), Decimal("32.00"))]
