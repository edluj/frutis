"""PRV-03 · Lotes de compra registrados."""
from datetime import date

from PySide6.QtCore import QDate, Qt

from app import formato as fmt
from app.views.base import Contexto, PaginaBase
from app.widgets import Badge, Campo, Card, Celda, Col, Kpi, Tabla, boton, combo, fila_kpis, hbox, selector_fecha


def _qd(q: QDate) -> date:
    return date(q.year(), q.month(), q.day())


class LotesView(PaginaBase):
    def __init__(self, ctx: Contexto):
        acciones = [boton("+ Registrar lote", "primario", lambda: ctx.navegar("compras.lote_nuevo"))] \
            if ctx.sesion.puede("compras", "crear") else []
        super().__init__(ctx, "Proveedores y Compras", "Lotes de compra", acciones=acciones)
        self.k_compras = Kpi("Compras del periodo", "—")
        self.k_kilos = Kpi("Kilos recibidos", "—")
        self.k_pend = Kpi("Lotes con saldo pendiente", "—")
        self.agregar(fila_kpis(self.k_compras, self.k_kilos, self.k_pend))

        proveedores = self.intentar(ctx.datos.proveedores_activos) or []
        self.proveedor = combo([("Todos", None)] + [(p["razon_social"], p["id"]) for p in proveedores])
        hoy = date(2026, 11, 2) if ctx.datos.es_demo else date.today()
        self.desde = selector_fecha(hoy.replace(day=1, month=hoy.month - 1 if hoy.month > 1 else 1))
        self.hasta = selector_fecha(hoy)
        self.pago = combo(["Todos", "Pendiente", "Vencido", "Pagado"])
        self.tabla = Tabla([Col("Lote"), Col("Proveedor", estirar=True), Col("Entrada"), Col("Productos", "der"),
                            Col("Total", "der"), Col("Condición"), Col("Pago"), Col("Caducidad más próxima"), Col("", ancho=110)])
        self.agregar(Card().agregar(
            hbox(Campo("Proveedor", self.proveedor), Campo("Desde", self.desde), Campo("Hasta", self.hasta),
                 Campo("Pago", self.pago), boton("Filtrar", "secundario", self._cargar), alinear=Qt.AlignmentFlag.AlignBottom),
            self.tabla))
        self.terminar()
        self._cargar()

    def _cargar(self) -> None:
        r = self.intentar(self.ctx.datos.lista_lotes, self.proveedor.currentData(), _qd(self.desde.date()),
                          _qd(self.hasta.date()), self.pago.currentText())
        if not r:
            return
        self.k_compras.poner(fmt.dinero(r["total"]), f"{len(r['filas'])} lotes · {r['proveedores']} proveedores")
        self.k_kilos.poner(f"{r['kilos']:,.0f} kg", f"Costo promedio {fmt.dinero(r['costo_promedio'])}/kg")
        self.k_pend.poner(str(r["pendientes"]), f"{fmt.dinero(r['por_pagar'])} por pagar")
        self.tabla.poner_filas([
            [Celda(f["folio"], True), f["proveedor"], fmt.fecha(f["entrada"]), str(f["productos"]), fmt.dinero(f["total"]),
             f["condicion"], Badge(f["pago"], f["tono"]), fmt.fecha(f["caducidad"]),
             boton("Ver detalle", "link", lambda f=f: self.ctx.navegar("compras.lote", folio=f["folio"]))]
            for f in r["filas"]])
