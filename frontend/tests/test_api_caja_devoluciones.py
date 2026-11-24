"""Apertura, corte y devoluciones contra un middleware simulado (rutas de middleware/README.md)."""
import json
from decimal import Decimal

import httpx
import pytest

from app.datos import ErrorNegocio
from app.datos.api import DatosApi
from tests.test_api_client import cliente

CAJA = {"id_caja": 7, "terminal": "POS-1", "fondo_inicial": "500.00", "fecha_apertura": "2026-11-24T08:00:00"}
RESUMEN = {
    **CAJA,
    "ventas": [
        {"metodo": "Efectivo", "es_efectivo": True, "es_credito": False, "tickets": 3, "importe": "300.00"},
        {"metodo": "Tarjeta de débito", "es_efectivo": False, "es_credito": False, "tickets": 1, "importe": "70.00"},
        {"metodo": "Transferencia", "es_efectivo": False, "es_credito": False, "tickets": 0, "importe": "0.00"},
        {"metodo": "Crédito", "es_efectivo": False, "es_credito": True, "tickets": 1, "importe": "22.00"},
    ],
    "cobros_efectivo": {"cantidad": 1, "importe": "10.00"},
    "devoluciones_efectivo": {"cantidad": 1, "importe": "20.00"},
    "efectivo_esperado": "790.00",
}
TICKET = {
    "id_venta": 1, "folio": "V00000001", "fecha": "2026-11-24T09:00:00", "metodo": "Efectivo", "es_credito": False,
    "total": "135.00", "estatus": "pagada", "facturado": False, "cliente": None,
    "renglones": [{"id_producto": 1, "nombre": "Manzana roja", "unidad_venta": "kg", "cantidad": "3.000",
                   "precio_unitario": "45.00", "importe": "135.00", "devuelto": "0.000"}],
}


class Middleware:
    """Responde por ruta y guarda lo que recibió."""

    def __init__(self, respuestas: dict):
        self.respuestas = respuestas
        self.recibido: dict[str, object] = {}

    def __call__(self, req: httpx.Request) -> httpx.Response:
        clave = f"{req.method} {req.url.path}"
        self.recibido[clave] = json.loads(req.content) if req.content else dict(req.url.params)
        status, cuerpo = self.respuestas[clave]
        return httpx.Response(status, json=cuerpo)


def datos_con(respuestas: dict) -> tuple[DatosApi, Middleware]:
    mw = Middleware(respuestas)
    return DatosApi(cliente(mw), "POS-1"), mw


def test_apertura_manda_la_terminal_y_el_fondo():
    datos, mw = datos_con({"POST /pos/cajas": (201, CAJA)})
    assert datos.cajas_disponibles() == [{"id_caja": "POS-1", "nombre": "Terminal POS-1"}]
    caja = datos.abrir_caja("POS-1", Decimal("500.00"))
    assert mw.recibido["POST /pos/cajas"] == {"terminal": "POS-1", "fondo_inicial": "500.00"}
    assert caja["id_caja"] == 7 and caja["fondo_inicial"] == Decimal("500.00")


def test_apertura_rechazada_muestra_el_mensaje_de_la_base():
    datos, _ = datos_con({"POST /pos/cajas": (409, {"detail": "Ya hay una caja abierta en esta terminal."})})
    with pytest.raises(ErrorNegocio, match="Ya hay una caja abierta"):
        datos.abrir_caja("POS-1", Decimal("0"))


def test_ultimo_corte_sin_cortes_es_none():
    datos, mw = datos_con({"GET /pos/cortes/ultimo": (404, {"detail": "Esta terminal todavía no tiene cortes."})})
    assert datos.datos_ultimo_corte("POS-1") is None
    assert mw.recibido["GET /pos/cortes/ultimo"] == {"terminal": "POS-1"}


def test_resumen_del_corte_arma_las_filas_de_la_pantalla():
    datos, _ = datos_con({"GET /pos/cortes/actual": (200, RESUMEN)})
    r = datos.resumen_corte()
    conceptos = [(f["concepto"], f["tickets"], f["importe"]) for f in r["filas"]]
    assert conceptos == [
        ("Fondo inicial", None, Decimal("500.00")),
        ("Ventas en efectivo", 3, Decimal("300.00")),
        ("Ventas con tarjeta de débito", 1, Decimal("70.00")),
        ("Ventas por transferencia", 0, Decimal("0.00")),
        ("Ventas a crédito", 1, Decimal("22.00")),
        ("Cobros a clientes en efectivo", 1, Decimal("10.00")),
        ("Devoluciones en efectivo", 1, Decimal("-20.00")),
    ]
    assert r["esperado"] == Decimal("790.00") and r["tickets"] == 5 and r["caja"] == "Caja 7"


