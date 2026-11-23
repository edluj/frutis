"""FIN-04 · Clientes de crédito (HU-39, SC-03)."""
from PySide6.QtCore import Qt

from app import formato as fmt
from app.datos import ErrorNegocio
from app.theme import C
from app.validaciones import error_obligatorio, monto_positivo
from app.views.base import Contexto, PaginaBase
from app.widgets import (
    Badge, Barra, Campo, Card, Celda, Col, Tabla, boton, combo, entrada, etiqueta, hbox, rejilla,
)

ESTATUS = ["Activo", "Suspendido"]
_TONO = {"Activo": "verde", "Pago vencido": "rojo", "Suspendido": "gris"}


class ClientesCreditoView(PaginaBase):
    def __init__(self, ctx: Contexto):
        super().__init__(ctx, "Finanzas", "Clientes de crédito",
                         acciones=[boton("Cuentas por cobrar", "secundario", lambda: ctx.navegar("fin.cxc"))])
        self.editando: dict | None = None
        self.buscar = entrada(placeholder="Nombre del cliente")
        self.buscar.textChanged.connect(self._cargar)
        self.estatus = combo(["Todos", "Activo", "Pago vencido", "Suspendido"])
        self.estatus.currentIndexChanged.connect(self._cargar)
        nuevo = boton("+ Nuevo cliente de crédito", "primario", self._nuevo)
        nuevo.setVisible(ctx.sesion.puede("finanzas", "crear"))
        self.tabla = Tabla([Col("Cliente", estirar=True), Col("Teléfono"), Col("Límite", "der"), Col("Debe", "der"),
                            Col("Uso del crédito", ancho=190), Col("Días", "der"), Col("Estatus"), Col("")])
        self.tabla.fila_elegida.connect(self._editar_fila)
        self.agregar(Card().agregar(
            hbox((Campo("Buscar cliente", self.buscar), 2), (Campo("Estatus", self.estatus), 1), nuevo,
                 alinear=Qt.AlignmentFlag.AlignBottom), self.tabla))

        self.nombre = entrada(max_len=150)
        self.telefono = entrada(max_len=20)
        self.limite = entrada(placeholder="$0.00")
        self.dias = entrada(max_len=3)
        fiscales = self.intentar(ctx.datos.lista_clientes_fiscales) or []
        self.fiscal = combo([("Sin datos fiscales", None)] + [(f"{c['razon_social']} · {c['rfc']}", c["rfc"]) for c in fiscales])
        self.estatus_form = combo(ESTATUS)
        self.campos = {"nombre": Campo("Nombre o razón social *", self.nombre), "telefono": Campo("Teléfono *", self.telefono),
                       "limite": Campo("Límite de crédito *", self.limite), "dias": Campo("Días de crédito *", self.dias),
                       "estatus": Campo("Estatus", self.estatus_form, "Un cliente suspendido no puede comprar a crédito.")}
        c = self.campos
        self.form = Card("Nuevo cliente de crédito").agregar(
            rejilla([[(c["nombre"], 2), c["telefono"], c["limite"], c["dias"]],
                     [(Campo("Datos fiscales (opcional)", self.fiscal), 3), (c["estatus"], 2)]]),
            hbox(boton("Guardar", "primario", self._guardar), boton("Cancelar", "texto", lambda: self.form.setVisible(False)),
                 "stretch"))
        self.form.setVisible(False)
        self.agregar(self.form)
        self.terminar()
        self._cargar()

    def _cargar(self, *_):
        filas = self.intentar(self.ctx.datos.lista_clientes_credito, self.buscar.text().strip(),
                              self.estatus.currentText()) or []
        salida = []
        for c in filas:
            uso = hbox(Barra(c["uso"], C.ROJO if c["uso"] >= 0.9 else C.VERDE, ancho_min=90),
                       etiqueta(fmt.porcentaje(c["uso"] * 100, 0), "Muted"), espacio=8)
            salida.append([Celda(c["nombre"], True), c["telefono"], fmt.dinero(c["limite"]), fmt.dinero(c["debe"]), uso, str(c["dias"]),
                           Badge(c["estatus_vista"], _TONO.get(c["estatus_vista"], "gris")),
                           boton("Estado de cuenta", "link", lambda c=c: self.ctx.navegar("fin.estado", id_cliente=c["id"]))])
        self.tabla.poner_filas(salida, datos=filas)

    def _editar_fila(self, fila: int) -> None:
        c = self.tabla.dato(fila)
        if c and self.ctx.sesion.puede("finanzas", "editar"):
            self._editar(c)

    def _nuevo(self) -> None:
        self.editando = None
        self.form.titulo_lbl.setText("Nuevo cliente de crédito")
        for w in (self.nombre, self.telefono, self.limite, self.dias):
            w.clear()
        self.dias.setText("15")
        self.fiscal.setCurrentIndex(0)
        self.estatus_form.setCurrentIndex(0)
        for campo in self.campos.values():
            campo.error(None)
        self.form.setVisible(True)
        self.nombre.setFocus()

    def _editar(self, c: dict) -> None:
        self.editando = c
        self.form.titulo_lbl.setText(f"Editar · {c['nombre']}")
        self.nombre.setText(c["nombre"])
        self.telefono.setText(c["telefono"])
        self.limite.setText(f"{c['limite']:,.2f}")
        self.dias.setText(str(c["dias"]))
        self.fiscal.setCurrentIndex(max(0, self.fiscal.findData(c["fiscal"])))
        self.estatus_form.setCurrentText(c["estatus"])
        for campo in self.campos.values():
            campo.error(None)
        self.form.setVisible(True)

    def _guardar(self) -> None:
        limite, err_limite = monto_positivo(self.limite.text(), "El límite de crédito debe ser mayor a 0.")
        dias_ok = self.dias.text().strip().isdigit() and int(self.dias.text()) > 0
        errores = {"nombre": error_obligatorio(self.nombre.text(), "El nombre", 150),
                   "telefono": error_obligatorio(self.telefono.text(), "El teléfono"),
                   "limite": err_limite, "dias": None if dias_ok else "Los días de crédito son obligatorios."}
        if any([self.campos[k].error(v) for k, v in errores.items()]):
            return
        datos = dict(nombre=self.nombre.text().strip(), telefono=self.telefono.text().strip(), limite=limite,
                     dias=int(self.dias.text()), fiscal=self.fiscal.currentData(), estatus=self.estatus_form.currentText())
        if self.editando:
            datos["id"] = self.editando["id"]
        try:
            self.intentar(self.ctx.datos.guardar_cliente_credito, datos, mostrar_dialogo=False)
        except ErrorNegocio as exc:
            self.campos.get(exc.campo or "nombre", self.campos["nombre"]).error(exc.mensaje)
            return
        if self.aviso.isVisible():
            return
        self.form.setVisible(False)
        self._cargar()
