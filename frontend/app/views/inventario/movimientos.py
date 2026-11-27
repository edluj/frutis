"""CAT-05 · Movimientos de inventario de un producto (kardex)."""
from datetime import date, timedelta

from PySide6.QtCore import QDate

from app import formato as fmt
from app.theme import C
from app.views.base import Contexto, PaginaBase
from app.widgets import Badge, Campo, Card, Celda, Col, Kpi, Tabla, combo, fila_kpis, hbox, selector_fecha


def _qd(q: QDate) -> date:
    return date(q.year(), q.month(), q.day())


class MovimientosView(PaginaBase):
    def __init__(self, ctx: Contexto):
        super().__init__(ctx, f'<a href="inv.productos" style="color:{C.GUINDA}">Productos</a> › Movimientos', "Movimientos")
        if ctx.datos.es_demo:
            self.lbl_estado.setVisible(False)
            self.punto.setVisible(False)
        self.badge = None
        self.k_ent = Kpi("Entradas", "—", color=C.VERDE)
        self.k_ven = Kpi("Ventas", "—")
        self.k_mer = Kpi("Mermas", "—", color=C.NARANJA)
        self.k_exi = Kpi("Existencia", "—")
        self.agregar(fila_kpis(self.k_ent, self.k_ven, self.k_mer, self.k_exi))
        productos = self.intentar(ctx.datos.lista_productos) or []
        self.producto = combo([(p["nombre"], p["id_producto"]) for p in productos])
        hoy = date(2026, 11, 2) if ctx.datos.es_demo else date.today()
        self.desde = selector_fecha(hoy - timedelta(days=8))
        self.hasta = selector_fecha(hoy)
        self.tipo = combo(["Todos", "Entradas", "Ventas", "Mermas"])
        for w in (self.producto, self.tipo):
            w.currentIndexChanged.connect(self._cargar)
        for w in (self.desde, self.hasta):
            w.dateChanged.connect(self._cargar)
        self.tabla = Tabla([Col("Fecha"), Col("Movimiento"), Col("Referencia", estirar=True), Col("Cantidad", "der"),
                            Col("Existencia", "der"), Col("Usuario")])
        self.agregar(Card().agregar(hbox(Campo("Producto", self.producto), Campo("Desde", self.desde),
                                         Campo("Hasta", self.hasta), Campo("Tipo", self.tipo)), self.tabla))
        self.terminar()

    def al_mostrar(self, id_producto=None, **_):
        if id_producto:
            i = self.producto.findData(int(id_producto))
            if i >= 0:
                self.producto.blockSignals(True)
                self.producto.setCurrentIndex(i)
                self.producto.blockSignals(False)
        self._cargar()

    def _cargar(self, *_):
        if self.producto.currentData() is None:
            return
        m = self.intentar(self.ctx.datos.movimientos, self.producto.currentData(), _qd(self.desde.date()),
                          _qd(self.hasta.date()), self.tipo.currentText())
        if not m:
            return
        u = "kg" if m["unidad"] == "kg" else "pza"
        d = 1 if u == "kg" else 0
        self.lbl_titulo.setText(m["producto"]["nombre"])
        if self.badge:
            self.badge.deleteLater()
        self.badge = Badge("Bajo el mínimo" if m["bajo"] else "Normal", "rojo" if m["bajo"] else "verde")
        self.zona_derecha.addWidget(self.badge)
        self.k_ent.poner(f"+{m['entradas']:.{d}f} {u}", f"{m['lotes_entrada']} lote{'s' if m['lotes_entrada'] != 1 else ''}")
        self.k_ven.poner(f"{fmt.MENOS}{m['ventas']:.{d}f} {u}", f"{fmt.dinero(m['importe_ventas'])} vendidos")
        self.k_mer.poner(f"{fmt.MENOS}{m['mermas']:.{d}f} {u}",
                         f"{fmt.porcentaje(m['pct_merma'], 0)} de lo recibido · {fmt.dinero(m['costo_mermas'])}")
        self.k_exi.poner(f"{m['existencia']:.{d}f} {u}", f"Mínimo {m['minimo']:.0f} {u}", C.ROJO if m["bajo"] else C.TEXTO)
        filas = []
        for x in m["movimientos"]:
            cant = x["cantidad"]
            txt = f"+{cant:.{d}f} {u}" if cant > 0 else f"{fmt.MENOS}{-cant:.{d}f} {u}"
            filas.append([fmt.fecha(x["fecha"]), Badge(x["tipo"], x["tono"]), x["referencia"],
                          Celda(txt, cant > 0, C.VERDE_TEXTO if cant > 0 else None),
                          Celda(f"{x['existencia']:.{d}f} {u}", True), x["usuario"]])
        self.tabla.poner_filas(filas)
