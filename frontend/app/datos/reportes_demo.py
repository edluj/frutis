"""Los 12 reportes de la pantalla REP-01 armados con los datos de demostración.

Cada reporte devuelve la misma forma, así la pantalla los dibuja todos igual:
titulo, barras opcionales (nombre, fracción, texto, color), columnas, filas y total.
"""
from collections import defaultdict
from decimal import Decimal as D

from app.formato import dinero, fecha, porcentaje
from app.theme import C

NOMBRES = [
    "Corte de caja", "Mermas", "Top productos", "Variación de costos", "Flujo de caja",
    "Inventario por caducar", "Ventas por método de pago", "Estado de cuenta por proveedor",
    "Horas pico", "Facturación mensual", "Utilidad neta real", "Rendimiento por cajero",
]
COLORES = [C.GUINDA, C.CAFE, C.VERDE, "#6B625C", C.CAFE_CLARO]


def _pct(parte, total) -> D:
    return (D(parte) / D(total) * 100) if total else D("0")


def generar(datos, numero: int, desde, hasta, cajero: str) -> dict:
    return _REPORTES[numero](datos, desde, hasta, cajero)


def _corte(datos, desde, hasta, cajero):
    if datos.turno:
        r = datos.resumen_corte()
        filas = [[f["concepto"], "" if f["tickets"] is None else str(f["tickets"]), dinero(f["importe"])] for f in r["filas"]]
        return dict(titulo=f"Turno abierto · {r['caja']} · {r['tickets']} tickets", barras=[],
                    columnas=[("Concepto", "izq"), ("Tickets", "der"), ("Importe", "der")],
                    filas=filas, total=["Efectivo esperado en caja", "", dinero(r["esperado"])])
    c = datos.ultimo_corte
    return dict(titulo=f"Último corte · {c['cajero']}", barras=[], columnas=[("Concepto", "izq"), ("Importe", "der")],
                filas=[["Efectivo esperado", dinero(c["esperado"])], ["Efectivo contado", dinero(c["contado"])],
                       ["Observaciones", c["observaciones"]]],
                total=["Diferencia", dinero(c["contado"] - c["esperado"])])


def _mermas(datos, desde, hasta, cajero):
    filas = [f for f in datos.lista_mermas()["filas"] if desde <= f["fecha"] <= hasta]
    por_motivo = defaultdict(D)
    for f in filas:
        por_motivo[f["motivo"]] += f["costo"]
    total = sum(por_motivo.values(), D("0"))
    barras = [(m, float(v / total) if total else 0, porcentaje(_pct(v, total)), COLORES[i % 5])
              for i, (m, v) in enumerate(sorted(por_motivo.items(), key=lambda kv: -kv[1]))]
    return dict(titulo=f"{len(filas)} mermas · {dinero(total)}", barras=barras,
                columnas=[("Fecha", "izq"), ("Producto", "izq"), ("Lote", "izq"), ("Cantidad", "der"), ("Motivo", "izq"), ("Costo", "der")],
                filas=[[fecha(f["fecha"]), f["producto"], f["lote"], f"{f['cantidad']:.1f} {f['unidad']}", f["motivo"], dinero(f["costo"])] for f in filas],
                total=["Total", "", "", "", "", dinero(total)])


def _top(datos, desde, hasta, cajero):
    ventas = [("Plátano Tabasco", 612.5, 14700), ("Manzana Gala", 318.0, 13356), ("Aguacate Hass", 142.5, 12112.5),
              ("Jitomate saladet", 402.0, 11256), ("Fresa", 196.0, 9408), ("Limón sin semilla", 210.0, 6720)]
    total = sum(v[2] for v in ventas)
    return dict(titulo="Productos más vendidos · por importe", barras=[
        (n, imp / ventas[0][2], dinero(imp), COLORES[i % 5]) for i, (n, _, imp) in enumerate(ventas[:4])],
        columnas=[("Producto", "izq"), ("Cantidad", "der"), ("Importe", "der"), ("% del total", "der")],
        filas=[[n, f"{k:,.1f} kg", dinero(imp), porcentaje(_pct(imp, total))] for n, k, imp in ventas],
        total=["Total", "", dinero(total), "100 %"])


def _costos(datos, desde, hasta, cajero):
    filas = []
    for p in datos.productos:
        costos = [(l["entrada"], r["costo"]) for l in datos.lotes for r in l["renglones"] if r["id_producto"] == p["id_producto"]]
        if not costos:
            continue
        costos.sort()
        primero, ultimo = costos[0][1], costos[-1][1]
        filas.append([p["nombre"], dinero(min(c for _, c in costos)), dinero(max(c for _, c in costos)), dinero(ultimo),
                      porcentaje(_pct(ultimo - primero, primero))])
    return dict(titulo="Costo de compra por producto en el periodo", barras=[],
                columnas=[("Producto", "izq"), ("Mínimo", "der"), ("Máximo", "der"), ("Último", "der"), ("Variación", "der")],
                filas=filas, total=None)


def _flujo(datos, desde, hasta, cajero):
    f = datos.flujo("")
    entradas = f["ventas"] + f["cobros"]
    salidas = f["pagos_proveedores"] + f["gastos"]
    return dict(titulo="Flujo de efectivo del periodo", barras=[],
                columnas=[("Concepto", "izq"), ("Importe", "der")],
                filas=[["Saldo inicial", dinero(f["inicial"])], ["+ Ventas cobradas", dinero(f["ventas"])],
                       ["+ Cobros a clientes de crédito", dinero(f["cobros"])],
                       ["− Pagos a proveedores", dinero(-f["pagos_proveedores"])], ["− Gastos operativos", dinero(-f["gastos"])]],
                total=["Saldo final", dinero(f["inicial"] + entradas - salidas)])


