"""FIN-06 · Estado de cuenta del cliente de crédito (HU-38b)."""
from datetime import date

from PySide6.QtCore import QDate, Qt

from app import formato as fmt
from app.theme import C
from app.views.base import Contexto, PaginaBase
from app.widgets import Badge, Campo, Card, Celda, Col, Kpi, Tabla, boton, etiqueta, fila_kpis, hbox, selector_fecha


def _qd(q: QDate) -> date:
    return date(q.year(), q.month(), q.day())


class EstadoCuentaClienteView(PaginaBase):
    def __init__(self, ctx: Contexto):
        super().__init__(ctx, f'<a href="fin.clientes" style="color:{C.GUINDA}">Clientes de crédito</a> › Estado de cuenta',
                         "Estado de cuenta",
                         acciones=[boton("Exportar PDF", "secundario", lambda: self._exportar()),
                                   boton("Imprimir para el cliente", "secundario", lambda: self._exportar())])
        if ctx.datos.es_demo:
            self.lbl_estado.setVisible(False)
            self.punto.setVisible(False)
        self.id_cliente = None
        hoy = date(2026, 11, 2) if ctx.datos.es_demo else date.today()
        self.hoy = hoy
        self.desde = selector_fecha(hoy.replace(day=1, month=max(1, hoy.month - 1)))
        self.hasta = selector_fecha(hoy)
        self.info = hbox(espacio=22)
        self.agregar(Card(margen=18).agregar(hbox(self.info, "stretch", Campo("Desde", self.desde), Campo("Hasta", self.hasta),
                                                  boton("Consultar", "secundario", self._cargar),
                                                  alinear=Qt.AlignmentFlag.AlignBottom)))
        self.k_limite = Kpi("Límite de crédito", "—")
        self.k_compras = Kpi("Compras a crédito", "—")
        self.k_pagos = Kpi("Pagos", "—")
        self.k_saldo = Kpi("Saldo", "—", color=C.GUINDA)
        self.agregar(fila_kpis(self.k_limite, self.k_compras, self.k_pagos, self.k_saldo))
        self.tabla = Tabla([Col("Fecha"), Col("Movimiento", estirar=True), Col("Referencia"), Col("Cargo", "der"),
                            Col("Abono", "der"), Col("Saldo", "der")])
        self.agregar(Card("Movimientos").agregar(self.tabla))
        self.terminar()

    def al_mostrar(self, id_cliente=None, **_):
        self.id_cliente = int(id_cliente) if id_cliente else None
        self._cargar()

    def _cargar(self) -> None:
        if not self.id_cliente:
            return
        d, h = _qd(self.desde.date()), _qd(self.hasta.date())
        e = self.intentar(self.ctx.datos.estado_cuenta_cliente, self.id_cliente, d, h)
        if not e:
            return
        c = e["cliente"]
        self.lbl_titulo.setText(c["nombre"])
        while self.info.count():
            w = self.info.takeAt(0).widget()
            if w:
                w.deleteLater()
        self.info.addWidget(etiqueta(c["telefono"], "Muted"))
        self.info.addWidget(etiqueta(f"Crédito {c['dias']} días", "Muted"))
        self.info.addWidget(Badge(e["estatus"], {"Activo": "verde", "Pago vencido": "rojo"}.get(e["estatus"], "gris")))
        self.k_limite.poner(fmt.dinero(c["limite"]), f"Disponible {fmt.dinero(e['disponible'])}")
        self.k_compras.poner(fmt.dinero(e["compras"]), f"{e['n_compras']} tickets en el periodo")
        self.k_pagos.poner(fmt.dinero(e["pagos"]), f"{e['n_pagos']} cobros")
        self.k_saldo.poner(fmt.dinero(e["saldo"]), f"Vence el {fmt.fecha_corta(e['vence'])}" if e["vence"] else "Sin saldo pendiente")
        filas = [[fmt.fecha(d), "Saldo inicial", "", "", "", fmt.dinero(e["inicial"])]]
        for m in e["movimientos"]:
            filas.append([fmt.fecha(m["fecha"]), m["movimiento"], m["referencia"],
                          fmt.dinero(m["cargo"]) if m["cargo"] else "", fmt.dinero(m["abono"]) if m["abono"] else "",
                          fmt.dinero(m["saldo"])])
        self.tabla.poner_filas(filas, total=["", Celda(f"Saldo al {fmt.fecha_corta(h)}", True), "",
                                             Celda(fmt.dinero(e["compras"]), True), Celda(fmt.dinero(e["pagos"]), True),
                                             Celda(fmt.dinero(e["saldo"]), True)])

    def _exportar(self) -> None:
        from app.exportar import exportar_tabla
        exportar_tabla(self, self.tabla, f"Estado de cuenta {self.lbl_titulo.text()}",
                       f"{fmt.fecha(_qd(self.desde.date()))} al {fmt.fecha(_qd(self.hasta.date()))}")
