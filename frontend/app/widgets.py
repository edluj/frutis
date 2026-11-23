"""Componentes reutilizables del diseño: página, tarjetas, campos, tablas, insignias y gráficas.

Cada pantalla se arma con estas piezas para que todas se vean igual que el lienzo de
diseño sin repetir estilos.
"""
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass

from PySide6.QtCore import QDate, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLayout,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStyledItemDelegate,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.iconos import icono
from app.theme import TEXTO as TEXTO_FAMILIA
from app.theme import TITULOS, C, fuente_texto

# ---------------------------------------------------------------- utilidades


def repulir(w: QWidget) -> None:
    """Vuelve a aplicar la hoja de estilos tras cambiar una propiedad dinámica."""
    w.style().unpolish(w)
    w.style().polish(w)
    w.update()


def limpiar(layout: QLayout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.hide()
            widget.setParent(None)
            widget.deleteLater()
        elif item.layout():
            limpiar(item.layout())


def hbox(*items, espacio: int = 12, margen: int = 0, alinear=None) -> QHBoxLayout:
    lay = QHBoxLayout()
    lay.setSpacing(espacio)
    lay.setContentsMargins(margen, margen, margen, margen)
    _agregar(lay, items)
    if alinear is not None:
        lay.setAlignment(alinear)
    return lay


def vbox(*items, espacio: int = 12, margen: int = 0) -> QVBoxLayout:
    lay = QVBoxLayout()
    lay.setSpacing(espacio)
    lay.setContentsMargins(margen, margen, margen, margen)
    _agregar(lay, items)
    return lay


def _agregar(lay, items) -> None:
    for it in items:
        if it is None:
            continue
        if it == "stretch":
            lay.addStretch(1)
        elif isinstance(it, tuple):  # (widget, stretch)
            w, s = it
            (lay.addLayout(w, s) if isinstance(w, QLayout) else lay.addWidget(w, s))
        elif isinstance(it, QLayout):
            lay.addLayout(it)
        else:
            lay.addWidget(it)


def envolver(layout: QLayout) -> QWidget:
    w = QWidget()
    w.setLayout(layout)
    w.setStyleSheet("background: transparent;")
    return w


def etiqueta(texto: str, nombre: str = "", rico: bool = False, ajustar: bool = False) -> QLabel:
    lbl = QLabel(texto)
    if nombre:
        lbl.setObjectName(nombre)
    if rico:
        lbl.setTextFormat(Qt.TextFormat.RichText)
    if ajustar:
        lbl.setWordWrap(True)
    return lbl


def estilo_fuente(px: int, peso: QFont.Weight = QFont.Weight.Normal, color: str | None = None,
                  titulo: bool = False) -> str:
    """Hoja de estilos de una fuente. Se usa en lugar de setFont porque la regla global
    `* { font-family }` de la hoja de estilos tiene prioridad sobre setFont."""
    familia = TITULOS if titulo else TEXTO_FAMILIA
    css = f"font-family: '{familia}'; font-size: {px}px; font-weight: {peso.value}; background: transparent;"
    return css + (f" color: {color};" if color else "")


def texto(texto_: str, px: int = 14, peso: QFont.Weight = QFont.Weight.Normal,
          color: str | None = None, titulo: bool = False, ajustar: bool = False) -> QLabel:
    lbl = QLabel(texto_)
    lbl.setStyleSheet(estilo_fuente(px, peso, color, titulo))
    lbl.setWordWrap(ajustar)
    return lbl


# ---------------------------------------------------------------- botones


def ancho_texto(texto_: str, px: int = 14, peso: QFont.Weight = QFont.Weight.Bold) -> int:
    """Ancho real del texto con la fuente del diseño (las hojas de estilo no siempre lo reportan)."""
    return QFontMetrics(fuente_texto(px, peso)).horizontalAdvance(texto_)


_RELLENO_BOTON = {"link": 14, "texto": 40, "opcion": 24}


def boton(etiqueta_: str, tipo: str = "primario", al_click: Callable | None = None,
          icono_: str | None = None, ancho: int | None = None) -> QPushButton:
    b = QPushButton(etiqueta_)
    b.setProperty("tipo", tipo)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    if icono_:
        color = "white" if tipo in ("primario", "peligro") else C.GUINDA
        b.setIcon(icono(icono_, color, 18))
    if al_click:
        b.clicked.connect(lambda *_: al_click())
    if ancho:
        b.setFixedWidth(ancho)
    elif etiqueta_:
        extra = 24 if icono_ else 0
        b.setMinimumWidth(ancho_texto(etiqueta_, 14, QFont.Weight.Bold) + _RELLENO_BOTON.get(tipo, 40) + extra)
    return b


def boton_icono(nombre: str, tooltip: str, al_click: Callable | None = None) -> QPushButton:
    b = QPushButton()
    b.setProperty("tipo", "icono")
    b.setIcon(icono(nombre, C.TEXTO, 16))
    b.setToolTip(tooltip)
    b.setAccessibleName(tooltip)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    if al_click:
        b.clicked.connect(lambda *_: al_click())
    return b


# ---------------------------------------------------------------- tarjetas


class Card(QFrame):
    """Tarjeta blanca con borde suave; `self.lay` recibe el contenido."""

    def __init__(self, titulo: str | None = None, derecha: Iterable[QWidget] = (), margen: int = 20,
                 espacio: int = 14):
        super().__init__()
        self.setObjectName("Card")
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(margen, margen, margen, margen)
        self.lay.setSpacing(espacio)
        self.titulo_lbl: QLabel | None = None
        derecha = list(derecha)
        if titulo is not None or derecha:
            self.titulo_lbl = etiqueta(titulo or "", "CardTitulo")
            self.lay.addLayout(hbox(self.titulo_lbl, "stretch", *derecha, espacio=10))

    def agregar(self, *items) -> "Card":
        _agregar(self.lay, items)
        return self


class Kpi(Card):
    def __init__(self, titulo: str, valor: str, detalle: str = "", color: str | None = None,
                 detalle_widget: QWidget | None = None):
        super().__init__(margen=18, espacio=4)
        self.lbl_valor = etiqueta(valor, "KpiValor")
        if color:
            self.lbl_valor.setStyleSheet(f"color: {color};")
        self.lbl_detalle = etiqueta(detalle, "KpiDetalle", ajustar=True)
        self.lay.addWidget(etiqueta(titulo, "KpiTitulo"))
        self.lay.addWidget(self.lbl_valor)
        self.lay.addWidget(detalle_widget or self.lbl_detalle)
        self.lay.addStretch(1)

    def poner(self, valor: str, detalle: str | None = None, color: str | None = None) -> None:
        self.lbl_valor.setText(valor)
        if detalle is not None:
            self.lbl_detalle.setText(detalle)
        if color:
            self.lbl_valor.setStyleSheet(f"color: {color};")


def fila_kpis(*kpis: Kpi) -> QHBoxLayout:
    lay = hbox(*kpis, espacio=16)
    for k in kpis:
        k.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    return lay


def dato(etiqueta_: str, valor: str, color: str | None = None, negrita: bool = False) -> QWidget:
    """Par etiqueta/valor de las fichas (Fecha · Sáb 31 oct 2026)."""
    v = etiqueta(valor, "Valor", ajustar=True)
    estilo = []
    if color:
        estilo.append(f"color: {color};")
    if negrita:
        estilo.append("font-weight: 800;")
    if estilo:
        v.setStyleSheet(" ".join(estilo))
    return envolver(vbox(etiqueta(etiqueta_, "Etiqueta"), v, espacio=2))


# ---------------------------------------------------------------- insignias y alertas

_TONOS = {
    "verde": (C.VERDE_SUAVE, C.VERDE_TEXTO),
    "naranja": (C.NARANJA_SUAVE, C.NARANJA_TEXTO),
    "rojo": (C.ROJO_SUAVE, C.ROJO),
    "gris": (C.GRIS_BADGE, C.GRIS_BADGE_TEXTO),
    "guinda": (C.GUINDA_SUAVE, C.GUINDA),
}


class Badge(QLabel):
    def __init__(self, texto_: str, tono: str = "gris"):
        super().__init__(texto_)
        fondo, color = _TONOS.get(tono, _TONOS["gris"])
        self.setStyleSheet(
            f"background: {fondo}; color: {color}; border-radius: 11px; padding: 0 8px;"
            "font-size: 12px; font-weight: 800;"
        )
        self.setFixedSize(ancho_texto(texto_, 12, QFont.Weight.ExtraBold) + 24, 22)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)


