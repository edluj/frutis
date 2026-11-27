"""ADM-01 · Usuarios del sistema (flujo T, HU-18)."""
from PySide6.QtCore import Qt

from app.datos import ErrorNegocio
from app.validaciones import error_correo, error_obligatorio, error_usuario
from app.views.base import Contexto, PaginaBase
from app.widgets import (
    Badge, Campo, Card, Celda, Col, Tabla, boton, boton_icono, combo, entrada, etiqueta, hbox, rejilla,
)


def _acceso(d, hoy) -> str:
    if d is None:
        return "Nunca"
    return f"Hoy {d:%H:%M}" if d.date() == hoy else f"{d:%d/%m %H:%M}"


class UsuariosView(PaginaBase):
    def __init__(self, ctx: Contexto):
        super().__init__(ctx, "Administración", "Usuarios",
                         acciones=[boton("Roles y permisos", "secundario", lambda: ctx.navegar("adm.roles"))])
        self.editando: dict | None = None
        from datetime import date
        self.hoy = date(2026, 11, 2) if ctx.datos.es_demo else date.today()
        roles = self.intentar(ctx.datos.nombres_roles) or []
        self.buscar = entrada(placeholder="Nombre o usuario")
        self.buscar.textChanged.connect(self._cargar)
        self.rol = combo(["Todos"] + roles)
        self.rol.currentIndexChanged.connect(self._cargar)
        nuevo = boton("+ Nuevo usuario", "primario", self._nuevo)
        nuevo.setVisible(ctx.sesion.puede("admin", "crear"))
        self.tabla = Tabla([Col("Nombre"), Col("Usuario"), Col("Correo", estirar=True), Col("Rol"), Col("Último acceso"),
                            Col("Estatus"), Col("", "centro", ancho=70)])
        self.agregar(Card().agregar(hbox((Campo("Buscar por nombre o usuario", self.buscar), 2), (Campo("Rol", self.rol), 1),
                                         nuevo, alinear=Qt.AlignmentFlag.AlignBottom), self.tabla))

        self.nombre = entrada(max_len=150)
        self.usuario = entrada(max_len=50)
        self.correo = entrada(max_len=120)
        self.password = entrada(password=True, max_len=128)
        self.rol_form = combo(roles)
        self.estatus = combo([("Activo", True), ("Inactivo", False)])
        self.campos = {
            "nombre": Campo("Nombre completo *", self.nombre, "Máximo 150 caracteres."),
            "usuario": Campo("Usuario *", self.usuario), "correo": Campo("Correo *", self.correo),
            "password": Campo("Contraseña temporal *", self.password, "Se guarda cifrada. Se pide cambiarla al primer inicio."),
            "rol": Campo("Rol *", self.rol_form), "estatus": Campo("Estatus", self.estatus),
        }
        c = self.campos
        self.form = Card("Nuevo usuario").agregar(
            rejilla([[(c["nombre"], 2), c["usuario"], (c["correo"], 2)], [(c["password"], 2), (c["rol"], 2), c["estatus"]]]),
            hbox(boton("Guardar", "primario", self._guardar), boton("Cancelar", "texto", lambda: self.form.setVisible(False)),
                 "stretch"))
        self.form.setVisible(False)
        self.agregar(self.form)
        self.terminar()
        self._cargar()

    def _cargar(self, *_):
        filas = self.intentar(self.ctx.datos.lista_usuarios, self.buscar.text().strip(), self.rol.currentText()) or []
        puede = self.ctx.sesion.puede("admin", "editar")
        salida = []
        for u in filas:
            yo = u["id"] == self.ctx.sesion.id_usuario
            accion = etiqueta("Tú", "Muted") if yo else (boton_icono("lapiz", "Editar", lambda u=u: self._editar(u)) if puede else "")
            salida.append([Celda(u["nombre"], True), u["usuario"], u["correo"],
                           Badge(u["rol"], "guinda" if u["rol"] == "Administrador" else "gris"), _acceso(u["ultimo"], self.hoy),
                           Badge("Activo" if u["activo"] else "Inactivo", "verde" if u["activo"] else "gris"), accion])
        self.tabla.poner_filas(salida)

    def _nuevo(self) -> None:
        self.editando = None
        self.form.titulo_lbl.setText("Nuevo usuario")
        for w in (self.nombre, self.usuario, self.correo, self.password):
            w.clear()
        self.usuario.setEnabled(True)
        self.campos["password"].lbl.setText("Contraseña temporal *")
        for campo in self.campos.values():
            campo.error(None)
        self.form.setVisible(True)
        self.nombre.setFocus()

    def _editar(self, u: dict) -> None:
        self.editando = u
        self.form.titulo_lbl.setText(f"Editar · {u['nombre']}")
        self.nombre.setText(u["nombre"])
        self.usuario.setText(u["usuario"])
        self.usuario.setEnabled(False)
        self.correo.setText(u["correo"])
        self.password.clear()
        self.campos["password"].lbl.setText("Contraseña temporal (vacío = no cambia)")
        self.rol_form.setCurrentText(u["rol"])
        self.estatus.setCurrentIndex(0 if u["activo"] else 1)
        for campo in self.campos.values():
            campo.error(None)
        self.form.setVisible(True)

    def _guardar(self) -> None:
        pw = self.password.text()
        err_pw = None
        if not self.editando or pw:
            err_pw = "La contraseña temporal es obligatoria." if not pw else \
                "Usa al menos 8 caracteres." if len(pw) < 8 else None
        errores = {"nombre": error_obligatorio(self.nombre.text(), "El nombre", 150),
                   "usuario": error_usuario(self.usuario.text()), "correo": error_correo(self.correo.text()),
                   "password": err_pw}
        if any([self.campos[k].error(v) for k, v in errores.items()]):
            return
        datos = dict(nombre=self.nombre.text().strip(), usuario=self.usuario.text().strip(), correo=self.correo.text().strip(),
                     password=pw, rol=self.rol_form.currentText(), activo=self.estatus.currentData())
        if self.editando:
            datos["id"] = self.editando["id"]
        try:
            self.intentar(self.ctx.datos.guardar_usuario, datos, mostrar_dialogo=False)
        except ErrorNegocio as exc:
            self.campos.get(exc.campo or "nombre", self.campos["nombre"]).error(exc.mensaje)
            return
        finally:
            self.password.clear()
        if self.aviso.isVisible():
            return
        self.form.setVisible(False)
        self._cargar()
