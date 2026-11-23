"""ADM-03 · Bitácora de auditoría, solo lectura (flujo V, HU-35)."""
from datetime import date, timedelta

from PySide6.QtCore import QDate

from app import formato as fmt
from app.views.base import Contexto, PaginaBase
from app.widgets import Badge, Campo, Card, Col, Tabla, boton, combo, etiqueta, hbox, rejilla, selector_fecha

POR_PAGINA = 10


def _qd(q: QDate) -> date:
    return date(q.year(), q.month(), q.day())


class AuditoriaView(PaginaBase):
    def __init__(self, ctx: Contexto):
        super().__init__(ctx, "Administración", "Auditoría", acciones=[Badge("Solo lectura", "gris")])
        if ctx.datos.es_demo:
            self.lbl_estado.setVisible(False)
            self.punto.setVisible(False)
        self.pagina = 0
        self.filas: list[dict] = []
        todas = self.intentar(ctx.datos.lista_auditoria) or []
        hoy = date(2026, 11, 2) if ctx.datos.es_demo else date.today()
        self.usuario = combo(["Todos"] + sorted({a["usuario"] for a in todas}))
        self.modulo = combo(["Todos"] + sorted({a["modulo"] for a in todas}))
        self.accion = combo(["Todas"] + sorted({a["accion"] for a in todas}))
        self.desde = selector_fecha(hoy - timedelta(days=2))
        self.hasta = selector_fecha(hoy)
        self.tabla = Tabla([Col("Fecha y hora"), Col("Usuario"), Col("Módulo"), Col("Acción"), Col("Detalle", estirar=True),
                            Col("IP")])
        self.contador = etiqueta("", "Muted")
        self.btn_ant = boton("Anterior", "texto", lambda: self._mover(-1))
        self.btn_sig = boton("Siguiente", "secundario", lambda: self._mover(1))
        self.agregar(Card().agregar(
            rejilla([[Campo("Usuario", self.usuario), Campo("Módulo", self.modulo), Campo("Acción", self.accion),
                      Campo("Desde", self.desde), Campo("Hasta", self.hasta)]]),
            hbox(boton("Buscar", "primario", self._buscar), boton("Exportar", "secundario", self._exportar), "stretch"),
            self.tabla, hbox(self.contador, "stretch", self.btn_ant, self.btn_sig)))
        self.terminar()
        self._buscar()

    def _buscar(self) -> None:
        self.filas = self.intentar(self.ctx.datos.lista_auditoria, self.usuario.currentText(), self.modulo.currentText(),
                                   self.accion.currentText(), _qd(self.desde.date()), _qd(self.hasta.date())) or []
        self.pagina = 0
        self._pintar()

    def _mover(self, delta: int) -> None:
        self.pagina += delta
        self._pintar()

    def _pintar(self) -> None:
        ini = self.pagina * POR_PAGINA
        vista = self.filas[ini:ini + POR_PAGINA]
        self.tabla.poner_filas([[fmt.fecha_hora(a["fecha"]), a["usuario"], a["modulo"], Badge(a["accion"], a["tono"]),
                                 a["detalle"], a["ip"]] for a in vista])
        self.contador.setText(f"Mostrando {len(vista)} de {len(self.filas)} registros")
        self.btn_ant.setEnabled(self.pagina > 0)
        self.btn_sig.setEnabled(ini + POR_PAGINA < len(self.filas))

    def _exportar(self) -> None:
        from app.exportar import a_xlsx
        from PySide6.QtWidgets import QFileDialog
        ruta, _ = QFileDialog.getSaveFileName(self, "Exportar bitácora", "auditoria.xlsx", "Excel (*.xlsx)")
        if ruta:
            a_xlsx(ruta, "Auditoría", ["Fecha y hora", "Usuario", "Módulo", "Acción", "Detalle", "IP"],
                   [[fmt.fecha_hora(a["fecha"]), a["usuario"], a["modulo"], a["accion"], a["detalle"], a["ip"]]
                    for a in self.filas])