class Alerta(QLabel):
    """Franja de aviso: naranja (atención), rojo (error), verde (éxito), crema (nota)."""

    def __init__(self, html: str = "", tono: str = "naranja"):
        super().__init__(html)
        self.setTextFormat(Qt.TextFormat.RichText)
        self.setWordWrap(True)
        self.setOpenExternalLinks(False)
        self.tono(tono)

    def tono(self, tono: str) -> None:
        fondo, color = {
            "naranja": (C.NARANJA_SUAVE, C.NARANJA_TEXTO),
            "rojo": (C.ROJO_SUAVE, C.ROJO),
            "verde": (C.VERDE_SUAVE, C.VERDE_TEXTO),
            "crema": (C.CREMA, C.TEXTO_SUAVE),
        }[tono]
        peso = "700" if tono == "rojo" else "500"
        self.setStyleSheet(
            f"background: {fondo}; color: {color}; border-radius: 10px; padding: 12px 14px;"
            f"font-size: 13px; font-weight: {peso};"
        )

    def mostrar(self, html: str, tono: str | None = None) -> None:
        if tono:
            self.tono(tono)
        self.setText(html)
        self.setVisible(bool(html))


# ---------------------------------------------------------------- campos


def entrada(valor: str = "", placeholder: str = "", password: bool = False,
            max_len: int | None = None, alinear_derecha: bool = False, compacto: bool = False) -> QLineEdit:
    e = QLineEdit(valor)
    if compacto:
        e.setProperty("compacto", True)
    e.setPlaceholderText(placeholder)
    if password:
        e.setEchoMode(QLineEdit.EchoMode.Password)
    if max_len:
        e.setMaxLength(max_len)
    if alinear_derecha:
        e.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    return e


