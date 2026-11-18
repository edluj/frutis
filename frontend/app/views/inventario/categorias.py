"""CAT-01 · Categorías de productos (flujo O, HU-22)."""
from PySide6.QtCore import Qt

from app.datos import ErrorNegocio
from app.validaciones import error_obligatorio
from app.views.base import Contexto, PaginaBase
from app.widgets import (
    Badge, Campo, Card, Celda, Col, Tabla, area_texto, boton, boton_icono, columnas, combo, entrada, hbox,
)


class CategoriasView(PaginaBase):
    def __init__(self, ctx: Contexto):
        super().__init__(ctx, "Catálogo e Inventario", "Categorías",
                         acciones=[boton("Ir a productos", "secundario", lambda: ctx.navegar("inv.productos"))])
        self.editando: dict | None = None
        self.buscar = entrada(placeholder="Nombre de la categoría")
        self.buscar.textChanged.connect(self._cargar)
        nueva = boton("+ Nueva categoría", "primario", self._nueva)
        nueva.setVisible(ctx.sesion.puede("inventario", "crear"))
        self.tabla = Tabla([Col("Categoría"), Col("Descripción", estirar=True), Col("Productos activos", "der"),
                            Col("Estatus"), Col("", "centro", ancho=70)])
        izq = Card().agregar(hbox((Campo("Buscar categoría", self.buscar), 1), nueva, alinear=Qt.AlignmentFlag.AlignBottom),
                             self.tabla)

        self.nombre = entrada(max_len=60)
        self.descripcion = area_texto(alto=76)
        self.estatus = combo([("Activa", True), ("Inactiva", False)])
        self.c_nombre = Campo("Nombre *", self.nombre)
        self.c_estatus = Campo("Estatus", self.estatus)
        self.form = Card("Nueva categoría").agregar(
            self.c_nombre, Campo("Descripción", self.descripcion), self.c_estatus,
            hbox(boton("Guardar", "primario", self._guardar), boton("Cancelar", "texto", lambda: self.form.setVisible(False)),
                 "stretch"))
        self.form.setFixedWidth(320)
        self.form.setVisible(False)
        self.agregar(columnas(izq, self.form, proporciones=[1, 0]))
        self.terminar()
        self._cargar()

    def _cargar(self, *_):
        filas = self.intentar(self.ctx.datos.lista_categorias, self.buscar.text().strip()) or []
        puede = self.ctx.sesion.puede("inventario", "editar")
        tonos = {i: "guinda" for i, c in enumerate(filas) if self.editando and c["id"] == self.editando["id"]}
        self.tabla.poner_filas(
            [[Celda(c["nombre"], True), c["descripcion"], str(c["productos"]),
              Badge("Activa" if c["activa"] else "Inactiva", "verde" if c["activa"] else "gris"),
              boton_icono("lapiz", "Editar", lambda c=c: self._editar(c)) if puede else ""] for c in filas],
            tonos=tonos)

    def _nueva(self) -> None:
        self.editando = None
        self.form.titulo_lbl.setText("Nueva categoría")
        self.nombre.clear()
        self.descripcion.clear()
        self.estatus.setCurrentIndex(0)
        self.c_estatus.setVisible(False)
        self.c_nombre.error(None)
        self.form.setVisible(True)
        self.nombre.setFocus()
        self._cargar()

    def _editar(self, c: dict) -> None:
        self.editando = c
        self.form.titulo_lbl.setText("Editar categoría")
        self.nombre.setText(c["nombre"])
        self.descripcion.setPlainText(c["descripcion"])
        self.estatus.setCurrentIndex(0 if c["activa"] else 1)
        self.c_estatus.setVisible(True)
        self.c_nombre.error(None)
        self.c_estatus.error(None)
        self.form.setVisible(True)
        self._cargar()

    def _guardar(self) -> None:
        if self.c_nombre.error(error_obligatorio(self.nombre.text(), "El nombre", 60)):
            return
        datos = dict(nombre=self.nombre.text().strip(), descripcion=self.descripcion.toPlainText().strip(),
                     activa=self.estatus.currentData())
        if self.editando:
            datos["id"] = self.editando["id"]
        try:
            self.intentar(self.ctx.datos.guardar_categoria, datos, mostrar_dialogo=False)
        except ErrorNegocio as exc:
            (self.c_estatus if exc.campo == "estatus" else self.c_nombre).error(exc.mensaje)
            return
        if self.aviso.isVisible():
            return
        self.editando = None
        self.form.setVisible(False)
        self._cargar()
