"""ADM-02 · Roles y matriz de permisos ver/crear/editar/eliminar (flujo U, HU-34)."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QButtonGroup, QCheckBox, QFrame, QInputDialog, QLabel, QPushButton, QVBoxLayout

from app.datos import ErrorNegocio
from app.sesion import MODULOS
from app.theme import C
from app.views.base import Contexto, PaginaBase
from app.widgets import (
    Badge, Card, Celda, Col, Tabla, avisar, boton, casilla, columnas, etiqueta, hbox, limpiar,
)

ACCIONES = ["ver", "crear", "editar", "eliminar"]
ESPECIALES = [("credito", "Vender a crédito a clientes autorizados"), ("devoluciones", "Autorizar devoluciones"),
              ("cortes", "Ver el corte de todas las cajas")]


class RolesView(PaginaBase):
    def __init__(self, ctx: Contexto):
        super().__init__(ctx, "Administración", "Roles y permisos",
                         acciones=[boton("Usuarios", "secundario", lambda: ctx.navegar("adm.usuarios"))])
        self.rol = "Cajero"
        self.checks: dict[str, list[QCheckBox]] = {}
        self.especiales: dict[str, QCheckBox] = {}
        self.menu = Card("Roles", margen=16, espacio=4)
        self.menu.setFixedWidth(250)
        self.lista_roles = QVBoxLayout()
        self.lista_roles.setSpacing(4)
        self.menu.agregar(self.lista_roles)
        if ctx.sesion.puede("admin", "crear"):
            self.menu.agregar(boton("+ Nuevo rol", "texto", self._nuevo_rol))
        self.panel = Card("Permisos del rol")
        self.tabla = Tabla([Col("Módulo", estirar=True)] + [Col(a.capitalize(), "centro", ancho=100) for a in ACCIONES])
        caja = QFrame()
        caja.setStyleSheet(f"QFrame#Especiales {{ background: {C.CREMA}; border-radius: 10px; }}")
        caja.setObjectName("Especiales")
        self.lay_esp = QVBoxLayout(caja)
        self.lay_esp.setContentsMargins(16, 14, 16, 14)
        self.lay_esp.setSpacing(10)
        self.btn_guardar = boton("Guardar permisos", "primario", self._guardar)
        self.nota = etiqueta("Aplican desde el siguiente inicio de sesión.", "Muted")
        self.panel.agregar(self.tabla, caja, hbox(self.btn_guardar, self.nota, "stretch"))
        self.agregar(columnas(self.menu, self.panel, proporciones=[0, 1]))
        self.terminar()
        self._pintar_roles()
        self._cargar()

    def _pintar_roles(self) -> None:
        limpiar(self.lista_roles)
        grupo = QButtonGroup(self)
        for r in self.intentar(self.ctx.datos.roles) or []:
            b = QPushButton()
            b.setCheckable(True)
            b.setChecked(r["nombre"] == self.rol)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setMinimumHeight(44)
            b.setStyleSheet("QPushButton { background: transparent; border: none; border-radius: 8px; text-align: left; }"
                            f"QPushButton:checked {{ background: {C.GUINDA_SUAVE}; }}"
                            f"QPushButton:hover {{ background: {C.FONDO}; }}")
            fila = hbox(etiqueta(r["nombre"]), "stretch",
                        Badge(("Fijo · " if r["fijo"] else "") + (f"{r['usuarios']} usuario{'s' if r['usuarios'] != 1 else ''}"
                                                                   if b.isChecked() else str(r["usuarios"])),
                              "guinda" if b.isChecked() else "gris"), espacio=6)
            fila.setContentsMargins(10, 0, 10, 0)
            for i in range(fila.count()):
                w = fila.itemAt(i).widget()
                if w:
                    w.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
                    if b.isChecked() and isinstance(w, QLabel) and not isinstance(w, Badge):
                        w.setStyleSheet(f"color: {C.GUINDA}; font-weight: 800;")
            b.setLayout(fila)
            b.clicked.connect(lambda _=False, n=r["nombre"]: self._elegir(n))
            grupo.addButton(b)
            self.lista_roles.addWidget(b)

    def _elegir(self, rol: str) -> None:
        self.rol = rol
        self._pintar_roles()
        self._cargar()

    def _cargar(self) -> None:
        p = self.intentar(self.ctx.datos.permisos_de, self.rol)
        if not p:
            return
        fijo = self.rol == "Administrador"
        editable = not fijo and self.ctx.sesion.puede("admin", "editar")
        self.panel.titulo_lbl.setText(f"Permisos del rol {self.rol}" + (" · fijo, no se edita" if fijo else ""))
        self.checks.clear()
        filas = []
        for clave, nombre, _ in MODULOS:
            valores = p["matriz"][clave]
            cbs = []
            for v in valores:
                cb = casilla("", bool(v))
                cb.setEnabled(editable)
                cbs.append(cb)
            # "Ver" es requisito de las demás acciones.
            for cb in cbs[1:]:
                cb.toggled.connect(lambda on, ver=cbs[0]: on and ver.setChecked(True))
            cbs[0].toggled.connect(lambda on, otros=cbs[1:]: not on and [o.setChecked(False) for o in otros])
            self.checks[clave] = cbs
            filas.append([Celda(nombre, True)] + cbs)
        self.tabla.poner_filas(filas)
        limpiar(self.lay_esp)
        self.lay_esp.addWidget(etiqueta("Permisos especiales", "Etiqueta"))
        self.especiales.clear()
        for clave, texto_ in ESPECIALES:
            cb = casilla(texto_, p["especiales"].get(clave, False) or (fijo and True))
            if clave == "devoluciones":
                # SC-02: solo el Administrador autoriza devoluciones (también lo exige un trigger en la base).
                cb.setChecked(fijo)
                cb.setEnabled(False)
                self.lay_esp.addLayout(hbox(cb, Badge("Solo Administrador", "gris"), "stretch", espacio=12))
            else:
                cb.setEnabled(editable)
                self.lay_esp.addWidget(cb)
            self.especiales[clave] = cb
        self.btn_guardar.setVisible(editable)
        self.nota.setVisible(editable)

    def _guardar(self) -> None:
        matriz = {m: tuple(int(cb.isChecked()) for cb in cbs) for m, cbs in self.checks.items()}
        especiales = {k: cb.isChecked() for k, cb in self.especiales.items()}
        try:
            self.intentar(self.ctx.datos.guardar_permisos, self.rol, matriz, especiales, mostrar_dialogo=False)
        except ErrorNegocio as exc:
            avisar(self, "Permisos", exc.mensaje, error=True)
            return
        if not self.aviso.isVisible():
            avisar(self, "Permisos guardados", f"Los permisos del rol {self.rol} aplican desde el siguiente inicio de sesión.")
            self._pintar_roles()

    def _nuevo_rol(self) -> None:
        nombre, ok = QInputDialog.getText(self, "Nuevo rol", "Nombre del rol:")
        nombre = nombre.strip()
        if not ok or not nombre:
            return
        try:
            self.intentar(self.ctx.datos.crear_rol, nombre, mostrar_dialogo=False)
        except ErrorNegocio as exc:
            avisar(self, "Nuevo rol", exc.mensaje, error=True)
            return
        self.rol = nombre
        self._pintar_roles()
        self._cargar()
