"""CAT-08 · Registro y consulta de mermas por lote (flujo R, HU-17)."""
from decimal import Decimal

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QVBoxLayout

from app import formato as fmt
from app.datos import ErrorNegocio
from app.theme import C
from app.validaciones import cantidad_positiva
from app.views.base import Contexto, PaginaBase
from app.widgets import (
    Campo, Card, Col, Tabla, boton, combo, entrada, etiqueta, hbox, rejilla, texto,
)

MOTIVOS = ["Maduración", "Golpe", "Plaga u hongo", "Devolución en mal estado", "Caducidad", "Otro"]


class MermasView(PaginaBase):
    def __init__(self, ctx: Contexto):
        super().__init__(ctx, "Catálogo e Inventario", "Mermas", estado="")
        self.lotes: list[dict] = []
        prods = self.intentar(ctx.datos.lista_productos) or []
        self.producto = combo([(p["nombre"], p) for p in prods if p["activo"]])
        self.lote = combo([])
        self.cantidad = entrada(placeholder="0.0")
        self.motivo = combo(MOTIVOS)
        self.obs = entrada(max_len=200, placeholder="Ej. Fresa aguada en la exhibición")
        self.c_cantidad = Campo("Cantidad *", self.cantidad)
        self.c_lote = Campo("Lote *", self.lote)
        self.costo_box = QFrame()
        self.costo_box.setStyleSheet(f"QFrame {{ background: {C.CREMA}; border-radius: 10px; }}")
        lay = QVBoxLayout(self.costo_box)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.addWidget(etiqueta("Costo de la merma", "Etiqueta"))
        self.costo = texto("$0.00", 18, QFont.Weight.ExtraBold)
        lay.addWidget(self.costo)
        self.producto.currentIndexChanged.connect(self._lotes)
        self.lote.currentIndexChanged.connect(self._costo)
        self.cantidad.textChanged.connect(self._costo)
        self.form = Card("Registrar merma").agregar(
            rejilla([[Campo("Producto *", self.producto), self.c_lote, self.c_cantidad, Campo("Motivo *", self.motivo)],
                     [(Campo("Observaciones", self.obs), 3), self.costo_box]]),
            hbox(boton("Registrar merma", "primario", self._registrar), boton("Cancelar", "texto", self._limpiar), "stretch"))
        self.form.setVisible(ctx.sesion.puede("inventario", "crear"))
        self.agregar(self.form)

        self.f_motivo = combo(["Todos"] + MOTIVOS)
        self.f_motivo.currentIndexChanged.connect(self._cargar)
        self.tabla = Tabla([Col("Fecha"), Col("Producto", estirar=True), Col("Lote"), Col("Cantidad", "der"),
                            Col("Motivo"), Col("Costo", "der"), Col("Usuario")])
        lista = Card()
        lista.agregar(hbox(etiqueta("Mermas recientes", "CardTitulo"), "stretch", Campo("Motivo", self.f_motivo),
                           boton("Reporte de mermas", "secundario", lambda: ctx.navegar("reportes", numero="2")),
                           alinear=Qt.AlignmentFlag.AlignBottom), self.tabla)
        self.agregar(lista)
        self.terminar()
        self._lotes()
        self._cargar()

    def al_mostrar(self, id_producto=None, lote=None, **_):
        if id_producto:
            for i in range(self.producto.count()):
                if self.producto.itemData(i)["id_producto"] == int(id_producto):
                    self.producto.setCurrentIndex(i)
            if lote:
                self.lote.setCurrentIndex(max(0, self.lote.findText(lote, Qt.MatchFlag.MatchStartsWith)))
            self.cantidad.setFocus()

    def _lotes(self, *_):
        p = self.producto.currentData()
        self.lote.clear()
        self.lotes = (self.intentar(self.ctx.datos.lotes_de_producto, p["id_producto"]) or []) if p else []
        u = "kg" if p and p["unidad_venta"] == "kg" else "pza"
        for l in self.lotes:
            self.lote.addItem(f"{l['lote']} · queda {l['queda']:.1f} {u} · caduca {l['caducidad']:%d/%m}", l)
        if not self.lotes:
            self.lote.addItem("Sin lotes con existencia", None)
        self._costo()

    def _costo(self, *_):
        l = self.lote.currentData()
        q = cantidad_positiva(self.cantidad.text())
        self.c_cantidad.error(None)
        if not l:
            self.costo.setText("$0.00")
            return
        if q is not None and q > l["queda"]:
            self.c_cantidad.error("La cantidad supera la existencia del lote.")
            self.costo.setText(f"{fmt.dinero(l['queda'] * l['costo'])} máximo")
            return
        self.costo.setText(fmt.dinero((q or Decimal('0')) * l["costo"]))

    def _cargar(self, *_):
        r = self.intentar(self.ctx.datos.lista_mermas, self.f_motivo.currentText())
        if not r:
            return
        self.poner_estado(f"{r['mes']}: {r['kilos_mes']:.1f} kg · {fmt.dinero(r['costo_mes'])}")
        self.tabla.poner_filas([[fmt.fecha(m["fecha"]), m["producto"], m["lote"], fmt.cantidad(m["cantidad"], m["unidad"], 1),
                                 m["motivo"], fmt.dinero(m["costo"]), m["usuario"]] for m in r["filas"]])

    def _limpiar(self) -> None:
        self.cantidad.clear()
        self.obs.clear()
        self.c_cantidad.error(None)

    def _registrar(self) -> None:
        p, l = self.producto.currentData(), self.lote.currentData()
        if not l:
            self.c_lote.error("Este producto no tiene lotes con existencia.")
            return
        q = cantidad_positiva(self.cantidad.text(), 3 if p["unidad_venta"] == "kg" else 0)
        if q is None:
            self.c_cantidad.error("Ingrese una cantidad válida.")
            return
        if q > l["queda"]:
            self.c_cantidad.error("La cantidad supera la existencia del lote.")
            return
        try:
            costo = self.intentar(self.ctx.datos.registrar_merma, p["id_producto"], l["lote"], q, self.motivo.currentText(),
                                  self.obs.text().strip(), mostrar_dialogo=False)
        except ErrorNegocio as exc:
            self.c_cantidad.error(exc.mensaje)
            return
        if costo is None:
            return
        self._limpiar()
        self._lotes()
        self._cargar()