def combo(opciones: Sequence, actual=None, compacto: bool = False) -> QComboBox:
    """opciones: textos o pares (texto, dato)."""
    c = QComboBox()
    # Sin esto un texto largo (régimen fiscal, motivo SAT) ensancha toda la página.
    c.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
    c.setMinimumContentsLength(6)
    if compacto:
        c.setProperty("compacto", True)
    for op in opciones:
        if isinstance(op, tuple):
            c.addItem(op[0], op[1])
        else:
            c.addItem(op, op)
    if actual is not None:
        i = c.findData(actual)
        if i < 0:
            i = c.findText(str(actual))
        if i >= 0:
            c.setCurrentIndex(i)
    c.setCursor(Qt.CursorShape.PointingHandCursor)
    return c


def selector_fecha(d=None) -> QDateEdit:
    f = QDateEdit()
    f.setDisplayFormat("dd/MM/yyyy")
    f.setCalendarPopup(True)
    if d is not None:
        f.setDate(QDate(d.year, d.month, d.day))
    else:
        f.setDate(QDate.currentDate())
    return f


def area_texto(valor: str = "", alto: int = 76) -> QPlainTextEdit:
    t = QPlainTextEdit(valor)
    t.setFixedHeight(alto)
    return t


class Campo(QWidget):
    """Etiqueta + control + mensaje de error o de ayuda, como en los formularios del diseño."""

    def __init__(self, etiqueta_: str, control: QWidget, ayuda: str = ""):
        super().__init__()
        self.control = control
        self.ayuda = ayuda
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        self.lbl = etiqueta(etiqueta_, "Etiqueta")
        self.msg = etiqueta(ayuda, "Ayuda", ajustar=True)
        self.msg.setVisible(bool(ayuda))
        lay.addWidget(self.lbl)
        lay.addWidget(control)
        lay.addWidget(self.msg)
        if isinstance(control, QLineEdit):
            control.textEdited.connect(lambda *_: self.error(None))

    def error(self, mensaje: str | None) -> bool:
        """Muestra u oculta el error. Devuelve True si hay error."""
        self.control.setProperty("error", bool(mensaje))
        repulir(self.control)
        if mensaje:
            self.msg.setObjectName("Error")
            self.msg.setText(mensaje)
            self.msg.setVisible(True)
        else:
            self.msg.setObjectName("Ayuda")
            self.msg.setText(self.ayuda)
            self.msg.setVisible(bool(self.ayuda))
        repulir(self.msg)
        return bool(mensaje)

    def valor(self) -> str:
        c = self.control
        if isinstance(c, QLineEdit):
            return c.text().strip()
        if isinstance(c, QComboBox):
            return c.currentText()
        if isinstance(c, QPlainTextEdit):
            return c.toPlainText().strip()
        return ""


