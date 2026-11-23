"""CAT-06 · Ajuste de precios con vista previa del margen (flujo Q, HU-31)."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout

from app import formato as fmt
from app.theme import C
from app.views.base import Contexto, PaginaBase
from app.widgets import (
    Alerta, Campo, Card, Celda, Col, Tabla, avisar, boton, casilla, combo, confirmar, entrada, etiqueta, hbox, limpiar,
)

APLICAR = ["Una categoría", "Un producto", "Todo el catálogo"]
TIPOS = ["Porcentaje de aumento", "Porcentaje de descuento", "Precio fijo"]


class AjustePreciosView(PaginaBase):
    def __init__(self, ctx: Contexto):
        super().__init__(ctx, "Catálogo e Inventario", "Ajuste de precios",
                         acciones=[boton("Historial de precios", "secundario", lambda: ctx.navegar("inv.historial"))])
        self.filas: list[dict] = []
        self.confirmaciones: dict[int, object] = {}
        cats = self.intentar(ctx.datos.categorias_activas) or []
        prods = self.intentar(ctx.datos.lista_productos) or []
        self.aplicar = combo(APLICAR)
        self.categoria = combo([(c["nombre"], c["id"]) for c in cats])
        self.producto = combo([(p["nombre"], p["id_producto"]) for p in prods])
        self.c_categoria = Campo("Categoría", self.categoria)
        self.c_producto = Campo("Producto", self.producto)
        self.tipo = combo(TIPOS)
        self.valor = entrada("5", placeholder="5 %")
        self.c_valor = Campo("Valor", self.valor)
        self.aplicar.currentIndexChanged.connect(self._modo)
        self.tipo.currentIndexChanged.connect(lambda *_: self.c_valor.lbl.setText(
            "Precio nuevo ($)" if self.tipo.currentText() == "Precio fijo" else "Valor (%)"))
        self.agregar(Card().agregar(hbox(Campo("Aplicar a", self.aplicar), self.c_categoria, self.c_producto,
                                         Campo("Tipo de ajuste", self.tipo), self.c_valor,
                                         boton("Previsualizar", "secundario", self._previsualizar),
                                         alinear=Qt.AlignmentFlag.AlignBottom)))
        self.c_producto.setVisible(False)

        self.tabla = Tabla([Col("Producto", estirar=True), Col("Costo", "der"), Col("Precio actual", "der"),
                            Col("Precio nuevo", "der"), Col("Margen nuevo", "der"), Col("")])
        self.alerta = Alerta("", "rojo")
        self.alerta.setVisible(False)
        self.checks = QVBoxLayout()
        self.checks.setSpacing(6)
        self.motivo = entrada(placeholder="Ej. Frutas +5 % por temporada", max_len=80)
        self.vista = Card("Vista previa").agregar(
            self.tabla, self.alerta, self.checks, Campo("Motivo del cambio", self.motivo),
            etiqueta("Los precios nuevos aplican desde la siguiente venta y no cambian tickets anteriores. El cambio queda "
                     "en el historial y en la auditoría.", "Muted", ajustar=True),
            hbox(boton("Aplicar ajuste", "primario", self._aplicar), boton("Cancelar", "texto", self._cancelar), "stretch"))
        self.vista.setVisible(False)
        self.agregar(self.vista)
        self.terminar()

    def _modo(self, *_):
        modo = self.aplicar.currentText()
        self.c_categoria.setVisible(modo == "Una categoría")
        self.c_producto.setVisible(modo == "Un producto")

    def _previsualizar(self) -> None:
        valor = fmt.leer_dinero(self.valor.text().replace("%", ""))
        if valor is None or valor <= 0 or (self.tipo.currentText() == "Porcentaje de descuento" and valor >= 100):
            self.c_valor.error("Ingrese un valor válido.")
            return
        self.c_valor.error(None)
        self.filas = self.intentar(self.ctx.datos.previsualizar_precios, self.aplicar.currentText(),
                                   self.categoria.currentData(), self.producto.currentData(),
                                   self.tipo.currentText(), valor) or []
        self.vista.titulo_lbl.setText(f"Vista previa · {len(self.filas)} productos")
        if not self.motivo.text():
            signo = "+" if self.tipo.currentText() == "Porcentaje de aumento" else "−"
            ambito = self.categoria.currentText() if self.aplicar.currentText() == "Una categoría" else "Ajuste"
            self.motivo.setText(f"{ambito} {signo}{valor} %" if self.tipo.currentText() != "Precio fijo" else "Ajuste individual")
        tonos, salida = {}, []
        for i, f in enumerate(self.filas):
            if f["perdida"]:
                tonos[i] = "rojo"
            salida.append([f["nombre"], fmt.precio_unitario(f["costo"], f["unidad"]), fmt.dinero(f["actual"]),
                           Celda(fmt.dinero(f["nuevo"]), True),
                           Celda(fmt.porcentaje(f["margen"]), f["perdida"], C.ROJO if f["perdida"] else None),
                           Celda("Debajo del costo", True, C.ROJO) if f["perdida"] else ""])
        self.tabla.poner_filas(salida, tonos=tonos)
        # Confirmación explícita por cada producto que quedaría con pérdida.
        limpiar(self.checks)
        self.confirmaciones.clear()
        perdidas = [f for f in self.filas if f["perdida"]]
        if perdidas:
            textos = [f"{f['nombre']} quedaría {fmt.dinero(f['costo'] - f['nuevo'])} por debajo de su costo" for f in perdidas]
            self.alerta.mostrar(". ".join(textos) + ". Para aplicar el ajuste confirma que quieres venderlo con pérdida "
                                "o quítalo del ajuste.", "rojo")
            for f in perdidas:
                cb = casilla(f"Confirmo vender {f['nombre']} por debajo del costo")
                self.checks.addWidget(cb)
                self.confirmaciones[f["id_producto"]] = cb
        else:
            self.alerta.setVisible(False)
        self.vista.setVisible(True)

    def _aplicar(self) -> None:
        sin_confirmar = [f["nombre"] for f in self.filas if f["perdida"] and not self.confirmaciones[f["id_producto"]].isChecked()]
        if sin_confirmar:
            avisar(self, "Falta confirmar", f"Confirma la venta con pérdida de: {', '.join(sin_confirmar)}.", error=True)
            return
        if not self.motivo.text().strip():
            avisar(self, "Falta el motivo", "Escribe el motivo del cambio para el historial.", error=True)
            return
        if not confirmar(self, "Aplicar ajuste", f"Se cambiará el precio de {len(self.filas)} productos.", "Aplicar"):
            return
        self.intentar(self.ctx.datos.aplicar_precios, self.filas, self.motivo.text().strip())
        if not self.aviso.isVisible():
            avisar(self, "Precios actualizados", "Los precios nuevos aplican desde la siguiente venta.")
            self._cancelar()

    def _cancelar(self) -> None:
        self.vista.setVisible(False)
        self.filas = []