def _caducar(datos, desde, hasta, cajero):
    filas = datos.lotes_caducidad(dias=7)
    total = sum((f["costo"] for f in filas), D("0"))
    return dict(titulo=f"{len(filas)} lotes caducan en 7 días o menos", barras=[],
                columnas=[("Caducidad", "izq"), ("Producto", "izq"), ("Lote", "izq"), ("Queda", "der"), ("Costo", "der")],
                filas=[[fecha(f["caducidad"]), f["producto"], f["lote"], f["queda_txt"], dinero(f["costo"])] for f in filas],
                total=["Total", "", "", "", dinero(total)])


def _metodos(datos, desde, hasta, cajero):
    filas = [("Efectivo", 812, D("176300.00")), ("Tarjeta", 420, D("98900.00")),
             ("Transferencia", 138, D("37200.00")), ("Crédito", 12, D("5840.00"))]
    total = sum((f[2] for f in filas), D("0"))
    tickets = sum(f[1] for f in filas)
    colores = [C.GUINDA, C.CAFE, C.VERDE, "#6B625C"]
    return dict(titulo=f"Octubre 2026 · {tickets:,} tickets",
                barras=[(n, float(imp / total), porcentaje(_pct(imp, total)), colores[i]) for i, (n, _, imp) in enumerate(filas)],
                columnas=[("Método", "izq"), ("Tickets", "der"), ("Importe", "der"), ("% del total", "der")],
                filas=[[n, f"{t:,}", dinero(imp), porcentaje(_pct(imp, total))] for n, t, imp in filas],
                total=["Total", f"{tickets:,}", dinero(total), "100 %"])


def _proveedores(datos, desde, hasta, cajero):
    filas, total = [], D("0")
    for p in datos.proveedores:
        e = datos.estado_cuenta_proveedor(p["id"], desde, hasta)
        if not e["movimientos"] and not e["saldo"]:
            continue
        total += e["saldo"]
        filas.append([p["razon_social"], dinero(e["compras"]), dinero(e["pagos"]), dinero(e["saldo"]), dinero(e["vencido"])])
    return dict(titulo="Saldo por proveedor", barras=[],
                columnas=[("Proveedor", "izq"), ("Compras", "der"), ("Pagos", "der"), ("Saldo", "der"), ("Vencido", "der")],
                filas=filas, total=["Total", "", "", dinero(total), ""])


def _horas(datos, desde, hasta, cajero):
    horas = [("7 a 9", 96), ("9 a 11", 248), ("11 a 13", 312), ("13 a 15", 276), ("15 a 17", 188), ("17 a 19", 204), ("19 a 21", 58)]
    maximo = max(h[1] for h in horas)
    total = sum(h[1] for h in horas)
    return dict(titulo="Tickets por franja horaria", barras=[(h, n / maximo, f"{n} tickets", C.GUINDA if n == maximo else C.CAFE_CLARO) for h, n in horas],
                columnas=[("Franja", "izq"), ("Tickets", "der"), ("% del total", "der")],
                filas=[[h, str(n), porcentaje(_pct(n, total))] for h, n in horas], total=["Total", f"{total:,}", "100 %"])


def _facturacion(datos, desde, hasta, cajero):
    filas = datos.lista_facturas(desde=desde, hasta=hasta)
    vigentes = [f for f in filas if f["estatus"] == "Vigente"]
    total = sum((f["total"] for f in vigentes), D("0"))
    return dict(titulo=f"{len(vigentes)} facturas vigentes · {dinero(total)}", barras=[],
                columnas=[("Folio", "izq"), ("Fecha", "izq"), ("Cliente", "izq"), ("Total", "der"), ("Estatus", "izq")],
                filas=[[f["folio"], fecha(f["fecha"]), f["cliente"], dinero(f["total"]), f["estatus"]] for f in filas],
                total=["Total vigente", "", "", dinero(total), ""])


def _utilidad(datos, desde, hasta, cajero):
    d = datos.dashboard("")
    mermas = datos.lista_mermas()["costo_mes"]
    neta = d["utilidad"] - mermas
    return dict(titulo="Utilidad del periodo descontando mermas", barras=[],
                columnas=[("Concepto", "izq"), ("Importe", "der")],
                filas=[["Ingresos por ventas", dinero(d["ingresos"])], ["− Compras a proveedores", dinero(-d["compras"])],
                       ["− Gastos operativos", dinero(-d["gastos"])], ["− Costo de mermas", dinero(-mermas)]],
                total=["Utilidad neta real", dinero(neta)])


def _cajeros(datos, desde, hasta, cajero):
    filas = [("Mario Pérez", 742, D("108420.50")), ("Luis Gómez", 515, D("71230.00")), ("Ana López", 125, D("18589.50"))]
    if cajero != "Todos":
        filas = [f for f in filas if f[0] == cajero]
    if not filas:
        return dict(titulo="", barras=[], columnas=[], filas=[], total=None)
    maximo = max(f[2] for f in filas)
    total = sum((f[2] for f in filas), D("0"))
    return dict(titulo="Ventas por cajero", barras=[(n, float(imp / maximo), dinero(imp), C.GUINDA) for n, _, imp in filas],
                columnas=[("Cajero", "izq"), ("Tickets", "der"), ("Importe", "der"), ("Ticket promedio", "der")],
                filas=[[n, f"{t:,}", dinero(imp), dinero(imp / t)] for n, t, imp in filas],
                total=["Total", f"{sum(f[1] for f in filas):,}", dinero(total), ""])


_REPORTES = {1: _corte, 2: _mermas, 3: _top, 4: _costos, 5: _flujo, 6: _caducar, 7: _metodos, 8: _proveedores,
             9: _horas, 10: _facturacion, 11: _utilidad, 12: _cajeros}
