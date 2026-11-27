"""Clientes de crédito (HU-39) y venta a crédito en el POS (HU-38a) contra un middleware simulado."""
from datetime import date, timedelta
from decimal import Decimal

from tests.test_api_caja_devoluciones import datos_con

HOY = date.today()
CLIENTE = {"id_cliente_credito": 1, "nombre": "Fonda Doña Lupe", "telefono": "5555550202", "correo": None,
           "limite_credito": "1000.00", "dias_credito": 15, "activo": True, "rfc_fiscal": None, "debe": "250.00",
           "vencido": False}
VENCIDO = {**CLIENTE, "id_cliente_credito": 2, "nombre": "Restaurante El Huerto", "vencido": True}
SUSPENDIDO = {**CLIENTE, "id_cliente_credito": 3, "nombre": "Hotel Plaza", "activo": False, "debe": "0.00"}


def test_clientes_del_pos():
    datos, _ = datos_con({"GET /pos/clientes-credito": (200, [
        {"id_cliente_credito": 1, "nombre": "Fonda Doña Lupe", "limite_credito": "1000.00", "debe": "250.00",
         "disponible": "750.00", "dias_credito": 15, "vence": (HOY + timedelta(days=15)).isoformat(), "vencido": False}])})
    [c] = datos.clientes_credito_pos()
    assert c["id"] == 1 and c["disponible"] == Decimal("750.00") and c["vence"] == HOY + timedelta(days=15)


def test_lista_de_clientes_con_estatus_de_pantalla():
    datos, mw = datos_con({"GET /finanzas/clientes-credito": (200, [CLIENTE, VENCIDO, SUSPENDIDO])})
    todos = datos.lista_clientes_credito()
    assert [c["estatus_vista"] for c in todos] == ["Activo", "Pago vencido", "Suspendido"]
    assert todos[0]["uso"] == 0.25 and todos[2]["estatus"] == "Suspendido"
    vencidos = datos.lista_clientes_credito("", "Pago vencido")
    assert mw.recibido["GET /finanzas/clientes-credito"] == {"estatus": "activos"}
    assert [c["nombre"] for c in vencidos] == ["Restaurante El Huerto"]


def test_guardar_cliente_manda_activo_y_rfc():
    datos, mw = datos_con({"POST /finanzas/clientes-credito": (201, CLIENTE),
                           "PUT /finanzas/clientes-credito/3": (200, SUSPENDIDO)})
    datos.guardar_cliente_credito(dict(nombre="Cocina Rosy", telefono="5533881200", limite=Decimal("3000"), dias=15,
                                       fiscal=None, estatus="Activo"))
    assert mw.recibido["POST /finanzas/clientes-credito"] == {
        "nombre": "Cocina Rosy", "telefono": "5533881200", "limite_credito": "3000", "dias_credito": 15,
        "rfc_fiscal": None, "activo": True}
    datos.guardar_cliente_credito(dict(id=3, nombre="Hotel Plaza", telefono="5519023344", limite=Decimal("5000"),
                                       dias=30, fiscal=None, estatus="Suspendido"))
    assert mw.recibido["PUT /finanzas/clientes-credito/3"]["activo"] is False
