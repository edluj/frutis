"""Los 12 reportes de REP-01 (HU-28, HU-29) y el resumen del día de la pantalla de inicio."""
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import Connection

from app.errores import ErrorNegocio
from app.repositories import compras, facturacion, finanzas, inventario, pos, usuarios
from app.repositories import reportes as repositorio
from app.schemas.reportes import Alerta, Barra, Columna, Reporte, ResumenDelDia
from app.security.dependencias import UsuarioActual
from app.services import finanzas as calculo

CERO = Decimal("0.00")
MESES_CORTOS = calculo.MESES_CORTOS
MOTIVOS = {"maduracion": "Maduración", "golpe": "Golpe", "plaga": "Plaga u hongo", "caducidad": "Caducidad",
           "devolucion": "Devolución en mal estado", "otro": "Otro"}
FRANJAS = [(7, 9), (9, 11), (11, 13), (13, 15), (15, 17), (17, 19), (19, 21)]


def _c(nombre: str, tipo: str = "texto", alineacion: str | None = None) -> Columna:
    return Columna(nombre=nombre, tipo=tipo, alineacion=alineacion or ("izq" if tipo in ("texto", "fecha") else "der"))


def _pct(parte, total) -> Decimal:
    return (Decimal(parte) / Decimal(total) * 100).quantize(Decimal("0.1")) if total else Decimal("0.0")


def _cantidad(valor: Decimal, unidad: str) -> str:
    return f"{valor:,.1f} kg" if unidad == "kg" else f"{valor:,.0f} pza"


def _corte(conn, desde, hasta, cajero):
    filas = repositorio.cortes(conn, desde, hasta, cajero)
    diferencia = sum((f["diferencia"] or CERO for f in filas), CERO)
    return Reporte(
        titulo=f"{len(filas)} cortes · diferencia total", columnas=[
            _c("Terminal"), _c("Cajero"), _c("Cierre", "fecha"), _c("Esperado", "dinero"), _c("Contado", "dinero"),
            _c("Diferencia", "dinero"), _c("Observaciones")],
        filas=[[f["terminal"], f["cajero"], f["fecha_cierre"].date().isoformat(), f["efectivo_esperado"],
                f["efectivo_contado"], f["diferencia"], f["observaciones"] or ""] for f in filas],
        total=["Total", "", "", None, None, diferencia, ""] if filas else None)


def _mermas(conn, desde, hasta, cajero):
    filas = inventario.listar_mermas(conn, None, desde, hasta)
    por_motivo: dict[str, Decimal] = defaultdict(lambda: CERO)
    for f in filas:
        por_motivo[MOTIVOS[f["motivo"]]] += f["costo"]
    total = sum(por_motivo.values(), CERO)
    return Reporte(
        titulo=f"{len(filas)} mermas", columnas=[
            _c("Fecha", "fecha"), _c("Producto"), _c("Lote"), _c("Cantidad", "texto", "der"), _c("Motivo"), _c("Costo", "dinero")],
        filas=[[f["fecha"].isoformat(), f["producto"], f["lote"], _cantidad(f["cantidad"], f["unidad_venta"]),
                MOTIVOS[f["motivo"]], f["costo"]] for f in filas],
        total=["Total", "", "", "", "", total] if filas else None,
        barras=[Barra(nombre=m, fraccion=float(v / total) if total else 0, valor=_pct(v, total), tipo="porcentaje")
                for m, v in sorted(por_motivo.items(), key=lambda kv: -kv[1])])


def _top(conn, desde, hasta, cajero):
    filas = repositorio.ventas_por_producto(conn, desde, hasta)
    total = sum((f["importe"] for f in filas), CERO)
    maximo = filas[0]["importe"] if filas else 0
    return Reporte(
        titulo="Productos más vendidos · por importe", columnas=[
            _c("Producto"), _c("Cantidad", "texto", "der"), _c("Importe", "dinero"), _c("% del total", "porcentaje")],
        filas=[[f["nombre"], _cantidad(f["cantidad"], f["unidad_venta"]), f["importe"], _pct(f["importe"], total)]
               for f in filas],
        total=["Total", "", total, Decimal("100")] if filas else None,
        barras=[Barra(nombre=f["nombre"], fraccion=float(f["importe"] / maximo), valor=f["importe"], tipo="dinero")
                for f in filas[:4]])