def rejilla(filas: Sequence[Sequence[QWidget | tuple]], espacio: int = 14) -> QGridLayout:
    """Rejilla de formulario. Un elemento (widget, columnas) ocupa varias columnas."""
    g = QGridLayout()
    g.setHorizontalSpacing(espacio)
    g.setVerticalSpacing(espacio)
    for r, fila in enumerate(filas):
        c = 0
        for item in fila:
            w, span = item if isinstance(item, tuple) else (item, 1)
            if w is not None:
                g.addWidget(w, r, c, 1, span, Qt.AlignmentFlag.AlignTop)
            c += span
    for col in range(g.columnCount()):
        g.setColumnStretch(col, 1)
    return g


def casilla(texto_: str, marcada: bool = False) -> QCheckBox:
    cb = QCheckBox(texto_)
    cb.setChecked(marcada)
    cb.setCursor(Qt.CursorShape.PointingHandCursor)
    return cb


# ---------------------------------------------------------------- tablas


@dataclass
class Col:
    titulo: str
    alinear: str = "izq"  # izq | der | centro
    estirar: bool = False
    ancho: int | None = None


@dataclass
class Celda:
    texto: str
    negrita: bool = False
    color: str | None = None


_ALINEAR = {
    "izq": Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
    "der": Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
    "centro": Qt.AlignmentFlag.AlignCenter,
}

_FONDO_FILA = {
    "rojo": C.ROJO_SUAVE,
    "naranja": C.NARANJA_SUAVE,
    "guinda": C.GUINDA_SUAVE,
    "total": C.CREMA_TOTAL,
}


class _DelegadoFondo(QStyledItemDelegate):
    """Pinta el color de fila (alertas, total) que la hoja de estilos de ::item ignora."""

    def paint(self, painter, option, index):
        fondo = index.data(Qt.ItemDataRole.BackgroundRole)
        if fondo is not None:
            painter.fillRect(option.rect, fondo)
        super().paint(painter, option, index)