def test_corte_usa_la_caja_del_resumen():
    datos, mw = datos_con({
        "GET /pos/cortes/actual": (200, RESUMEN),
        "POST /pos/cortes": (201, {"id_caja": 7, "efectivo_esperado": "790.00", "efectivo_contado": "780.00",
                                   "diferencia": "-10.00"}),
    })
    datos.resumen_corte()
    r = datos.cerrar_caja(Decimal("780.00"), "Faltan $10")
    assert mw.recibido["POST /pos/cortes"] == {"id_caja": 7, "efectivo_contado": "780.00", "observaciones": "Faltan $10"}
    assert r["diferencia"] == Decimal("-10.00")


def test_corte_sin_observaciones_marca_el_campo():
    datos, _ = datos_con({
        "GET /pos/cortes/actual": (200, RESUMEN),
        "POST /pos/cortes": (409, {"detail": "Escriba las observaciones: hay diferencia en el arqueo."}),
    })
    datos.resumen_corte()
    with pytest.raises(ErrorNegocio) as exc:
        datos.cerrar_caja(Decimal("1"), "")
    assert exc.value.campo == "observaciones"


def test_observaciones_con_caracteres_prohibidos_marcan_el_campo():
    datos, _ = datos_con({
        "GET /pos/cortes/actual": (200, RESUMEN),
        "POST /pos/cortes": (422, {"detail": "Datos inválidos.",
                                   "errores": [{"campo": "body.observaciones", "mensaje": "x"}]}),
    })
    datos.resumen_corte()
    with pytest.raises(ErrorNegocio, match="comillas") as exc:
        datos.cerrar_caja(Decimal("1"), 'dijo "hola"')
    assert exc.value.campo == "observaciones"


def test_buscar_ticket_convierte_montos():
    datos, _ = datos_con({"GET /pos/ventas/V00000001": (200, TICKET)})
    t = datos.buscar_ticket(" v00000001 ")
    assert t["folio"] == "V00000001"
    assert t["renglones"][0]["cantidad"] == Decimal("3.000") and t["renglones"][0]["precio"] == Decimal("45.00")


def test_devolucion_completa_con_autorizacion_por_ticket():
    datos, mw = datos_con({
        "GET /pos/devoluciones/administradores": (200, [{"usuario": "admin", "nombre_completo": "Ana López"}]),
        "POST /pos/devoluciones/autorizacion": (200, {"autorizacion": "firmada", "autorizado_por": "Ana López",
                                                      "expira_minutos": 5}),
        "GET /pos/cajas/actual": (200, CAJA),
        "POST /pos/devoluciones": (201, {"folio": "D00000001-1", "total": "67.50", "reembolso": "efectivo"}),
    })
    assert datos.administradores() == ["Ana López"]
    with pytest.raises(ErrorNegocio, match="Busca primero el ticket"):
        datos.autorizar("Ana López", "x")
    assert datos.autorizar("Ana López", "secreta", "V00000001").startswith("Autorizado por Ana López")
    assert mw.recibido["POST /pos/devoluciones/autorizacion"] == {
        "usuario": "admin", "password": "secreta", "folio_venta": "V00000001"}

    renglones = [dict(id_producto=1, cantidad=Decimal("1.000"), buen_estado=True),
                 dict(id_producto=1, cantidad=Decimal("0.500"), buen_estado=False)]
    with pytest.raises(ErrorNegocio, match="Falta la autorización"):
        datos.procesar_devolucion("V00000002", renglones, "Producto en mal estado", "Efectivo (sale de la caja)", "Ana")
    r = datos.procesar_devolucion("V00000001", renglones, "Producto en mal estado", "Efectivo (sale de la caja)", "Ana")
    assert r["total"] == Decimal("67.50")
    assert mw.recibido["POST /pos/devoluciones"] == {
        "id_caja": 7, "folio_venta": "V00000001", "motivo": "Producto en mal estado", "reembolso": "efectivo",
        "autorizacion": "firmada",
        "renglones": [{"id_producto": 1, "cantidad": "1.000", "estado": "bueno"},
                      {"id_producto": 1, "cantidad": "0.500", "estado": "danado"}],
    }
    # La autorización se usa una vez.
    with pytest.raises(ErrorNegocio, match="Falta la autorización"):
        datos.procesar_devolucion("V00000001", renglones, "x", "Efectivo (sale de la caja)", "Ana")


def test_contrasena_del_administrador_incorrecta_no_cierra_la_sesion_del_cajero():
    datos, _ = datos_con({
        "GET /pos/devoluciones/administradores": (200, [{"usuario": "admin", "nombre_completo": "Ana López"}]),
        "POST /pos/devoluciones/autorizacion": (403, {"detail": "Contraseña del Administrador incorrecta."}),
    })
    datos.administradores()
    datos.api._token = "sesion-del-cajero"
    with pytest.raises(ErrorNegocio, match="Contraseña del Administrador incorrecta."):
        datos.autorizar("Ana López", "mala", "V00000001")
    assert datos.api.autenticado
