"""PRV-01 · Proveedores: consulta, alta y edición (flujo F, HU-23)."""

from app import formato as fmt
from app.datos import ErrorNegocio
from app.validaciones import error_correo, error_obligatorio, error_rfc
from app.views.base import Contexto, PaginaBase
from app.widgets import Badge, Campo, Card, Col, Tabla, boton, boton_icono, combo, entrada, hbox, rejilla


class ProveedoresView(PaginaBase):
    def __init__(self, ctx: Contexto):
        acciones = [boton("Registrar lote", "primario", lambda: ctx.navegar("compras.lote_nuevo"))] \
            if ctx.sesion.puede("compras", "crear") else []
        super().__init__(ctx, "Proveedores y Compras", "Proveedores", acciones=acciones)
        self.editando: dict | None = None

        self.buscar = entrada(placeholder="Ej. Hortalizas o HVA010203AB1")
        self.buscar.textChanged.connect(self._cargar)
        self.estatus = combo(["Activos", "Inactivos", "Todos"])
        self.estatus.currentIndexChanged.connect(self._cargar)
        nuevo = boton("+ Nuevo proveedor", "primario", self._nuevo)
        nuevo.setVisible(ctx.sesion.puede("compras", "crear"))
        self.tabla = Tabla([Col("Razón social", estirar=True), Col("RFC"), Col("Teléfono"), Col("Días de crédito", "der"),
                            Col("Saldo por pagar", "der"), Col("Estatus"), Col("Acciones", ancho=110)])
        self.agregar(Card().agregar(
            hbox((Campo("Buscar por nombre o RFC", self.buscar), 3), (Campo("Estatus", self.estatus), 1), nuevo,
                 alinear=_abajo()), self.tabla))

        # Formulario de alta / edición
        self.razon = entrada(max_len=150)
        self.rfc = entrada(max_len=13)
        self.telefono = entrada(max_len=20)
        self.correo = entrada(max_len=120)
        self.dias = entrada("15", max_len=3)
        self.direccion = entrada(max_len=200)
        self.estatus_form = combo([("Activo", True), ("Inactivo", False)])
        self.campos = {
            "razon": Campo("Razón social *", self.razon), "rfc": Campo("RFC *", self.rfc),
            "telefono": Campo("Teléfono *", self.telefono), "correo": Campo("Correo", self.correo),
            "dias": Campo("Días de crédito *", self.dias), "direccion": Campo("Dirección", self.direccion),
            "estatus": Campo("Estatus", self.estatus_form),
        }
        c = self.campos
        self.form = Card("Alta de proveedor")
        self.form.agregar(rejilla([[(c["razon"], 2), c["rfc"], c["telefono"]],
                                   [c["correo"], c["dias"], (c["direccion"], 2)], [c["estatus"]]]),
                          hbox(boton("Guardar", "primario", self._guardar), boton("Cancelar", "texto", self._cerrar_form), "stretch"))
        self.form.setVisible(False)
        self.agregar(self.form)
        self.terminar()
        self._cargar()

    def _cargar(self, *_):
        filas = self.intentar(self.ctx.datos.lista_proveedores, self.buscar.text().strip(), self.estatus.currentText()) or []
        puede_editar = self.ctx.sesion.puede("compras", "editar")
        self.tabla.poner_filas([
            [_negrita(p["razon_social"]), p["rfc"], p["telefono"], str(p["dias_credito"]), fmt.dinero(p["saldo"]),
             Badge("Activo" if p["activo"] else "Inactivo", "verde" if p["activo"] else "gris"),
             hbox(boton_icono("documento", "Estado de cuenta", lambda p=p: self.ctx.navegar("compras.estado", id_proveedor=p["id"])),
                  boton_icono("lapiz", "Editar", lambda p=p: self._editar(p)) if puede_editar else None, espacio=6)]
            for p in filas], datos=filas)

    def _nuevo(self) -> None:
        self.editando = None
        self.form.titulo_lbl.setText("Alta de proveedor")
        for w in (self.razon, self.rfc, self.telefono, self.correo, self.direccion):
            w.clear()
        self.dias.setText("15")
        self.campos["estatus"].setVisible(False)
        self._limpiar_errores()
        self.form.setVisible(True)
        self.razon.setFocus()

    def _editar(self, p: dict) -> None:
        self.editando = p
        self.form.titulo_lbl.setText(f"Editar · {p['razon_social']}")
        self.razon.setText(p["razon_social"])
        self.rfc.setText(p["rfc"])
        self.telefono.setText(p["telefono"])
        self.correo.setText(p["correo"])
        self.dias.setText(str(p["dias_credito"]))
        self.direccion.setText(p["direccion"])
        self.estatus_form.setCurrentIndex(0 if p["activo"] else 1)
        self.campos["estatus"].setVisible(True)
        self._limpiar_errores()
        self.form.setVisible(True)

    def _cerrar_form(self) -> None:
        self.form.setVisible(False)

    def _limpiar_errores(self) -> None:
        for campo in self.campos.values():
            campo.error(None)

    def _guardar(self) -> None:
        self._limpiar_errores()
        rfc = self.rfc.text().strip().upper()
        errores = {
            "razon": error_obligatorio(self.razon.text(), "La razón social", 150),
            "rfc": error_rfc(rfc),
            "telefono": error_obligatorio(self.telefono.text(), "El teléfono"),
            "correo": error_correo(self.correo.text(), obligatorio=False),
            "dias": None if self.dias.text().strip().isdigit() else "Escribe los días de crédito (0 si es de contado).",
        }
        hay = [self.campos[k].error(v) for k, v in errores.items()]
        if any(hay):
            return
        datos = dict(razon_social=self.razon.text().strip(), rfc=rfc, telefono=self.telefono.text().strip(),
                     correo=self.correo.text().strip(), dias_credito=int(self.dias.text()), direccion=self.direccion.text().strip())
        if self.editando:
            datos.update(id=self.editando["id"], activo=self.estatus_form.currentData())
        try:
            ok = self.intentar(self.ctx.datos.guardar_proveedor, datos, mostrar_dialogo=False)
        except ErrorNegocio as exc:
            self.campos.get(exc.campo or "", self.campos["razon"]).error(exc.mensaje)
            return
        if ok is None and self.aviso.isVisible():
            return
        self.form.setVisible(False)
        self._cargar()


def _negrita(texto_: str):
    from app.widgets import Celda
    return Celda(texto_, negrita=True)


def _abajo():
    from PySide6.QtCore import Qt
    return Qt.AlignmentFlag.AlignBottom