class Tabla(QTableWidget):
    """Tabla del diseño: encabezado crema, filas de 44 px y alto ajustado al contenido.

    Las celdas aceptan texto, `Celda` (negrita/color) o un widget (insignias, botones).
    """

    fila_elegida = Signal(int)

    def __init__(self, columnas: Sequence[Col], alto_fila: int = 44, max_filas_visibles: int | None = None):
        super().__init__(0, len(columnas))
        self.columnas = list(columnas)
        self.alto_fila = alto_fila
        self.max_filas = max_filas_visibles
        self.datos: list = []
        self.setHorizontalHeaderLabels([c.titulo for c in columnas])
        self.verticalHeader().setVisible(False)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setItemDelegate(_DelegadoFondo(self))
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setShowGrid(False)
        self.setWordWrap(True)
        self.setTextElideMode(Qt.TextElideMode.ElideNone)
        self.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded if max_filas_visibles
                                        else Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        h = self.horizontalHeader()
        h.setHighlightSections(False)
        h.setMinimumSectionSize(60)
        h.setFixedHeight(40)
        for i, c in enumerate(columnas):
            item = self.horizontalHeaderItem(i)
            item.setTextAlignment(_ALINEAR[c.alinear])
            if c.ancho:
                h.setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)
                self.setColumnWidth(i, c.ancho)
            elif c.estirar:
                h.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
            else:
                h.setSectionResizeMode(i, QHeaderView.ResizeMode.Interactive)
        self.verticalHeader().setDefaultSectionSize(alto_fila)
        self.cellClicked.connect(lambda r, _c: self.fila_elegida.emit(r))
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def poner_filas(self, filas: Sequence[Sequence], datos: Sequence | None = None,
                    tonos: dict[int, str] | None = None, total: Sequence | None = None) -> None:
        self.clearSpans()
        self.setRowCount(0)
        self.datos = list(datos) if datos is not None else []
        tonos = dict(tonos or {})
        todas = list(filas)
        if total is not None:
            todas.append(total)
            tonos[len(todas) - 1] = "total"
        self.setRowCount(len(todas))
        for r, fila in enumerate(todas):
            es_total = total is not None and r == len(todas) - 1
            fondo = _FONDO_FILA.get(tonos.get(r, ""))
            for c, valor in enumerate(fila):
                self._poner_celda(r, c, valor, es_total, fondo)
        self.ajustar_columnas()
        self.ajustar_alto()

    def ajustar_columnas(self) -> None:
        """Ancho al contenido, contando insignias y botones (que Qt no mide bien)."""
        for i, col in enumerate(self.columnas):
            if col.ancho or col.estirar:
                continue
            self.resizeColumnToContents(i)
            ancho = self.columnWidth(i)
            for r in range(self.rowCount()):
                w = self.cellWidget(r, i)
                if w is not None:
                    w.ensurePolished()
                    for hijo in w.findChildren(QWidget):
                        hijo.ensurePolished()
                    ancho = max(ancho, w.layout().sizeHint().width() + 6)
            self.setColumnWidth(i, ancho + 8)
        # Las columnas elásticas llenan el espacio, pero si no caben se vuelven de ancho fijo
        # y aparece el desplazamiento horizontal (como en el diseño) en lugar de aplastarlas.
        elasticas = [i for i, c in enumerate(self.columnas) if c.estirar]
        if not elasticas:
            return
        h = self.horizontalHeader()
        fijas = sum(self.columnWidth(i) for i in range(self.columnCount()) if i not in elasticas)
        contenido = {i: max(self.sizeHintForColumn(i), h.sectionSizeHint(i), 140) + 16 for i in elasticas}
        disponible = self.viewport().width() or self.width()
        cabe = fijas + sum(contenido.values()) <= disponible
        for i in elasticas:
            if cabe:
                h.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
            else:
                h.setSectionResizeMode(i, QHeaderView.ResizeMode.Interactive)
                self.setColumnWidth(i, contenido[i])

    def showEvent(self, e):
        super().showEvent(e)
        self.ajustar_columnas()
        self._fijar_alto()

    def _poner_celda(self, r: int, c: int, valor, negrita_fila: bool, fondo: str | None) -> None:
        alinear = _ALINEAR[self.columnas[c].alinear]
        if isinstance(valor, QWidget) or isinstance(valor, QLayout):
            contenedor = QWidget()
            lay = valor if isinstance(valor, QLayout) else hbox(valor, espacio=6)
            lay.setContentsMargins(10, 0, 10, 0)
            lay.setAlignment(alinear)
            contenedor.setLayout(lay)
            contenedor.setStyleSheet(f"background: {fondo or 'transparent'};")
            contenedor.ensurePolished()
            for hijo in contenedor.findChildren(QWidget):
                hijo.ensurePolished()
            item = QTableWidgetItem("")
            if fondo:
                item.setBackground(QColor(fondo))
            # Para que "ajustar al contenido" cuente el ancho de la insignia o los botones.
            item.setSizeHint(QSize(contenedor.sizeHint().width() + 4, self.alto_fila))
            self.setItem(r, c, item)
            self.setCellWidget(r, c, contenedor)
            return
        celda = valor if isinstance(valor, Celda) else Celda("" if valor is None else str(valor))
        item = QTableWidgetItem(celda.texto)
        item.setTextAlignment(alinear)
        f = fuente_texto(14, QFont.Weight.ExtraBold if (celda.negrita or negrita_fila) else QFont.Weight.Normal)
        item.setFont(f)
        if celda.color:
            item.setForeground(QColor(celda.color))
        if fondo:
            item.setBackground(QColor(fondo))
        self.setItem(r, c, item)

    def ajustar_alto(self) -> None:
        self.resizeRowsToContents()
        for r in range(self.rowCount()):
            if self.rowHeight(r) < self.alto_fila:
                self.setRowHeight(r, self.alto_fila)
        self._fijar_alto()
        QTimer.singleShot(0, self._fijar_alto)

    def _fijar_alto(self) -> None:
        filas = range(self.rowCount())
        if self.max_filas:
            filas = range(min(self.rowCount(), self.max_filas))
        alto = self.horizontalHeader().height() + sum(self.rowHeight(r) for r in filas) + 4
        barra = self.horizontalScrollBar()
        if barra.maximum() > 0:
            alto += barra.sizeHint().height()
        if alto != self.height():
            self.setFixedHeight(alto)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if e.oldSize().width() != e.size().width():
            QTimer.singleShot(0, self.ajustar_columnas)
        QTimer.singleShot(0, self._fijar_alto)

    def dato(self, fila: int):
        return self.datos[fila] if 0 <= fila < len(self.datos) else None


