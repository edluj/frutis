"""PRV-06 · Estado de cuenta por proveedor (reporte 8)."""
from datetime import date

from PySide6.QtCore import QDate, Qt

from app import formato as fmt
from app.theme import C
from app.views.base import Contexto, PaginaBase
from app.widgets import Card, Campo, Celda, Col, Kpi, Tabla, boton, etiqueta, fila_kpis, hbox, selector_fecha


def _qd(q: QDate) -> date:
    return date(q.year(), q.month(), q.day())


class EstadoCuentaProveedorView(PaginaBase):
    def __init__(self, ctx: Contexto):
        super().__init__(ctx, f'<a href="compras.proveedores" style="color:{C.GUINDA}">Proveedores</a> › Estado de cuenta',
                         "Estado de cuenta",
                         acciones=[boton("Exportar PDF", "secundario", lambda: self._exportar())])
        self.id_proveedor = None
        hoy = date(2026, 11, 2) if ctx.datos.es_demo else date.today()
        self.desde = selector_fecha(hoy.replace(day=1, month=max(1, hoy.month - 1)))
        self.hasta = selector_fecha(hoy)
        self.info = hbox(espacio=26)
        self.agregar(Card(margen=18).agregar(hbox(self.info, "stretch", Campo("Desde", self.desde), Campo("Hasta", self.hasta),
                                                  boton("Consultar", "secundario", self._cargar),
                                                  alinear=Qt.AlignmentFlag.AlignBottom)))
        self.k_compras = Kpi("Compras del periodo", "—")
        self.k_pagos = Kpi("Pagos del periodo", "—")
        self.k_saldo = Kpi("Saldo", "—", color=C.GUINDA)
        self.agregar(fila_kpis(self.k_compras, self.k_pagos, self.k_saldo))
        self.tabla = Tabla([Col("Fecha"), Col("Movimiento", estirar=True), Col("Referencia"), Col("Cargo", "der"),
                            Col("Abono", "der"), Col("Saldo", "der")])
        self.agregar(Card("Movimientos").agregar(self.tabla))
        self.terminar()

    def al_mostrar(self, id_proveedor=None, **_):
        self.id_proveedor = int(id_proveedor) if id_proveedor else None
        self._cargar()

    def _cargar(self) -> None:
        if not self.id_proveedor:
            return
        d, h = _qd(self.desde.date()), _qd(self.hasta.date())
        e = self.intentar(self.ctx.datos.estado_cuenta_proveedor, self.id_proveedor, d, h)
        if not e:
            return
        p = e["proveedor"]
        self.lbl_titulo.setText(p["razon_social"])
        while self.info.count():
            w = self.info.takeAt(0).widget()
            if w:
                w.deleteLater()
        for t in (f"RFC {p['rfc']}", p["telefono"], "Contado" if not p["dias_credito"] else f"Crédito {p['dias_credito']} días"):
            self.info.addWidget(etiqueta(t, "Muted"))
        self.k_compras.poner(fmt.dinero(e["compras"]), f"{e['n_compras']} lotes")
        self.k_pagos.poner(fmt.dinero(e["pagos"]), f"{e['n_pagos']} pago{'s' if e['n_pagos'] != 1 else ''}")
        self.k_saldo.poner(fmt.dinero(e["saldo"]), f"{fmt.dinero(e['vencido'])} vencido" if e["vencido"] else "Sin saldo vencido")
        filas = [[fmt.fecha(d), "Saldo inicial", "", "", "", fmt.dinero(e["inicial"])]]
        for m in e["movimientos"]:
            filas.append([fmt.fecha(m["fecha"]), m["movimiento"], m["referencia"],
                          fmt.dinero(m["cargo"]) if m["cargo"] else "", fmt.dinero(m["abono"]) if m["abono"] else "",
                          fmt.dinero(m["saldo"])])
        self.tabla.poner_filas(filas, total=["", Celda("Saldo final", True), "", Celda(fmt.dinero(e["compras"]), True),
                                             Celda(fmt.dinero(e["pagos"]), True), Celda(fmt.dinero(e["saldo"]), True)])

    def _exportar(self) -> None:
        from app.exportar import exportar_tabla
        exportar_tabla(self, self.tabla, f"Estado de cuenta {self.lbl_titulo.text()}",
                       f"{fmt.fecha(_qd(self.desde.date()))} al {fmt.fecha(_qd(self.hasta.date()))}")
