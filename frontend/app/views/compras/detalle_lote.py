"""PRV-04 · Detalle del lote: avance de venta, merma y cuenta por pagar."""
from app import formato as fmt
from app.theme import C
from app.views.base import Contexto, PaginaBase
from app.widgets import Badge, Card, Celda, Col, Kpi, Tabla, boton, columnas, dato, etiqueta, fila_kpis, hbox, rejilla


class DetalleLoteView(PaginaBase):
    def __init__(self, ctx: Contexto):
        super().__init__(ctx, f'<a href="compras.lotes" style="color:{C.GUINDA}">Lotes de compra</a>', "Lote")

    def al_mostrar(self, folio: str = "", **_):
        d = self.intentar(self.ctx.datos.detalle_lote, folio)
        if not d:
            return
        self.lbl_migas.setText(f'<a href="compras.lotes" style="color:{C.GUINDA}">Lotes de compra</a> › {folio}')
        self.lbl_titulo.setText(f"Lote {folio} · {d['proveedor']}")
        etiqueta_pago = "Pagado" if d["saldo"] <= 0 else ("Pago vencido" if d["tono"] == "rojo" else "Pago pendiente")
        self.zona_derecha.addWidget(Badge(etiqueta_pago, "verde" if d["saldo"] <= 0 else d["tono"] if d["tono"] != "gris" else "naranja"))

        pct_v = (d["vendido"] / d["recibido"] * 100) if d["recibido"] else 0
        pct_m = (d["merma"] / d["recibido"] * 100) if d["recibido"] else 0
        cond = "contado" if d["dias"] == 0 else f"crédito {d['dias']} días"
        self.agregar(fila_kpis(
            Kpi("Entrada", fmt.fecha_corta(d["entrada"]), f"Factura proveedor {d['factura'] or '—'}"),
            Kpi("Total del lote", fmt.dinero(d["total"]), f"{d['recibido']:,.0f} kg · {cond}"),
            Kpi("Vendido del lote", fmt.porcentaje(pct_v), f"{d['vendido']:,.1f} de {d['recibido']:,.0f} kg"),
            Kpi("Merma", fmt.porcentaje(pct_m), f"{d['merma']:,.1f} kg · {fmt.dinero(d['costo_merma'])}", C.NARANJA),
        ))
        t = Tabla([Col("Producto", estirar=True), Col("Recibido", "der"), Col("Costo", "der"), Col("Vendido", "der"),
                   Col("Merma", "der"), Col("Existencia", "der"), Col("Caducidad")])
        t.poner_filas([
            [p["nombre"], fmt.cantidad(p["recibido"], p["unidad"], 1), fmt.precio_unitario(p["costo"], p["unidad"]),
             fmt.cantidad(p["vendido"], p["unidad"], 1), fmt.cantidad(p["merma"], p["unidad"], 1),
             Celda(fmt.cantidad(p["existencia"], p["unidad"], 1), True),
             Badge(f"{fmt.fecha(p['caducidad'])} · {_dias(p['dias'])}",
                   "gris" if p["existencia"] <= 0 else "rojo" if p["dias"] <= 1 else "naranja" if p["dias"] <= 3 else "verde")]
            for p in d["productos"]])
        self.agregar(Card("Productos").agregar(t))

        cxp = Card("Cuenta por pagar")
        if d["dias"] == 0:
            cxp.agregar(etiqueta("Lote de contado: se pagó al recibirlo.", "Muted"))
        else:
            cxp.agregar(rejilla([[dato("Vence", fmt.fecha(d["vence"])), dato("Pagado", fmt.dinero(d["pagado"])),
                                  dato("Saldo", fmt.dinero(d["saldo"]), negrita=True)]]))
            if d["saldo"] > 0 and self.ctx.sesion.puede("compras", "crear"):
                cxp.agregar(hbox(boton("Registrar pago", "primario",
                                       lambda: self.ctx.navegar("compras.cxp", lote=d["folio"])), "stretch"))
        mermas = Card("Mermas del lote")
        if d["mermas"]:
            tm = Tabla([Col("Fecha"), Col("Producto", estirar=True), Col("Cantidad", "der"), Col("Motivo"), Col("Costo", "der")])
            tm.poner_filas([[fmt.fecha(m["fecha"]), m["producto"], f"{m['cantidad']:.1f} kg", m["motivo"], fmt.dinero(m["costo"])]
                            for m in d["mermas"]])
            mermas.agregar(tm)
        else:
            mermas.agregar(etiqueta("Sin mermas registradas en este lote.", "Muted"))
        self.agregar(columnas(cxp, mermas))
        self.terminar()


def _dias(n: int) -> str:
    if n < 0:
        return "caducó"
    if n == 0:
        return "hoy"
    return "mañana" if n == 1 else f"{n} días"
