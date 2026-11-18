"""FAC-03 · Facturas emitidas: consulta y cancelación (flujo J, HU-33)."""
from datetime import date

from PySide6.QtCore import QDate, Qt

from app import catalogos_sat as sat
from app import formato as fmt
from app.datos import ErrorNegocio
from app.views.base import Contexto, PaginaBase
from app.widgets import (
    Alerta, Badge, Campo, Card, Celda, Col, Tabla, avisar, boton, combo, confirmar, entrada, etiqueta, hbox,
    selector_fecha,
)


def _qd(q: QDate) -> date:
    return date(q.year(), q.month(), q.day())


class FacturasEmitidasView(PaginaBase):
    def __init__(self, ctx: Contexto):
        acciones = [boton("+ Generar factura", "primario", lambda: ctx.navegar("fac.generar"))] \
            if ctx.sesion.puede("facturacion", "crear") else []
        super().__init__(ctx, "Facturación", "Facturas emitidas", acciones=acciones)
        self.seleccion: dict | None = None
        hoy = date(2026, 11, 2) if ctx.datos.es_demo else date.today()
        self.texto = entrada(placeholder="F-0012 o RSO100518KJ3", max_len=13)
        self.texto.returnPressed.connect(self._cargar)
        self.desde = selector_fecha(hoy.replace(day=1, month=max(1, hoy.month - 1)))
        self.hasta = selector_fecha(hoy)
        self.estatus = combo(["Todas", "Vigentes", "Canceladas"])
        self.tabla = Tabla([Col("Folio"), Col("Fecha"), Col("Cliente", estirar=True), Col("UUID"), Col("Total", "der"),
                            Col("Estatus"), Col("Archivos"), Col("", "centro", ancho=140)])
        self.agregar(Card().agregar(
            hbox((Campo("Folio o RFC", self.texto), 2), Campo("Desde", self.desde), Campo("Hasta", self.hasta),
                 Campo("Estatus", self.estatus), boton("Buscar", "secundario", self._cargar),
                 alinear=Qt.AlignmentFlag.AlignBottom),
            self.tabla))

        self.motivo = combo(sat.MOTIVOS_CANCELACION)
        self.motivo.currentIndexChanged.connect(self._motivo)
        self.sustituto = entrada(placeholder="F-0013", max_len=10)
        self.campo_sustituto = Campo("Folio que la sustituye *", self.sustituto)
        self.cancelar = Card("Cancelar factura")
        self.cancelar.agregar(
            hbox((Campo("Motivo SAT *", self.motivo), 2), (self.campo_sustituto, 1), alinear=Qt.AlignmentFlag.AlignTop),
            Alerta("La cancelación no se puede deshacer y queda en la bitácora de auditoría. El SAT puede tardar hasta "
                   "72 horas en aceptarla.", "naranja"),
            hbox(boton("Confirmar cancelación", "peligro", self._confirmar), boton("Volver", "texto", self._cerrar), "stretch"))
        self.cancelar.setVisible(False)
        self.cancelar.setMaximumWidth(790)
        self.agregar(self.cancelar)
        self.terminar()
        self._cargar()

    def _cargar(self) -> None:
        filas = self.intentar(self.ctx.datos.lista_facturas, self.texto.text().strip(), _qd(self.desde.date()),
                              _qd(self.hasta.date()), self.estatus.currentText()) or []
        puede = self.ctx.sesion.puede("facturacion", "editar")
        aviso = lambda m: lambda: avisar(self, "Archivos", m)  # noqa: E731
        tonos = {}
        salida = []
        for i, f in enumerate(filas):
            seleccionada = self.seleccion and self.seleccion["folio"] == f["folio"]
            if seleccionada:
                tonos[i] = "guinda"
            accion = (etiqueta("Seleccionada", "Error") if seleccionada else
                      boton("Cancelar", "texto", lambda f=f: self._elegir(f)) if puede and f["estatus"] == "Vigente" else "")
            salida.append([
                Celda(f["folio"], True), fmt.fecha(f["fecha"]), f["cliente"], f"{f['uuid'][:8]}…{f['uuid'][-4:]}",
                fmt.dinero(f["total"]), Badge(f["estatus"], "verde" if f["estatus"] == "Vigente" else "rojo"),
                hbox(boton("PDF", "link", aviso("El PDF lo entrega el PAC desde el servidor.")),
                     etiqueta("·", "Muted"), boton("XML", "link", aviso("El XML lo entrega el PAC desde el servidor.")), espacio=0),
                accion])
        self.tabla.poner_filas(salida, datos=filas, tonos=tonos)

    def _elegir(self, f: dict) -> None:
        self.seleccion = f
        self.cancelar.titulo_lbl.setText(f"Cancelar factura {f['folio']}")
        self.sustituto.clear()
        self.campo_sustituto.error(None)
        self.cancelar.setVisible(True)
        self._cargar()

    def _motivo(self, *_):
        requiere = self.motivo.currentData() == "01"
        self.campo_sustituto.lbl.setText("Folio que la sustituye *" if requiere else "Folio que la sustituye")
        self.sustituto.setEnabled(requiere)

    def _cerrar(self) -> None:
        self.seleccion = None
        self.cancelar.setVisible(False)
        self._cargar()

    def _confirmar(self) -> None:
        f = self.seleccion
        if self.motivo.currentData() == "01" and not self.sustituto.text().strip():
            self.campo_sustituto.error("El motivo 01 requiere el folio que la sustituye.")
            return
        if not confirmar(self, "Cancelar factura", f"¿Cancelar la factura {f['folio']} por {fmt.dinero(f['total'])}? "
                         "No se puede deshacer.", "Sí, cancelar", peligro=True):
            return
        try:
            self.intentar(self.ctx.datos.cancelar_factura, f["folio"], self.motivo.currentText(),
                          self.sustituto.text().strip().upper(), mostrar_dialogo=False)
        except ErrorNegocio as exc:
            self.campo_sustituto.error(exc.mensaje)
            return
        if self.aviso.isVisible():
            return
        self._cerrar()
        avisar(self, "Cancelación enviada", f"La solicitud de cancelación de {f['folio']} se envió al SAT.")
