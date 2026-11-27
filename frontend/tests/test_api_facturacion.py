"""Facturación con el PAC simulado (HU-32, HU-12a, HU-33) contra un middleware simulado."""
from decimal import Decimal

import pytest

from app.datos import ErrorNegocio
from tests.test_api_caja_devoluciones import datos_con

CONCEPTO = {"nombre": "Jitomate saladet", "unidad_venta": "kg", "cantidad": "1.255", "precio_unitario": "28.50",
            "importe": "35.77", "tasa_iva": "0.0000", "clave_sat": "01010101"}
FACTURA = {"folio": "F-000002", "folio_venta": "V00000007", "uuid": "AAAAAAAA-BBBB-4CCC-8DDD-EEEEEEEEEEEE",
           "estatus": "Vigente", "rfc": "RSO100518KJ3", "razon_social": "Restaurante El Sol", "codigo_postal": "06600",
           "correo": "pagos@elsol.mx", "uso_cfdi": "G03", "forma_pago": "01", "metodo_pago": "PUE",
           "subtotal": "35.77", "iva": "0.00", "total": "35.77", "fecha_timbrado": "2026-11-27T10:00:00",
           "fecha_cancelacion": None, "motivo_cancelacion": None, "conceptos": [CONCEPTO]}
CLIENTE = {"id_cliente": 2, "rfc": "RSO100518KJ3", "razon_social": "Restaurante El Sol", "regimen_fiscal": "601",
           "codigo_postal": "06600", "correo": "pagos@elsol.mx", "facturas": 1}


def test_ticket_y_timbres():
    datos, _ = datos_con({"GET /facturacion/timbres": (200, {"disponibles": 963, "contratados": 1000}),
                          "GET /facturacion/tickets/V00000007": (200, {"folio": "V00000007", "total": "35.77",
                                                                      "metodo": "Efectivo", "conceptos": [CONCEPTO]})})
    assert datos.timbres_disponibles() == (963, 1000)
    t = datos.ticket_para_factura("V00000007")
    assert t["metodo"] == "Efectivo" and t["renglones"][0]["precio"] == Decimal("28.50")


def test_ticket_ya_facturado():
    datos, _ = datos_con({"GET /facturacion/tickets/V00000001": (409, {
        "detail": "Este ticket ya fue facturado. Un ticket solo se factura una vez.", "campo": "ticket"})})
    with pytest.raises(ErrorNegocio) as exc:
        datos.ticket_para_factura("V00000001")
    assert exc.value.campo == "ticket"


def test_timbrar_manda_las_claves_del_sat_y_devuelve_la_forma_de_la_pantalla():
    datos, mw = datos_con({"POST /facturacion/facturas": (201, FACTURA)})
    f = datos.timbrar(dict(ticket="V00000007", rfc="RSO100518KJ3", regimen="601", cp="06600", uso="G03", forma="01",
                           metodo_pago="PUE", correo="pagos@elsol.mx"))
    assert mw.recibido["POST /facturacion/facturas"]["folio_venta"] == "V00000007"
    assert f["estatus"] == "Vigente" and f["cliente"]["cp"] == "06600" and f["ticket"] == "V00000007"
    assert f["renglones"][0]["importe"] == Decimal("35.77")


def test_sin_conexion_al_timbrar():
    datos, _ = datos_con({"POST /facturacion/facturas": (503, {"detail": "Sin conexión a internet, no es posible timbrar."})})
    with pytest.raises(ErrorNegocio, match="Sin conexión a internet"):
        datos.timbrar(dict(ticket="V00000007", rfc="RSO100518KJ3", regimen="601", cp="06600", uso="G03", forma="01",
                           metodo_pago="PUE", correo="pagos@elsol.mx"))


def test_lista_de_facturas_y_cancelacion():
    datos, mw = datos_con({"GET /facturacion/facturas": (200, [FACTURA]),
                           "POST /facturacion/facturas/F-000002/cancelacion": (200, FACTURA)})
    [f] = datos.lista_facturas("", None, None, "Vigentes")
    assert mw.recibido["GET /facturacion/facturas"] == {"estatus": "Vigente"}
    assert f["cliente"] == "Restaurante El Sol"
    datos.cancelar_factura("F-000002", "01 Comprobante emitido con errores con relación", "f-000003")
    assert mw.recibido["POST /facturacion/facturas/F-000002/cancelacion"] == {"motivo": "01", "folio_sustituto": "F-000003"}


def test_editar_cliente_fiscal_usa_su_id():
    datos, mw = datos_con({"GET /facturacion/clientes": (200, [CLIENTE]), "PUT /facturacion/clientes/2": (200, CLIENTE)})
    [c] = datos.lista_clientes_fiscales()
    assert c["regimen"] == "601" and c["cp"] == "06600"
    datos.guardar_cliente_fiscal(dict(rfc="RSO100518KJ3", razon_social="Restaurante El Sol SA", regimen="601", cp="06600",
                                      correo="pagos@elsol.mx"), "RSO100518KJ3")
    assert mw.recibido["PUT /facturacion/clientes/2"]["razon_social"] == "Restaurante El Sol SA"