def _costos(conn, desde, hasta, cajero):
    por_producto: dict[str, list[Decimal]] = defaultdict(list)
    for f in repositorio.costos_de_compra(conn, desde, hasta):
        por_producto[f["nombre"]].append(f["costo"])
    return Reporte(
        titulo="Costo de compra por producto en el periodo", columnas=[
            _c("Producto"), _c("Mínimo", "dinero"), _c("Máximo", "dinero"), _c("Último", "dinero"),
            _c("Variación", "porcentaje")],
        filas=[[n, min(c), max(c), c[-1], _pct(c[-1] - c[0], c[0])] for n, c in por_producto.items()])


def _flujo(conn, desde, hasta, cajero):
    fin = hasta + timedelta(days=1)
    eventos, previos = finanzas.eventos(conn, desde, fin), finanzas.eventos(conn, None, desde)
    inicial = calculo._entradas(previos) - calculo._salidas(previos)
    ventas = calculo._suma(eventos, "venta_cobrada") - calculo._suma(eventos, "devolucion_pagada")
    cobros = calculo._suma(eventos, "cobro")
    pagos = calculo._suma(eventos, "pago_proveedor", "compra_contado")
    gastos = calculo._suma(eventos, "gasto")
    return Reporte(
        titulo="Flujo de efectivo del periodo", columnas=[_c("Concepto"), _c("Importe", "dinero")],
        filas=[["Saldo inicial", inicial], ["+ Ventas cobradas", ventas], ["+ Cobros a clientes de crédito", cobros],
               ["− Pagos a proveedores", -pagos], ["− Gastos operativos", -gastos]],
        total=["Saldo final", inicial + ventas + cobros - pagos - gastos])


def _caducar(conn, desde, hasta, cajero):
    filas = inventario.lotes_por_caducar(conn, 7, None, None)
    total = sum((f["costo"] for f in filas), CERO)
    return Reporte(
        titulo=f"{len(filas)} lotes caducados o por caducar en 7 días", columnas=[
            _c("Caducidad", "fecha"), _c("Producto"), _c("Lote"), _c("Queda", "texto", "der"), _c("Costo", "dinero")],
        filas=[[f["caducidad"].isoformat(), f["producto"], f["lote"], _cantidad(f["queda"], f["unidad_venta"]), f["costo"]]
               for f in filas],
        total=["Total", "", "", "", total] if filas else None)


def _metodos(conn, desde, hasta, cajero):
    filas = repositorio.ventas_por_metodo(conn, desde, hasta)
    total, tickets = sum((f["importe"] for f in filas), CERO), sum(f["tickets"] for f in filas)
    return Reporte(
        titulo=f"{tickets:,} tickets", columnas=[
            _c("Método"), _c("Tickets", "entero"), _c("Importe", "dinero"), _c("% del total", "porcentaje")],
        filas=[[f["metodo"], f["tickets"], f["importe"], _pct(f["importe"], total)] for f in filas],
        total=["Total", tickets, total, Decimal("100")] if filas else None,
        barras=[Barra(nombre=f["metodo"], fraccion=float(f["importe"] / total) if total else 0,
                      valor=_pct(f["importe"], total), tipo="porcentaje") for f in filas])


def _proveedores(conn, desde, hasta, cajero):
    filas = [f for f in repositorio.saldos_por_proveedor(conn, desde, hasta) if f["compras"] or f["pagos"] or f["saldo"]]
    return Reporte(
        titulo="Saldo por proveedor", columnas=[
            _c("Proveedor"), _c("Compras", "dinero"), _c("Pagos", "dinero"), _c("Saldo", "dinero"), _c("Vencido", "dinero")],
        filas=[[f["razon_social"], f["compras"], f["pagos"], f["saldo"], f["vencido"]] for f in filas],
        total=["Total", None, None, sum((f["saldo"] for f in filas), CERO), None] if filas else None)