def vacio(mensaje: str = "Sin información para los parámetros seleccionados.") -> QLabel:
    lbl = etiqueta(mensaje, "Muted")
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl.setMinimumHeight(60)
    return lbl


# ---------------------------------------------------------------- barras y gráficas


class Barra(QWidget):
    """Barra de avance redondeada (uso de crédito, existencias, métodos de pago)."""

    def __init__(self, fraccion: float, color: str = C.VERDE, alto: int = 8, ancho_min: int = 120,
                 pista: str = C.PISTA):
        super().__init__()
        self.fraccion = max(0.0, min(1.0, fraccion))
        self.color = color
        self.pista = pista
        self.setFixedHeight(alto)
        self.setMinimumWidth(ancho_min)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.height() / 2 if self.height() <= 10 else 6
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(self.pista))
        p.drawRoundedRect(QRectF(self.rect()), r, r)
        if self.fraccion > 0:
            p.setBrush(QColor(self.color))
            ancho = max(self.height() if self.height() <= 10 else 8, self.width() * self.fraccion)
            p.drawRoundedRect(QRectF(0, 0, ancho, self.height()), r, r)
        p.end()


class GraficaBarras(QWidget):
    """Barras verticales agrupadas con etiqueta y subtítulo por grupo."""

    def __init__(self, grupos: Sequence[tuple[str, str, Sequence[float]]], colores: Sequence[str],
                 alto: int = 300, guias: int = 4):
        super().__init__()
        self.grupos = list(grupos)
        self.colores = list(colores)
        self.guias = guias
        self.setMinimumHeight(alto)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        etiquetas = 46 if any(g[1] for g in self.grupos) else 26
        area = h - etiquetas - 8
        maximo = max((v for g in self.grupos for v in g[2]), default=1) or 1
        p.setPen(QColor(C.BORDE))
        for i in range(self.guias + 1):
            y = 8 + area * i / self.guias
            p.drawLine(0, int(y), w, int(y))
        n = len(self.grupos)
        if not n:
            return
        ancho_grupo = w / n
        series = max(len(g[2]) for g in self.grupos)
        barra = min(36, ancho_grupo * 0.7 / series)
        hueco = 8
        for gi, (nombre, sub, valores) in enumerate(self.grupos):
            total = series * barra + (series - 1) * hueco
            x0 = gi * ancho_grupo + (ancho_grupo - total) / 2
            for si, v in enumerate(valores):
                alto_b = area * (v / maximo) * 0.92
                x = x0 + si * (barra + hueco)
                path = QPainterPath()
                path.addRoundedRect(QRectF(x, 8 + area - alto_b, barra, alto_b + 4), 5, 5)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(self.colores[si % len(self.colores)]))
                p.setClipRect(QRectF(0, 0, w, 8 + area))
                p.drawPath(path)
                p.setClipping(False)
            p.setPen(QColor(C.TEXTO))
            p.setFont(fuente_texto(13, QFont.Weight.ExtraBold))
            p.drawText(QRectF(gi * ancho_grupo, 8 + area + 6, ancho_grupo, 20), Qt.AlignmentFlag.AlignCenter, nombre)
            if sub:
                p.setPen(QColor(C.TEXTO_SUAVE))
                p.setFont(fuente_texto(12))
                p.drawText(QRectF(gi * ancho_grupo, 8 + area + 24, ancho_grupo, 20), Qt.AlignmentFlag.AlignCenter, sub)
        p.end()


