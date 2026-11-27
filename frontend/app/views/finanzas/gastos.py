"""FIN-02 · Gastos operativos (flujo M, HU-26)."""
from datetime import date

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import QFileDialog

from app import formato as fmt
from app.datos import ErrorNegocio
from app.validaciones import monto_positivo
from app.views.base import Contexto, PaginaBase
from app.widgets import Campo, Card, Celda, Col, Tabla, avisar, boton, combo, entrada, hbox, rejilla, selector_fecha

CONCEPTOS = ["Sueldos", "Renta", "Luz", "Agua", "Gas", "Mantenimiento", "Transporte", "Otros"]
METODOS = ["Transferencia", "Efectivo", "Tarjeta"]


def _qd(q: QDate) -> date:
    return date(q.year(), q.month(), q.day())


class GastosView(PaginaBase):
    def __init__(self, ctx: Contexto):
        super().__init__(ctx, "Finanzas", "Gastos operativos", estado="")
        hoy = date(2026, 11, 2) if ctx.datos.es_demo else date.today()
        self.comprobante: str | None = None

        self.concepto = combo(CONCEPTOS)
        self.detalle = entrada(max_len=120, placeholder="Ej. Bimestre sep-oct")
        self.monto = entrada(placeholder="$0.00")
        self.campo_monto = Campo("Monto *", self.monto)
        self.fecha = selector_fecha(hoy)
        self.metodo = combo(METODOS)
        self.btn_comp = boton("Adjuntar PDF o foto", "secundario", self._adjuntar)
        self.form = Card("Registrar gasto").agregar(
            rejilla([[Campo("Concepto *", self.concepto), self.campo_monto, Campo("Fecha *", self.fecha),
                      Campo("Método de pago *", self.metodo), Campo("Comprobante", self.btn_comp)],
                     [(Campo("Detalle", self.detalle), 5)]]),
            hbox(boton("Guardar gasto", "primario", self._guardar), boton("Cancelar", "texto", self._limpiar), "stretch"))
        self.form.setVisible(ctx.sesion.puede("finanzas", "crear"))
        self.agregar(self.form)

        self.f_concepto = combo(["Todos"] + CONCEPTOS)
        self.desde = selector_fecha(hoy.replace(day=1, month=max(1, hoy.month - 1)))
        self.hasta = selector_fecha(hoy)
        self.tabla = Tabla([Col("Fecha"), Col("Concepto"), Col("Detalle", estirar=True), Col("Método"), Col("Monto", "der"),
                            Col("Comprobante"), Col("Registró")])
        self.agregar(Card().agregar(
            hbox(Campo("Concepto", self.f_concepto), Campo("Desde", self.desde), Campo("Hasta", self.hasta),
                 boton("Filtrar", "secundario", self._cargar), alinear=Qt.AlignmentFlag.AlignBottom),
            self.tabla))
        self.terminar()
        self._cargar()

    def _cargar(self) -> None:
        r = self.intentar(self.ctx.datos.lista_gastos, self.f_concepto.currentText(), _qd(self.desde.date()),
                          _qd(self.hasta.date()))
        if not r:
            return
        self.poner_estado(f"{fmt.mes_anio(_qd(self.desde.date()))} · {fmt.dinero(r['total'])}")
        ver = lambda: avisar(self, "Comprobante", "Los comprobantes se guardan en el servidor (ruta /finanzas/gastos).")  # noqa: E731
        self.tabla.poner_filas(
            [[fmt.fecha(g["fecha"]), g["concepto"], g["detalle"], g["metodo"], fmt.dinero(g["monto"]),
              boton("Ver", "link", ver) if g["comprobante"] else "—", g["usuario"]] for g in r["filas"]],
            total=["", Celda("Total", True), "", "", Celda(fmt.dinero(r["total"]), True), "", ""])

    def _adjuntar(self) -> None:
        ruta, _ = QFileDialog.getOpenFileName(self, "Comprobante", "", "PDF o imagen (*.pdf *.png *.jpg *.jpeg)")
        if ruta:
            self.comprobante = ruta
            self.btn_comp.setText("✓ " + ruta.replace("\\", "/").split("/")[-1][:18])

    def _limpiar(self) -> None:
        self.monto.clear()
        self.detalle.clear()
        self.comprobante = None
        self.btn_comp.setText("Adjuntar PDF o foto")
        self.campo_monto.error(None)

    def _guardar(self) -> None:
        monto, error = monto_positivo(self.monto.text())
        if self.campo_monto.error(error):
            return
        datos = dict(fecha=_qd(self.fecha.date()), concepto=self.concepto.currentText(), detalle=self.detalle.text().strip(),
                     metodo=self.metodo.currentText(), monto=monto, comprobante=bool(self.comprobante))
        try:
            self.intentar(self.ctx.datos.registrar_gasto, datos, mostrar_dialogo=False)
        except ErrorNegocio as exc:
            self.campo_monto.error(exc.mensaje)
            return
        if self.aviso.isVisible():
            return
        self._limpiar()
        self._cargar()