def _horas(conn, desde, hasta, cajero):
    por_hora = {f["hora"]: f["tickets"] for f in repositorio.tickets_por_hora(conn, desde, hasta)}
    franjas = [(f"{a} a {b}", sum(n for h, n in por_hora.items() if a <= h < b)) for a, b in FRANJAS]
    fuera = sum(n for h, n in por_hora.items() if not FRANJAS[0][0] <= h < FRANJAS[-1][1])
    if fuera:
        franjas.append(("Otras horas", fuera))
    total = sum(n for _, n in franjas)
    maximo = max((n for _, n in franjas), default=0)
    return Reporte(
        titulo="Tickets por franja horaria", columnas=[_c("Franja"), _c("Tickets", "entero"), _c("% del total", "porcentaje")],
        filas=[[f, n, _pct(n, total)] for f, n in franjas] if total else [],
        total=["Total", total, Decimal("100")] if total else None,
        barras=[Barra(nombre=f, fraccion=n / maximo, valor=n, tipo="tickets") for f, n in franjas] if maximo else [])


def _facturacion(conn, desde, hasta, cajero):
    filas = facturacion.listar_facturas(conn, None, desde, hasta)
    vigentes = [f for f in filas if f["estatus"] == "Vigente"]
    total = sum((f["total"] for f in vigentes), CERO)
    return Reporte(
        titulo=f"{len(vigentes)} facturas vigentes", columnas=[
            _c("Folio"), _c("Fecha", "fecha"), _c("Cliente"), _c("Total", "dinero"), _c("Estatus")],
        filas=[[f["folio"], (f["fecha_timbrado"].date() if f["fecha_timbrado"] else desde).isoformat(), f["razon_social"],
                f["total"], f["estatus"]] for f in filas],
        total=["Total vigente", "", "", total, ""] if filas else None)


def _utilidad(conn, desde, hasta, cajero):
    eventos = finanzas.eventos(conn, desde, hasta + timedelta(days=1))
    ingresos = calculo._ingresos(eventos)
    compras_ = calculo._suma(eventos, "compra_contado", "compra_credito")
    gastos = calculo._suma(eventos, "gasto")
    mermas = repositorio.costo_mermas(conn, desde, hasta)
    return Reporte(
        titulo="Utilidad del periodo descontando mermas", columnas=[_c("Concepto"), _c("Importe", "dinero")],
        filas=[["Ingresos por ventas", ingresos], ["− Compras a proveedores", -compras_], ["− Gastos operativos", -gastos],
               ["− Costo de mermas", -mermas]],
        total=["Utilidad neta real", ingresos - compras_ - gastos - mermas])


def _cajeros(conn, desde, hasta, cajero):
    filas = repositorio.ventas_por_cajero(conn, desde, hasta, cajero)
    maximo = filas[0]["importe"] if filas else 0
    return Reporte(
        titulo="Ventas por cajero", columnas=[
            _c("Cajero"), _c("Tickets", "entero"), _c("Importe", "dinero"), _c("Ticket promedio", "dinero")],
        filas=[[f["cajero"], f["tickets"], f["importe"], (f["importe"] / f["tickets"]).quantize(CERO)] for f in filas],
        total=["Total", sum(f["tickets"] for f in filas), sum((f["importe"] for f in filas), CERO), None] if filas else None,
        barras=[Barra(nombre=f["cajero"], fraccion=float(f["importe"] / maximo), valor=f["importe"], tipo="dinero")
                for f in filas])


REPORTES = {1: _corte, 2: _mermas, 3: _top, 4: _costos, 5: _flujo, 6: _caducar, 7: _metodos, 8: _proveedores,
            9: _horas, 10: _facturacion, 11: _utilidad, 12: _cajeros}


def reporte(conn: Connection, numero: int, desde: date, hasta: date, cajero: str | None) -> Reporte:
    if hasta < desde:
        raise ErrorNegocio(409, "La fecha final es anterior a la inicial.")
    return REPORTES[numero](conn, desde, hasta, cajero)


