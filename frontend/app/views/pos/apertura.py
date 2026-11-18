"""POS-01 · Apertura de caja (flujo D, HU-15)."""
from decimal import Decimal

from PySide6.QtWidgets import QSpinBox

from app import formato as fmt
from app.presenters.pos import DENOMINACIONES, fondo_inicial
from app.theme import C
from app.views.base import Contexto, PaginaBase
from app.widgets import (
    Alerta, Campo, Card, Celda, Col, Tabla, boton, columnas, combo, dato, entrada, etiqueta, hbox, rejilla,
)


class AperturaView(PaginaBase):
    def __init__(self, ctx: Contexto):
        super().__init__(ctx, "Punto de Venta", "Apertura de caja",
                         estado=f"{ctx.datos.estado_conexion()} · Terminal {ctx.config.terminal}",
                         punto=C.NARANJA if ctx.datos.es_demo else C.VERDE)
        self.agregar(Alerta("<b>Caja cerrada.</b>&nbsp;&nbsp; Para empezar a vender, registra el fondo inicial "
                            "con el que abres el turno.", "naranja"))

        cajas = self.intentar(ctx.datos.cajas_disponibles) or []
        self.caja = combo([(c["nombre"], c["id_caja"]) for c in cajas])
        cajero = entrada(ctx.sesion.nombre_completo)
        cajero.setReadOnly(True)

        self.piezas: dict[str, QSpinBox] = {}
        filas = []
        for nombre, valor in DENOMINACIONES:
            sb = QSpinBox()
            sb.setRange(0, 999)
            sb.setFixedWidth(84)
            sb.setAccessibleName(f"Piezas de {nombre}")
            sb.valueChanged.connect(self._recalcular)
            self.piezas[nombre] = sb
            filas.append([nombre, sb, "$0.00"])
        self.morralla = entrada(placeholder="$0.00", alinear_derecha=True, compacto=True)
        self.morralla.setFixedWidth(110)
        self.morralla.setAccessibleName("Monedas de $5 y menores")
        self.morralla.textChanged.connect(self._recalcular)
        filas.append(["Monedas de $5 y menores", "—", self.morralla])
        self.tabla = Tabla([Col("Denominación", estirar=True), Col("Piezas", "der", ancho=120), Col("Importe", "der", ancho=140)])
        self.tabla.poner_filas(filas, total=[Celda("Fondo inicial", True), "", Celda("$0.00", True)])
        self.error = etiqueta("", "Error")
        self.error.setVisible(False)

        self.btn_abrir = boton("Abrir caja", "primario", self._abrir)
        self.btn_abrir.setMinimumHeight(52)
        self.btn_abrir.setStyleSheet("font-size: 16px;")
        izq = Card("Fondo inicial").agregar(
            rejilla([[Campo("Caja", self.caja), Campo("Cajero", cajero)]]),
            self.tabla, self.error,
            hbox(self.btn_abrir, boton("Cancelar", "texto", lambda: ctx.navegar("inicio")), "stretch"),
        )

        der = Card("Último corte de esta caja")
        corte = self.intentar(ctx.datos.datos_ultimo_corte, self.caja.currentData() or 1)
        if corte:
            dif = corte["contado"] - corte["esperado"]
            der.agregar(rejilla([
                [dato("Fecha", fmt.fecha_hora(corte["fecha"])), dato("Cajero", corte["cajero"])],
                [dato("Efectivo esperado", fmt.dinero(corte["esperado"])), dato("Efectivo contado", fmt.dinero(corte["contado"]))],
                [dato("Diferencia", fmt.dinero(dif), C.ROJO if dif < 0 else C.VERDE_TEXTO if dif > 0 else None, negrita=True),
                 dato("Observaciones", corte["observaciones"])],
            ]))
        der.agregar(etiqueta("Solo puede haber una caja abierta por terminal. La apertura queda en la bitácora de "
                             "auditoría.", "Muted", ajustar=True))
        self.agregar(columnas(izq, der))
        self.terminar()
        self._recalcular()

    def _fondo(self) -> Decimal | None:
        texto = self.morralla.text().strip()
        morralla = fmt.leer_dinero(texto) if texto else Decimal("0")
        if morralla is None or morralla < 0:
            return None
        return fondo_inicial({n: sb.value() for n, sb in self.piezas.items()}, morralla)

    def _recalcular(self, *_):
        valores = dict(DENOMINACIONES)
        for r, (nombre, sb) in enumerate(self.piezas.items()):
            item = self.tabla.item(r, 2)
            item.setText(fmt.dinero(valores[nombre] * sb.value()))
        total = self._fondo()
        self.tabla.item(self.tabla.rowCount() - 1, 2).setText(fmt.dinero(total) if total is not None else "—")
        self.morralla.setProperty("error", total is None)
        self.morralla.style().polish(self.morralla)

    def _abrir(self) -> None:
        fondo = self._fondo()
        if fondo is None:
            self.error.setText("Ingrese un importe válido en monedas.")
            self.error.setVisible(True)
            return
        self.error.setVisible(False)
        caja = self.intentar(self.ctx.datos.abrir_caja, self.caja.currentData(), fondo)
        if caja:
            self.ctx.actualizar_caja()
            self.ctx.navegar("pos.cobro")
