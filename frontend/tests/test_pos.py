"""Lógica de pantalla del Punto de Venta (HU-06, HU-08, HU-09, HU-15, HU-38a)."""
from decimal import Decimal as D

import pytest

from app.presenters.pos import (
    CREDITO_EXCEDIDO, MONTO_INSUFICIENTE, SIN_EXISTENCIA, Carrito, cambio, diferencia_arqueo, error_corte,
    fondo_inicial, validar_cobro,
)

MANZANA = dict(id_producto=1, nombre="Manzana Gala", unidad_venta="kg", precio_venta=D("42.00"), existencia=D("10"))
PINA = dict(id_producto=8, nombre="Piña miel", unidad_venta="pza", precio_venta=D("35.00"), existencia=D("3"))
EFECTIVO = dict(id_metodo=1, es_efectivo=True, es_credito=False)
TARJETA = dict(id_metodo=2, es_efectivo=False, es_credito=False)
CREDITO = dict(id_metodo=5, es_efectivo=False, es_credito=True)


def test_importe_por_peso_redondea_a_centavos():
    c = Carrito()
    c.agregar(MANZANA, D("1.250"))
    assert c.total == D("52.50")
    c.agregar(dict(MANZANA, id_producto=2, precio_venta=D("85.00")), D("0.333"))
    assert c.total == D("52.50") + D("28.31")


def test_mismo_producto_se_suma_en_un_renglon():
    c = Carrito()
    c.agregar(MANZANA, D("1"))
    c.agregar(MANZANA, D("0.5"))
    assert len(c) == 1 and c.renglones[0].cantidad == D("1.5")


def test_sin_existencia_suficiente():
    c = Carrito()
    c.agregar(PINA, D("3"))
    with pytest.raises(ValueError, match=SIN_EXISTENCIA):
        c.agregar(PINA, D("1"))


def test_pieza_no_acepta_fracciones():
    with pytest.raises(ValueError):
        Carrito().agregar(PINA, D("1.5"))


def test_quitar_y_vaciar():
    c = Carrito()
    c.agregar(MANZANA, D("1"))
    c.agregar(PINA, D("1"))
    c.quitar(0)
    assert [r.nombre for r in c.renglones] == ["Piña miel"]
    c.vaciar()
    assert c.vacio and c.total == 0


def test_cambio_en_tiempo_real():
    assert cambio(D("168.50"), D("200")) == D("31.50")
    assert cambio(D("168.50"), None) is None


def test_validar_cobro():
    c = Carrito()
    assert validar_cobro(c, EFECTIVO, D("100"), None) == "Agregue al menos un producto."
    c.agregar(MANZANA, D("1"))  # $42.00
    assert validar_cobro(c, EFECTIVO, D("40"), None) == MONTO_INSUFICIENTE
    assert validar_cobro(c, EFECTIVO, D("42"), None) is None
    assert validar_cobro(c, TARJETA, None, None) is None
    assert validar_cobro(c, CREDITO, None, None) == "Elija el cliente de crédito."
    assert validar_cobro(c, CREDITO, None, dict(disponible=D("41.99"))) == CREDITO_EXCEDIDO
    assert validar_cobro(c, CREDITO, None, dict(disponible=D("650"))) is None


def test_fondo_inicial_por_denominacion():
    assert fondo_inicial({"Billete de $200": 2, "Billete de $100": 3, "Billete de $50": 4, "Monedas de $10": 6},
                         D("40")) == D("1000")


def test_arqueo_con_diferencia_exige_observaciones():
    assert diferencia_arqueo(D("10650.00"), D("10674.50")) == D("-24.50")
    assert error_corte(D("10650"), D("10674.50"), "", False) == ("observaciones",
                                                                 "Las observaciones son obligatorias si hay diferencia.")
    assert error_corte(D("10650"), D("10674.50"), "Cambio mal entregado", False) == (None, None)
    assert error_corte(D("10674.50"), D("10674.50"), "", False) == (None, None)
    assert error_corte(D("10674.50"), D("10674.50"), "", True)[0] == "general"
    assert error_corte(None, D("1"), "", False)[0] == "contado"