# ---------------------------------------------------------------- resumen del día (ACC-02)

def _fecha_corta(d: date) -> str:
    return f"{d.day} {MESES_CORTOS[d.month - 1]}"


def resumen(conn: Connection, usuario: UsuarioActual) -> ResumenDelDia:
    """Cada parte solo aparece si el rol puede ver su módulo: un cajero no ve lo que deben los clientes."""
    puede = {p["modulo"] for p in usuarios.permisos_del_rol(conn, usuario.id_rol) if p["puede_ver"]}
    ve_todo = "reportes" in puede or "finanzas" in puede
    ventas = repositorio.ventas_de_hoy(conn, None if ve_todo else usuario.id_usuario)
    caja = pos.caja_abierta_de(conn, usuario.id_usuario)
    alertas: list[Alerta] = []
    caducar, caducar_detalle = None, "Sin acceso a inventario"
    if "inventario" in puede:
        lotes = inventario.lotes_por_caducar(conn, 3, None, None)
        nombres = sorted({l["producto"] for l in lotes})
        caducar = len(lotes)
        caducar_detalle = (", ".join(nombres[:2]) + (f" y {len(nombres) - 2} productos más" if len(nombres) > 2 else "")
                           ) or "Sin lotes por caducar"
        for l in lotes[:1]:
            cuando = "ya caducaron" if l["dias"] < 0 else "caducan hoy" if l["dias"] == 0 else (
                "caducan mañana" if l["dias"] == 1 else f"caducan en {l['dias']} días")
            alertas.append(Alerta(etiqueta="Caducidad", texto=f"{l['producto']}, lote {l['lote']}: "
                                  f"{_cantidad(l['queda'], l['unidad_venta'])} {cuando}.", tono="naranja"))
        for e in inventario.existencias(conn):
            if CERO < e["existencia"] < e["stock_minimo"]:
                alertas.append(Alerta(etiqueta="", tono="rojo", texto=f"Stock bajo: {e['nombre']} tiene "
                                      f"{_cantidad(e['existencia'], e['unidad_venta'])} (mínimo "
                                      f"{_cantidad(e['stock_minimo'], e['unidad_venta'])})."))
                break
    if "compras" in puede:
        hoy = date.today()
        for c in compras.cuentas_por_pagar(conn, None):
            if c["saldo"] > 0 and c["vence"] <= hoy + timedelta(days=3):
                verbo = "venció" if c["vence"] < hoy else "vence"
                alertas.append(Alerta(etiqueta="Por pagar", tono="rojo" if c["vence"] < hoy else "naranja",
                                      texto=f"{c['proveedor']}, lote {c['lote']}: ${c['saldo']:,.2f} {verbo} el "
                                      f"{_fecha_corta(c['vence'])}."))
                break
    por_cobrar, por_cobrar_detalle = None, "Sin acceso a finanzas"
    if "finanzas" in puede:
        abiertas = [c for c in finanzas.cuentas_por_cobrar(conn, None) if c["saldo"] > 0]
        vencidas = [c for c in abiertas if c["vence"] < date.today()]
        por_cobrar = sum((c["saldo"] for c in abiertas), CERO)
        por_cobrar_detalle = f"{len({c['cliente'] for c in abiertas})} clientes · {len(vencidas)} vencidas"
        for c in vencidas[:1]:
            alertas.append(Alerta(etiqueta="", tono="rojo", texto=f"Cobro vencido: {c['cliente']} debe "
                                  f"${c['saldo']:,.2f} desde el {_fecha_corta(c['vence'])}."))
    return ResumenDelDia(
        ventas_hoy=ventas["importe"], tickets=ventas["tickets"], caja_abierta=caja is not None,
        caja_detalle=(f"{caja['terminal']} · desde las {caja['fecha_apertura']:%H:%M} · {usuario.nombre_completo}"
                      if caja else "Ninguna caja abierta"),
        caducar=caducar, caducar_detalle=caducar_detalle, por_cobrar=por_cobrar, por_cobrar_detalle=por_cobrar_detalle,
        alertas=alertas)