class BarrasSimples(QWidget):
    """Columnas de un solo valor con colores propios (saldo al cierre de cada semana)."""

    def __init__(self, valores: Sequence[float], colores: Sequence[str], alto: int = 130):
        super().__init__()
        self.valores, self.colores = list(valores), list(colores)
        self.setFixedHeight(alto)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        n = len(self.valores) or 1
        maximo = max(self.valores, default=1) or 1
        hueco = 12
        ancho = (self.width() - hueco * (n - 1)) / n
        for i, v in enumerate(self.valores):
            alto = self.height() * v / maximo
            path = QPainterPath()
            path.addRoundedRect(QRectF(i * (ancho + hueco), self.height() - alto, ancho, alto + 6), 6, 6)
            p.setClipRect(self.rect())
            p.fillPath(path, QColor(self.colores[i % len(self.colores)]))
        p.end()


def leyenda(*pares: tuple[str, str]) -> QHBoxLayout:
    items = []
    for color, nombre in pares:
        cuadro = QLabel()
        cuadro.setFixedSize(12, 12)
        cuadro.setStyleSheet(f"background: {color}; border-radius: 3px;")
        items += [cuadro, texto(nombre, 13, QFont.Weight.DemiBold)]
    lay = hbox(*items, espacio=6)
    return lay


# ---------------------------------------------------------------- página


