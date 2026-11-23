"""REP-01 · Reportes operativos y financieros (flujo S, HU-28 y HU-29)."""
from datetime import date

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import QButtonGroup, QLabel, QPushButton, QVBoxLayout

from app.datos.reportes_demo import NOMBRES
from app.theme import C
from app.views.base import Contexto, PaginaBase
from app.widgets import (
    Barra, Campo, Card, Celda, Col, Tabla, boton, columnas, combo, hbox, limpiar, selector_fecha, texto, vbox, vacio,
)
from PySide6.QtGui import QFont

def _qd(q: QDate) -> date:
    return date(q.year(), q.month(), q.day())


class ReportesView(PaginaBase):
    def __init__(self, ctx: Contexto):
        super().__init__(ctx, "Reportes", "Reportes", estado=ctx.datos.estado_conexion(),
                         punto=C.NARANJA if ctx.datos.es_demo else C.VERDE)
        self.numero = 7
        self.reporte: dict | None = None
        menu = Card("Reportes", margen=16, espacio=2)
        menu.setFixedWidth(250)
        self.grupo = QButtonGroup(self)
        self.botones = {}
        for i, nombre in enumerate(NOMBRES, start=1):
            b = QPushButton()
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setAccessibleName(nombre)
            b.setStyleSheet(
                "QPushButton { background: transparent; border: none; border-radius: 8px; }"
                f"QPushButton:hover {{ background: {C.FONDO}; }}"
                f"QPushButton:checked {{ background: {C.GUINDA_SUAVE}; }}")
            lbl = QLabel(f"{i}. {nombre}")
            lbl.setWordWrap(True)
            lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            lay = QVBoxLayout(b)
            lay.setContentsMargins(10, 7, 10, 7)
            lay.addWidget(lbl)
            b.setMinimumHeight(lbl.sizeHint().height() + 14)
            b.toggled.connect(lambda on, l=lbl: l.setStyleSheet(
                f"color: {C.GUINDA}; font-weight: 800; background: transparent;" if on else "background: transparent;"))
            b.clicked.connect(lambda _=False, n=i: self._elegir(n))
            self.grupo.addButton(b)
            self.botones[i] = b
            menu.agregar(b)

        hoy = date(2026, 11, 2) if ctx.datos.es_demo else date.today()
        self.desde = selector_fecha(date(hoy.year, max(1, hoy.month - 1), 1))
        self.hasta = selector_fecha(date(2026, 10, 31) if ctx.datos.es_demo else hoy)
        self.cajero = combo(["Todos"] + (self.intentar(ctx.datos.cajeros) or []))
        filtros = Card(margen=18).agregar(hbox(Campo("Desde", self.desde), Campo("Hasta", self.hasta),
                                               Campo("Cajero", self.cajero), boton("Generar", "primario", self._generar),
                                               alinear=Qt.AlignmentFlag.AlignBottom))
        self.btn_pdf = boton("Exportar PDF", "secundario", lambda: self._exportar("pdf"))
        self.btn_xlsx = boton("Exportar Excel", "secundario", lambda: self._exportar("xlsx"))
        self.resultado = Card(derecha=[self.btn_pdf, self.btn_xlsx])
        self.barras = vbox(espacio=10)
        self.tabla = Tabla([Col("")])
        self.sin_datos = vacio()
        self.resultado.agregar(self.barras, self.tabla, self.sin_datos)
        self.agregar(columnas(menu, vbox(filtros, self.resultado, espacio=20), proporciones=[0, 1]))
        self.terminar()

    def al_mostrar(self, numero=None, **_):
        self._elegir(int(numero) if numero else self.numero)

    def _elegir(self, n: int) -> None:
        self.numero = n
        self.botones[n].setChecked(True)
        self.lbl_titulo.setText(NOMBRES[n - 1])
        self._generar()

    def _generar(self) -> None:
        r = self.intentar(self.ctx.datos.reporte, self.numero, _qd(self.desde.date()), _qd(self.hasta.date()),
                          self.cajero.currentText())
        limpiar(self.barras)
        if not r:
            return
        self.reporte = r
        hay = bool(r["filas"])
        self.resultado.titulo_lbl.setText(r["titulo"] if hay else NOMBRES[self.numero - 1])
        for w in (self.btn_pdf, self.btn_xlsx, self.tabla):
            w.setVisible(hay)
        self.sin_datos.setVisible(not hay)
        if not hay:
            return
        for nombre, frac, txt, color in r["barras"]:
            fila = hbox(espacio=14)
            n = texto(nombre, 14, QFont.Weight.ExtraBold)
            n.setFixedWidth(120)
            v = texto(txt, 14, QFont.Weight.ExtraBold)
            v.setFixedWidth(110)
            v.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            fila.addWidget(n)
            fila.addWidget(Barra(frac, color, alto=22, ancho_min=160), 1)
            fila.addWidget(v)
            self.barras.addLayout(fila)
        # La tabla se rehace con las columnas del reporte elegido.
        nueva = Tabla([Col(t, a, estirar=(i == 0)) for i, (t, a) in enumerate(r["columnas"])])
        total = [Celda(c, True) for c in r["total"]] if r["total"] else None
        nueva.poner_filas(r["filas"], total=total)
        self.resultado.lay.replaceWidget(self.tabla, nueva)
        self.tabla.hide()
        self.tabla.deleteLater()
        self.tabla = nueva

    def _exportar(self, formato: str) -> None:
        from app import formato as fmt
        from app.exportar import exportar_tabla
        sub = f"{fmt.fecha(_qd(self.desde.date()))} al {fmt.fecha(_qd(self.hasta.date()))} · cajero: {self.cajero.currentText()}"
        exportar_tabla(self, self.tabla, f"{self.numero}. {NOMBRES[self.numero - 1]}", sub, formato)
