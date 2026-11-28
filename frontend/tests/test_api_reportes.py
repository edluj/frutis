"""Reportes (HU-28, HU-29) y resumen de inicio contra un middleware simulado."""
from datetime import date
from decimal import Decimal

from app.datos.api import _RUTAS_PENDIENTES
from tests.test_api_caja_devoluciones import datos_con

REPORTE = {
    "titulo": "Productos más vendidos · por importe",
    "columnas": [{"nombre": "Producto", "alineacion": "izq", "tipo": "texto"},
                 {"nombre": "Cantidad", "alineacion": "der", "tipo": "texto"},
                 {"nombre": "Importe", "alineacion": "der", "tipo": "dinero"},
                 {"nombre": "% del total", "alineacion": "der", "tipo": "porcentaje"}],
    "filas": [["Plátano", "7.0 kg", "1500.00", "75.0"], ["Piña", "2 pza", "500.00", "25.0"]],
    "total": ["Total", "", "2000.00", "100"],
    "barras": [{"nombre": "Plátano", "fraccion": 1.0, "valor": "1500.00", "tipo": "dinero"}],
}


def test_ya_no_quedan_rutas_pendientes():
    assert _RUTAS_PENDIENTES == {}


def test_reporte_con_formato_de_pantalla():
    datos, mw = datos_con({"GET /reportes/3": (200, REPORTE)})
    r = datos.reporte(3, date(2026, 11, 1), date(2026, 11, 30), "Todos")
    assert mw.recibido["GET /reportes/3"] == {"desde": "2026-11-01", "hasta": "2026-11-30"}
    assert r["columnas"][2] == ("Importe", "der")
    assert r["filas"][0] == ["Plátano", "7.0 kg", "$1,500.00", "75.0 %"]
    assert r["total"] == ["Total", "", "$2,000.00", "100.0 %"]
    nombre, frac, texto, _color = r["barras"][0]
    assert (nombre, frac, texto) == ("Plátano", 1.0, "$1,500.00")


def test_reporte_filtrado_por_cajero_y_con_fechas():
    corte = {"titulo": "1 cortes", "columnas": [{"nombre": "Cierre", "alineacion": "izq", "tipo": "fecha"},
                                                {"nombre": "Tickets", "alineacion": "der", "tipo": "entero"}],
             "filas": [["2026-11-04", 1234]], "total": None, "barras": []}
    datos, mw = datos_con({"GET /reportes/1": (200, corte)})
    r = datos.reporte(1, date(2026, 11, 1), date(2026, 11, 30), "Cajero de prueba")
    assert mw.recibido["GET /reportes/1"]["cajero"] == "Cajero de prueba"
    assert r["filas"] == [["04/11/2026", "1,234"]] and r["total"] is None


def test_resumen_de_inicio_sin_permisos_de_finanzas_ni_inventario():
    datos, _ = datos_con({"GET /reportes/resumen-del-dia": (200, {
        "ventas_hoy": "90.00", "tickets": 2, "caja_abierta": True, "caja_detalle": "POS-01 · desde las 08:05 · Cajero",
        "caducar": None, "caducar_detalle": "Sin acceso a inventario", "por_cobrar": None,
        "por_cobrar_detalle": "Sin acceso a finanzas",
        "alertas": [{"etiqueta": "Caducidad", "texto": "Fresa, lote L-1: 2.0 kg caducan mañana.", "tono": "naranja"}]})})
    r = datos.resumen_inicio()
    assert r["ticket_promedio"] == Decimal("45.00") and r["caducar"] == "—" and r["por_cobrar"] == Decimal("0")
    assert r["alertas"] == [("Caducidad", "Fresa, lote L-1: 2.0 kg caducan mañana.", "naranja")]


def test_cajeros():
    datos, _ = datos_con({"GET /reportes/cajeros": (200, ["Cajero de prueba"])})
    assert datos.cajeros() == ["Cajero de prueba"]


def test_la_etiqueta_total_en_una_columna_de_fechas():
    mermas = {"titulo": "1 mermas", "columnas": [{"nombre": "Fecha", "alineacion": "izq", "tipo": "fecha"},
                                                 {"nombre": "Costo", "alineacion": "der", "tipo": "dinero"}],
              "filas": [["2026-11-26", "40.00"]], "total": ["Total", "40.00"], "barras": []}
    datos, _ = datos_con({"GET /reportes/2": (200, mermas)})
    assert datos.reporte(2, date(2026, 11, 1), date(2026, 11, 30), "Todos")["total"] == ["Total", "$40.00"]