class Pagina(QWidget):
    """Encabezado blanco (migas + título + estado/acciones) y cuerpo con desplazamiento."""

    def __init__(self, migas: str, titulo: str, estado: str | None = None,
                 acciones: Iterable[QWidget] = (), punto: str = C.VERDE, ancho_max: int | None = None):
        super().__init__()
        self.setObjectName("Contenido")
        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)

        enc = QFrame()
        enc.setObjectName("Encabezado")
        enc.setFixedHeight(84)
        lay_enc = QHBoxLayout(enc)
        lay_enc.setContentsMargins(30, 12, 30, 12)
        self.lbl_migas = etiqueta(migas, "Migas", rico="<a" in migas)
        self.lbl_migas.linkActivated.connect(self._migas_click)
        self.lbl_titulo = etiqueta(titulo, "TituloPagina")
        lay_enc.addLayout(vbox(self.lbl_migas, self.lbl_titulo, espacio=2))
        lay_enc.addStretch(1)
        self.zona_derecha = hbox(espacio=10)
        lay_enc.addLayout(self.zona_derecha)
        self.lbl_estado = None
        if estado is not None:
            self.poner_estado(estado, punto)
        for a in acciones:
            self.zona_derecha.addWidget(a)
        raiz.addWidget(enc)

        scroll = QScrollArea()
        scroll.setObjectName("Cuerpo")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        interior = QWidget()
        interior.setObjectName("CuerpoInterior")
        self.cuerpo = QVBoxLayout(interior)
        self.cuerpo.setContentsMargins(30, 26, 30, 30)
        self.cuerpo.setSpacing(20)
        if ancho_max:
            interior.setMaximumWidth(ancho_max)
        scroll.setWidget(interior)
        raiz.addWidget(scroll, 1)
        self.al_migas: Callable[[str], None] | None = None

    def poner_estado(self, estado: str, punto: str | None = C.VERDE) -> None:
        if self.lbl_estado is None:
            self.punto = QLabel()
            self.punto.setFixedSize(8, 8)
            self.lbl_estado = etiqueta("", "Estado")
            self.zona_derecha.insertWidget(0, self.lbl_estado)
            self.zona_derecha.insertWidget(0, self.punto)
            self.zona_derecha.insertSpacing(1, -2)
        self.punto.setVisible(bool(punto))
        if punto:
            self.punto.setStyleSheet(f"background: {punto}; border-radius: 4px;")
        self.lbl_estado.setText(estado)

    def _migas_click(self, enlace: str) -> None:
        if self.al_migas:
            self.al_migas(enlace)

    def agregar(self, *items) -> None:
        _agregar(self.cuerpo, items)

    def terminar(self) -> None:
        self.cuerpo.addStretch(1)


def columnas(*items, espacio: int = 20, proporciones: Sequence[int] | None = None) -> QHBoxLayout:
    """Columnas lado a lado alineadas arriba (formularios y paneles laterales)."""
    lay = QHBoxLayout()
    lay.setSpacing(espacio)
    for i, it in enumerate(items):
        s = proporciones[i] if proporciones else 1
        if isinstance(it, QLayout):
            cont = QVBoxLayout()
            cont.addLayout(it)
            cont.addStretch(1)
            lay.addLayout(cont, s)
        else:
            cont = QVBoxLayout()
            cont.setSpacing(0)
            cont.addWidget(it)
            cont.addStretch(1)
            lay.addLayout(cont, s)
    return lay


# ---------------------------------------------------------------- diálogos


def confirmar(padre: QWidget, titulo: str, mensaje: str, aceptar: str = "Sí, continuar",
              peligro: bool = False) -> bool:
    caja = QMessageBox(padre)
    caja.setWindowTitle(titulo)
    caja.setText(mensaje)
    caja.setIcon(QMessageBox.Icon.Warning if peligro else QMessageBox.Icon.Question)
    si = caja.addButton(aceptar, QMessageBox.ButtonRole.AcceptRole)
    no = caja.addButton("Cancelar", QMessageBox.ButtonRole.RejectRole)
    si.setProperty("tipo", "peligro" if peligro else "primario")
    no.setProperty("tipo", "texto")
    caja.setDefaultButton(no)
    caja.exec()
    return caja.clickedButton() is si


def avisar(padre: QWidget, titulo: str, mensaje: str, error: bool = False) -> None:
    caja = QMessageBox(padre)
    caja.setWindowTitle(titulo)
    caja.setText(mensaje)
    caja.setIcon(QMessageBox.Icon.Critical if error else QMessageBox.Icon.Information)
    ok = caja.addButton("Aceptar", QMessageBox.ButtonRole.AcceptRole)
    ok.setProperty("tipo", "primario")
    caja.exec()
