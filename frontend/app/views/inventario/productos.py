"""CAT-02 · Productos del catálogo (flujo P, HU-10)."""

from PySide6.QtCore import Qt

from app import formato as fmt
from app.datos import ErrorNegocio
from app.validaciones import cantidad_positiva, error_obligatorio, monto_positivo
from app.views.base import Contexto, PaginaBase
from app.widgets import (
    Badge, Campo, Card, Celda, Col, Tabla, boton, boton_icono, combo, entrada, etiqueta, hbox, rejilla,
)


class ProductosView(PaginaBase):
    def __init__(self, ctx: Contexto):
        acciones = [boton("Categorías", "secundario", lambda: ctx.navegar("inv.categorias"))]
        if ctx.sesion.puede("inventario", "editar"):
            acciones.append(boton("Ajustar precios", "secundario", lambda: ctx.navegar("inv.precios")))
        super().__init__(ctx, "Catálogo e Inventario", "Productos", acciones=acciones)
        self.editando: dict | None = None
        cats = self.intentar(ctx.datos.categorias_activas) or []
        self.buscar = entrada(placeholder="Nombre o código de barras")
        self.buscar.textChanged.connect(self._cargar)
        self.categoria = combo([("Todas", None)] + [(c["nombre"], c["id"]) for c in cats])
        self.existencia = combo(["Todas", "Bajo el mínimo", "Por caducar"])
        self.categoria.currentIndexChanged.connect(self._cargar)
        self.existencia.currentIndexChanged.connect(self._cargar)
        nuevo = boton("+ Nuevo producto", "primario", self._nuevo)
        nuevo.setVisible(ctx.sesion.puede("inventario", "crear"))
        self.tabla = Tabla([Col("Código"), Col("Producto", estirar=True), Col("Categoría"), Col("Unidad"), Col("Precio", "der"),
                            Col("Existencia", "der"), Col("Mínimo", "der"), Col("Estado"), Col("", ancho=96)])
        self.agregar(Card().agregar(
            hbox((Campo("Buscar por nombre o código", self.buscar), 2), (Campo("Categoría", self.categoria), 1),
                 (Campo("Existencia", self.existencia), 1), nuevo, alinear=Qt.AlignmentFlag.AlignBottom),
            self.tabla))

        self.codigo = entrada(max_len=32)
        self.nombre = entrada(max_len=120)
        self.cat_form = combo([(c["nombre"], c["id"]) for c in cats])
        self.unidad = combo([("Kilogramo", "kg"), ("Pieza", "pza")])
        self.precio = entrada(placeholder="$0.00")
        self.minimo = entrada(placeholder="15")
        self.estatus = combo([("Activo", True), ("Inactivo (baja lógica)", False)])
        self.campos = {"codigo": Campo("Código de barras *", self.codigo), "nombre": Campo("Nombre *", self.nombre),
                       "categoria": Campo("Categoría *", self.cat_form), "unidad": Campo("Unidad de venta *", self.unidad),
                       "precio": Campo("Precio con IVA *", self.precio), "minimo": Campo("Stock mínimo *", self.minimo),
                       "estatus": Campo("Estatus", self.estatus)}
        c = self.campos
        self.form = Card("Nuevo producto").agregar(
            rejilla([[c["codigo"], (c["nombre"], 2), c["categoria"], c["unidad"], c["precio"]],
                     [(c["minimo"], 2), (c["estatus"], 2)]]),
            etiqueta("La existencia no se captura aquí: se calcula con los lotes de compra, las ventas y las mermas.", "Muted"),
            hbox(boton("Guardar", "primario", self._guardar), boton("Cancelar", "texto", lambda: self.form.setVisible(False)),
                 "stretch"))
        self.form.setVisible(False)
        self.agregar(self.form)
        self.terminar()
        self._cargar()

    def _cargar(self, *_):
        filas = self.intentar(self.ctx.datos.lista_productos, self.buscar.text().strip(), self.categoria.currentData(),
                              self.existencia.currentText()) or []
        puede = self.ctx.sesion.puede("inventario", "editar")
        salida = []
        for p in filas:
            u = "pza" if p["unidad_venta"] != "kg" else "kg"
            acciones = hbox(boton_icono("movimientos", "Movimientos", lambda p=p: self.ctx.navegar("inv.movimientos", id_producto=p["id_producto"])),
                            boton_icono("lapiz", "Editar", lambda p=p: self._editar(p)) if puede else None, espacio=6)
            nombre = Celda(p["nombre"], True, None if p["activo"] else "#9A918B")
            salida.append([p["codigo_barras"], nombre, p["categoria"], u, fmt.dinero(p["precio_venta"]),
                           fmt.cantidad(p["existencia"], u, 1 if u == "kg" else 0), f"{p['stock_minimo']:.0f} {u}",
                           Badge(p["estado"] if p["activo"] else "Baja", p["tono"] if p["activo"] else "gris"), acciones])
        self.tabla.poner_filas(salida, datos=filas)

    def _nuevo(self) -> None:
        self.editando = None
        self.form.titulo_lbl.setText("Nuevo producto")
        for w in (self.codigo, self.nombre, self.precio, self.minimo):
            w.clear()
        self.campos["estatus"].setVisible(False)
        for campo in self.campos.values():
            campo.error(None)
        self.form.setVisible(True)
        self.codigo.setFocus()

    def _editar(self, p: dict) -> None:
        self.editando = p
        self.form.titulo_lbl.setText(f"Editar · {p['nombre']}")
        self.codigo.setText(p["codigo_barras"])
        self.nombre.setText(p["nombre"])
        self.cat_form.setCurrentIndex(max(0, self.cat_form.findData(p["id_categoria"])))
        self.unidad.setCurrentIndex(0 if p["unidad_venta"] == "kg" else 1)
        self.precio.setText(f"{p['precio_venta']:.2f}")
        self.minimo.setText(f"{p['stock_minimo']:.0f}")
        self.estatus.setCurrentIndex(0 if p["activo"] else 1)
        self.campos["estatus"].setVisible(True)
        for campo in self.campos.values():
            campo.error(None)
        self.form.setVisible(True)

    def _guardar(self) -> None:
        precio, err_precio = monto_positivo(self.precio.text(), "El precio debe ser mayor a 0.")
        minimo = cantidad_positiva(self.minimo.text())
        errores = {"codigo": error_obligatorio(self.codigo.text(), "El código de barras", 32),
                   "nombre": error_obligatorio(self.nombre.text(), "El nombre", 120),
                   "precio": err_precio, "minimo": None if minimo is not None else "Escribe el stock mínimo."}
        if any([self.campos[k].error(v) for k, v in errores.items()]):
            return
        datos = dict(codigo_barras=self.codigo.text().strip(), nombre=self.nombre.text().strip(),
                     id_categoria=self.cat_form.currentData(), unidad_venta=self.unidad.currentData(),
                     precio_venta=precio, stock_minimo=minimo, activo=self.estatus.currentData() if self.editando else True)
        if self.editando:
            datos["id_producto"] = self.editando["id_producto"]
        try:
            self.intentar(self.ctx.datos.guardar_producto, datos, mostrar_dialogo=False)
        except ErrorNegocio as exc:
            self.campos.get(exc.campo or "nombre", self.campos["nombre"]).error(exc.mensaje)
            return
        if self.aviso.isVisible():
            return
        self.form.setVisible(False)
        self._cargar()
