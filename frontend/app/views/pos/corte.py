"""POS-03 · Corte de caja con arqueo (flujo D, HU-09)."""
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QHBoxLayout

from app import formato as fmt
from app.datos import ErrorNegocio
from app.presenters.pos import diferencia_arqueo, error_corte, texto_diferencia
from app.theme import C
from app.views.base import Contexto, PaginaBase
from app.widgets import (
    Campo, Card, Celda, Col, Tabla, area_texto, avisar, boton, columnas, confirmar, entrada, etiqueta, hbox, texto,
)


class CorteView(PaginaBase):
    def __init__(self, ctx: Contexto):
        super().__init__(ctx, "Punto de Venta", "Corte de caja", estado="")
        self.resumen = self.intentar(ctx.datos.resumen_corte)
        if self.resumen is None:
            if not self.aviso.isVisible():
                self.aviso.mostrar("No hay una caja abierta en esta terminal.", "naranja")
            self.terminar()
            return
        r = self.resumen
        self.lbl_migas.setText(f"Punto de Venta · {r['caja']}")
        self.poner_estado(f"Turno abierto desde las {r['desde'].hour}:{r['desde'].minute:02d} · {r['tickets']} tickets")

        tabla = Tabla([Col("Concepto", estirar=True), Col("Tickets", "der", ancho=90), Col("Importe", "der", ancho=130)])
        filas = []
        for f in r["filas"]:
            imp = Celda(fmt.dinero(f["importe"]), color=C.ROJO if f["importe"] < 0 else None)
            filas.append([f["concepto"], "" if f["tickets"] is None else str(f["tickets"]), imp])
        tabla.poner_filas(filas, total=[Celda("Efectivo esperado en caja", True), "", Celda(fmt.dinero(r["esperado"]), True)])
        izq = Card("Resumen del turno").agregar(
            tabla,
            etiqueta("Efectivo esperado = fondo inicial + ventas y cobros en efectivo − devoluciones en efectivo. "
                     "Tarjeta, transferencia y crédito no entran al cajón.", "Muted", ajustar=True))

        self.contado = entrada(placeholder="$0.00")
        self.contado.setAccessibleName("Efectivo contado")
        self.contado.textChanged.connect(self._recalcular)
        self.campo_contado = Campo("Efectivo contado", self.contado)
        self.caja_dif = QFrame()
        lay = QHBoxLayout(self.caja_dif)
        lay.setContentsMargins(16, 14, 16, 14)
        self.lbl_dif = texto("Sin diferencia", 15, QFont.Weight.ExtraBold)
        self.val_dif = texto("$0.00", 28, QFont.Weight.DemiBold, titulo=True)
        lay.addWidget(self.lbl_dif)
        lay.addStretch(1)
        lay.addWidget(self.val_dif)
        self.obs = area_texto("")
        self.obs.setPlaceholderText("Explica la diferencia (por ejemplo, cambio mal entregado en un ticket).")
        self.obs.textChanged.connect(lambda: self.campo_obs.error(None))
        self.campo_obs = Campo("Observaciones (obligatorias si hay diferencia)", self.obs)
        self.error = etiqueta("", "Error", ajustar=True)
        self.error.setVisible(False)
        der = Card("Arqueo").agregar(
            self.campo_contado, self.caja_dif, self.campo_obs, self.error,
            hbox(boton("Cerrar caja e imprimir", "primario", self._cerrar),
                 boton("Volver al cobro", "texto", lambda: ctx.navegar("pos.cobro")), "stretch"),
            etiqueta("No se puede cerrar con una venta en proceso. El corte queda en la bitácora de auditoría.",
                     "Muted", ajustar=True))
        self.agregar(columnas(izq, der))
        self.terminar()
        self._recalcular()

    def _recalcular(self, *_):
        contado = fmt.leer_dinero(self.contado.text())
        if contado is None:
            self.caja_dif.setStyleSheet(f"background: {C.CREMA}; border-radius: 10px;")
            self.lbl_dif.setText("Captura el efectivo contado")
            self.lbl_dif.setStyleSheet(f"color: {C.TEXTO_SUAVE};")
            self.val_dif.setText("—")
            self.val_dif.setStyleSheet(f"color: {C.TEXTO_SUAVE};")
            return
        dif = diferencia_arqueo(contado, self.resumen["esperado"])
        fondo, color = (C.ROJO_SUAVE, C.ROJO) if dif < 0 else (C.NARANJA_SUAVE, C.NARANJA_TEXTO) if dif > 0 else (C.VERDE_SUAVE, C.VERDE_TEXTO)
        self.caja_dif.setStyleSheet(f"background: {fondo}; border-radius: 10px;")
        self.lbl_dif.setText(texto_diferencia(dif))
        self.lbl_dif.setStyleSheet(f"color: {color};")
        self.val_dif.setText(fmt.dinero(dif))
        self.val_dif.setStyleSheet(f"color: {color};")

    def _venta_en_proceso(self) -> bool:
        cobro = self.ctx.pagina("pos.cobro")
        return cobro is not None and not cobro.carrito.vacio

    def _cerrar(self) -> None:
        contado = fmt.leer_dinero(self.contado.text())
        campo, msg = error_corte(contado, self.resumen["esperado"], self.obs.toPlainText(), self._venta_en_proceso())
        self.error.setVisible(False)
        if campo == "contado":
            self.campo_contado.error(msg)
            return
        if campo == "observaciones":
            self.campo_obs.error(msg)
            return
        if campo == "general":
            self.error.setText(msg)
            self.error.setVisible(True)
            return
        if not confirmar(self, "Cerrar caja", f"Se cerrará {self.resumen['caja']} con {fmt.dinero(contado)} contados. "
                         "Después no se podrá vender hasta abrir otro turno.", "Cerrar caja"):
            return
        try:
            r = self.intentar(self.ctx.datos.cerrar_caja, contado, self.obs.toPlainText().strip(), mostrar_dialogo=False)
        except ErrorNegocio as exc:
            if exc.campo == "observaciones":
                self.campo_obs.error(exc.mensaje)
            else:
                avisar(self, "Corte de caja", exc.mensaje, error=True)
            return
        if r is None:
            return
        avisar(self, "Caja cerrada", f"Corte registrado. Diferencia: {fmt.dinero(r['diferencia'])}.\n"
               "El comprobante se envió a la impresora (simulador).")
        self.ctx.olvidar("pos.cobro")
        self.ctx.actualizar_caja()
        self.ctx.navegar("pos.apertura")
