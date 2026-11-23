"""CAT-07 · Historial de precios contra costo de compra (solo lectura)."""
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath
from PySide6.QtWidgets import QSizePolicy, QWidget

from app import formato as fmt
from app.theme import C, fuente_texto
from app.views.base import Contexto, PaginaBase
from app.widgets import Campo, Card, Col, Tabla, boton, columnas, combo, envolver, etiqueta, hbox, leyenda


class BarrasPrecio(QWidget):
    """Pares de barras horizontales: precio de venta y costo en cada fecha de cambio."""

    def __init__(self, puntos):
        super().__init__()
        self.puntos = list(puntos)
        self.setMinimumHeight(len(self.puntos) * 48 + 8)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        maximo = float(max((max(v, c) for _, v, c in self.puntos), default=1)) or 1
        izq, der = 84, 70
        ancho = self.width() - izq - der
        for i, (nombre, venta, costo) in enumerate(self.puntos):
            y = 6 + i * 48
            p.setPen(QColor(C.TEXTO))
            p.setFont(fuente_texto(13, QFont.Weight.ExtraBold))
            p.drawText(QRectF(0, y, izq, 34), Qt.AlignmentFlag.AlignVCenter, nombre)
            for j, (valor, color, peso) in enumerate(((venta, C.GUINDA, QFont.Weight.ExtraBold), (costo, "#D2A98F", QFont.Weight.Normal))):
                w = ancho * float(valor) / maximo
                yy = y + j * 18
                path = QPainterPath()
                path.addRoundedRect(QRectF(izq, yy, w, 14), 3, 3)
                p.fillPath(path, QColor(color))
                p.setPen(QColor(C.TEXTO if j == 0 else C.TEXTO_SUAVE))
                p.setFont(fuente_texto(12, peso))
                p.drawText(QRectF(izq + w + 6, yy - 3, der + 20, 20), Qt.AlignmentFlag.AlignVCenter, fmt.dinero(valor))
        p.end()


class HistorialPreciosView(PaginaBase):
    def __init__(self, ctx: Contexto):
        acciones = [boton("Ajustar precios", "primario", lambda: ctx.navegar("inv.precios"))] \
            if ctx.sesion.puede("inventario", "editar") else []
        super().__init__(ctx, "Catálogo e Inventario", "Historial de precios", acciones=acciones)
        prods = self.intentar(ctx.datos.lista_productos) or []
        self.producto = combo([(p["nombre"], p["id_producto"]) for p in prods], 3)
        self.periodo = combo(["Últimos 3 meses", "Últimos 6 meses", "Último año"])
        self.producto.currentIndexChanged.connect(self._cargar)
        self.izq = Card()
        self.izq.agregar(hbox(Campo("Producto", self.producto), Campo("Periodo", self.periodo)))
        self.titulo_graf = etiqueta("Precio de venta contra costo de compra", "Etiqueta")
        self.izq.agregar(self.titulo_graf)
        self.cont_graf = hbox()
        self.izq.agregar(self.cont_graf, envolver(leyenda((C.GUINDA, "Precio de venta"), ("#D2A98F", "Costo"))))
        self.tabla = Tabla([Col("Fecha"), Col("Anterior", "der"), Col("Nuevo", "der"), Col("Motivo", estirar=True), Col("Usuario")])
        self.vacio = etiqueta("Este producto no ha cambiado de precio.", "Muted")
        der = Card("Cambios registrados").agregar(self.tabla, self.vacio,
                                                  etiqueta("Solo lectura. Cada cambio también queda en la bitácora de auditoría.",
                                                           "Muted", ajustar=True))
        self.agregar(columnas(self.izq, der))
        self.terminar()
        self._cargar()

    def al_mostrar(self, id_producto=None, **_):
        if id_producto:
            self.producto.setCurrentIndex(max(0, self.producto.findData(int(id_producto))))

    def _cargar(self, *_):
        if self.producto.currentData() is None:
            return
        h = self.intentar(self.ctx.datos.historial, self.producto.currentData())
        if not h:
            return
        from app.widgets import limpiar
        limpiar(self.cont_graf)
        u = "kg" if h["producto"]["unidad_venta"] == "kg" else "pieza"
        self.titulo_graf.setText(f"Precio de venta contra costo de compra (por {u})")
        self.cont_graf.addWidget(BarrasPrecio(h["puntos"]))
        self.tabla.poner_filas([[fmt.fecha_hora(c["fecha"]), fmt.dinero(c["anterior"]), fmt.dinero(c["nuevo"]), c["motivo"],
                                 c["usuario"]] for c in h["cambios"]])
        self.tabla.setVisible(bool(h["cambios"]))
        self.vacio.setVisible(not h["cambios"])
