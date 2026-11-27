"""Categorías (HU-22) y productos (HU-10) contra un middleware simulado (rutas de middleware/README.md)."""
from decimal import Decimal

import pytest

from app.datos import ErrorNegocio
from tests.test_api_caja_devoluciones import datos_con

CATEGORIA = {"id_categoria": 1, "nombre": "Frutas", "descripcion": None, "activo": True, "productos_activos": 4}
PRODUCTO = {
    "id_producto": 4, "codigo_barras": "FRU-0004", "nombre": "Piña", "id_categoria": 1, "categoria": "Frutas",
    "unidad_venta": "pieza", "precio_venta": "35.00", "costo_actual": "22.00", "tasa_iva": "0.1600",
    "stock_minimo": "4.000", "es_frecuente": True, "activo": True, "existencia": "3.000", "estado": "Bajo",
}


def test_categorias_con_la_forma_de_la_pantalla():
    datos, mw = datos_con({"GET /inventario/categorias": (200, [CATEGORIA])})
    assert datos.lista_categorias("fru") == [
        {"id": 1, "nombre": "Frutas", "descripcion": "", "activa": True, "productos": 4}]
    assert mw.recibido["GET /inventario/categorias"] == {"busqueda": "fru"}
    datos.categorias_activas()
    assert mw.recibido["GET /inventario/categorias"] == {"activas": "true"}


def test_alta_y_edicion_de_categoria():
    datos, mw = datos_con({"POST /inventario/categorias": (201, CATEGORIA), "PUT /inventario/categorias/1": (200, CATEGORIA)})
    datos.guardar_categoria({"nombre": "Frutas", "descripcion": "", "activa": True})
    assert mw.recibido["POST /inventario/categorias"] == {"nombre": "Frutas", "descripcion": None, "activo": True}
    datos.guardar_categoria({"id": 1, "nombre": "Frutas", "descripcion": "Fresca", "activa": False})
    assert mw.recibido["PUT /inventario/categorias/1"]["activo"] is False


def test_error_de_categoria_llega_con_su_campo():
    mensaje = "No se puede dar de baja: tiene 4 productos activos."
    datos, _ = datos_con({"PUT /inventario/categorias/1": (409, {"detail": mensaje, "campo": "estatus"})})
    with pytest.raises(ErrorNegocio) as exc:
        datos.guardar_categoria({"id": 1, "nombre": "Frutas", "descripcion": "", "activa": False})
    assert (exc.value.mensaje, exc.value.campo) == (mensaje, "estatus")


def test_productos_traducen_unidad_estado_y_filtro():
    datos, mw = datos_con({"GET /inventario/productos": (200, [PRODUCTO])})
    [p] = datos.lista_productos("", 1, "Bajo el mínimo")
    assert mw.recibido["GET /inventario/productos"] == {"id_categoria": "1", "existencia": "bajo"}
    assert p["unidad_venta"] == "pza" and p["tono"] == "rojo"
    assert p["precio_venta"] == Decimal("35.00") and p["existencia"] == Decimal("3.000")


def test_alta_de_producto_manda_la_unidad_de_la_base():
    datos, mw = datos_con({"POST /inventario/productos": (201, PRODUCTO)})
    datos.guardar_producto(dict(codigo_barras="FRU-0004", nombre="Piña", id_categoria=1, unidad_venta="pza",
                                precio_venta=Decimal("35.00"), stock_minimo=Decimal("4"), activo=True))
    cuerpo = mw.recibido["POST /inventario/productos"]
    assert cuerpo["unidad_venta"] == "pieza" and cuerpo["precio_venta"] == "35.00"


def test_editar_producto_conserva_iva_y_acceso_rapido():
    datos, mw = datos_con({"GET /inventario/productos": (200, [PRODUCTO]), "PUT /inventario/productos/4": (200, PRODUCTO)})
    datos.guardar_producto(dict(id_producto=4, codigo_barras="FRU-0004", nombre="Piña", id_categoria=1,
                                unidad_venta="pza", precio_venta=Decimal("38.00"), stock_minimo=Decimal("4"), activo=True))
    cuerpo = mw.recibido["PUT /inventario/productos/4"]
    assert cuerpo["tasa_iva"] == "0.1600" and cuerpo["es_frecuente"] is True and cuerpo["precio_venta"] == "38.00"


def test_codigo_repetido_marca_el_campo():
    datos, _ = datos_con({"POST /inventario/productos": (409, {"detail": "El código de barras ya está registrado.",
                                                               "campo": "codigo"})})
    with pytest.raises(ErrorNegocio) as exc:
        datos.guardar_producto(dict(codigo_barras="FRU-0001", nombre="X", id_categoria=1, unidad_venta="kg",
                                    precio_venta=Decimal("1"), stock_minimo=Decimal("0")))
    assert exc.value.campo == "codigo"
