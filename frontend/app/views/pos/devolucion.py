"""POS-04 · Devolución parcial o total a partir del ticket (flujo E, HU-30, SC-02)."""
from decimal import Decimal

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox, QComboBox, QLineEdit

from app import formato as fmt
from app.datos import ErrorNegocio
from app.theme import C
from app.validaciones import cantidad_positiva
from app.views.base import Contexto, PaginaBase
from app.widgets import (
    Alerta, Badge, Campo, Card, Celda, Col, Tabla, avisar, boton, casilla, columnas, combo, confirmar, entrada, etiqueta, hbox, rejilla,
)

MOTIVOS = ["Producto en mal estado", "Producto equivocado", "Cobro incorrecto", "El cliente cambió de opinión"]
REEMBOLSOS = ["Efectivo (sale de la caja)", "Reverso a tarjeta", "Transferencia", "Abono a crédito"]
ESTADOS = [("Buen estado", True), ("Mal estado · merma", False)]


class DevolucionView(PaginaBase):
    def __init__(self, ctx: Contexto):
        super().__init__(ctx, "Punto de Venta", "Devolución", estado=ctx.datos.estado_conexion(),
                         punto=C.NARANJA if ctx.datos.es_demo else C.VERDE)
        self.ticket: dict | None = None
        self.autorizado_por: str | None = None
        self.filas: list[tuple[QCheckBox, QLineEdit, QComboBox, dict]] = []

        self.folio = entrada(placeholder="V00001031", max_len=12)
        self.folio.setAccessibleName("Número de ticket")
        self.folio.setFixedWidth(240)
        self.folio.returnPressed.connect(self._buscar)
        self.campo_folio = Campo("Número de ticket", self.folio)
        self.info = hbox(espacio=18)
        busq = Card(margen=16).agregar(hbox(self.campo_folio, boton("Buscar", "secundario", self._buscar), "stretch",
                                            self.info, alinear=Qt.AlignmentFlag.AlignBottom))
        self.agregar(busq)

        self.tabla = Tabla([Col("", "centro", ancho=44), Col("Producto", estirar=True), Col("Vendido", "der", ancho=92),
                            Col("A devolver", "der", ancho=130), Col("Estado del producto", ancho=200),
                            Col("Importe", "der", ancho=90)], alto_fila=52)
        self.motivo = combo(MOTIVOS)
        self.reembolso = combo(REEMBOLSOS)
        self.vacio = etiqueta("Busca el ticket para ver sus productos.", "Muted")
        izq = Card("Productos del ticket").agregar(
            self.vacio, self.tabla, rejilla([[Campo("Motivo", self.motivo), Campo("Forma de reembolso", self.reembolso)]]))
        self.tabla.setVisible(False)

        admins = self.intentar(ctx.datos.administradores) or []
        self.admin = combo(admins)
        self.pass_admin = entrada(password=True, placeholder="Contraseña", max_len=128)
        self.pass_admin.setAccessibleName("Contraseña del Administrador")
        self.pass_admin.returnPressed.connect(self._autorizar)
        self.campo_pass = Campo("Contraseña del Administrador", self.pass_admin)
        self.estado_aut = Alerta("", "verde")
        self.estado_aut.setVisible(False)
        self.btn_autorizar = boton("Autorizar", "secundario", self._autorizar)
        self.btn_procesar = boton("Procesar devolución", "primario", self._procesar)
        self.btn_procesar.setMinimumHeight(48)
        self.btn_procesar.setEnabled(False)
        der = Card("Autorización del Administrador").agregar(
            etiqueta("Solo un usuario con rol Administrador puede autorizar devoluciones. Lo que está en mal "
                     "estado se registra como merma; lo que está en buen estado regresa al inventario.", "Muted", ajustar=True),
            Campo("Administrador", self.admin), self.campo_pass, self.btn_autorizar, self.estado_aut,
            self.btn_procesar, boton("Cancelar", "texto", self._limpiar))
        der.setFixedWidth(310)
        self.agregar(columnas(izq, der, proporciones=[1, 0]))
        self.terminar()

    def al_mostrar(self, **params):
        if params.get("folio"):
            self.folio.setText(params["folio"])
            self._buscar()
        self.folio.setFocus()

    # ------------------------------------------------------------ ticket
    def _buscar(self) -> None:
        folio = self.folio.text().strip().upper()
        if not folio:
            self.campo_folio.error("Escribe el número de ticket.")
            return
        try:
            t = self.intentar(self.ctx.datos.buscar_ticket, folio, mostrar_dialogo=False)
        except ErrorNegocio as exc:
            self.campo_folio.error(exc.mensaje)
            return
        if t is None:
            return
        self.ticket = t
        while self.info.count():
            w = self.info.takeAt(0).widget()
            if w:
                w.deleteLater()
        for txt in (fmt.fecha_hora(t["fecha"]), t["metodo"], f"Total {fmt.dinero(t['total'])}"):
            self.info.addWidget(etiqueta(txt, "Muted"))
        self.info.addWidget(Badge("Facturado" if t["facturado"] else "Sin factura", "naranja" if t["facturado"] else "gris"))
        self._pintar()

    def _pintar(self) -> None:
        self.filas.clear()
        filas = []
        for r in self.ticket["renglones"]:
            disponible = r["cantidad"] - r["devuelto"]
            cb = casilla("")
            cb.setEnabled(disponible > 0)
            cb.setAccessibleName(f"Devolver {r['nombre']}")
            cant = entrada(alinear_derecha=True, compacto=True)
            cant.setFixedWidth(76)
            cant.setEnabled(False)
            cant.setAccessibleName(f"Cantidad a devolver de {r['nombre']}")
            estado = combo([e for e in ESTADOS], compacto=True)
            estado.setEnabled(False)
            cb.toggled.connect(lambda on, c=cant, e=estado, d=disponible, u=r["unidad"]: self._marcar(on, c, e, d, u))
            cant.textChanged.connect(self._total)
            unidad = "kg" if r["unidad"] == "kg" else "pza"
            vendido = fmt.cantidad(r["cantidad"], r["unidad"])
            if r["devuelto"] > 0:
                vendido += f"\n({fmt.cantidad(r['devuelto'], r['unidad'])} devuelto)"
            filas.append([cb, Celda(r["nombre"]), vendido, hbox(cant, etiqueta(unidad, "Muted"), espacio=6), estado, "—"])
            self.filas.append((cb, cant, estado, r))
        self.tabla.poner_filas(filas, total=["", Celda("Total a devolver", True), "", "", "", Celda("$0.00", True)])
        self.tabla.setVisible(True)
        self.vacio.setVisible(False)
        self._total()

    def _marcar(self, on: bool, cant: QLineEdit, estado: QComboBox, disponible: Decimal, unidad: str) -> None:
        cant.setEnabled(on)
        estado.setEnabled(on)
        cant.setText((f"{disponible:.3f}" if unidad == "kg" else f"{disponible:.0f}") if on else "")
        if on and self.motivo.currentText() == "Producto en mal estado":
            estado.setCurrentIndex(1)
        self._total()

    def _seleccion(self) -> tuple[list[dict], str | None]:
        salida = []
        for cb, cant, estado, r in self.filas:
            if not cb.isChecked():
                continue
            q = cantidad_positiva(cant.text(), 3 if r["unidad"] == "kg" else 0)
            if q is None or q > r["cantidad"] - r["devuelto"]:
                return [], f"La cantidad a devolver de {r['nombre']} no es válida."
            salida.append(dict(id_producto=r["id_producto"], cantidad=q, buen_estado=estado.currentData(),
                               importe=(r["precio"] * q).quantize(Decimal("0.01"))))
        return salida, None

    def _total(self, *_):
        total = Decimal("0")
        for i, (cb, cant, _e, r) in enumerate(self.filas):
            q = cantidad_positiva(cant.text()) if cb.isChecked() else None
            imp = (r["precio"] * q).quantize(Decimal("0.01")) if q else None
            self.tabla.item(i, 5).setText(fmt.dinero(imp) if imp else "—")
            total += imp or 0
        self.tabla.item(len(self.filas), 5).setText(fmt.dinero(total))
        self._habilitar()

    # ------------------------------------------------------------ autorización
    def _autorizar(self) -> None:
        if not self.pass_admin.text():
            self.campo_pass.error("Escribe la contraseña del Administrador.")
            return
        try:
            msg = self.intentar(self.ctx.datos.autorizar, self.admin.currentText(), self.pass_admin.text(),
                                mostrar_dialogo=False)
        except ErrorNegocio as exc:
            self.campo_pass.error(exc.mensaje)
            return
        finally:
            self.pass_admin.clear()
        if msg:
            self.autorizado_por = self.admin.currentText()
            self.estado_aut.mostrar(msg, "verde")
            self.admin.setEnabled(False)
            self.pass_admin.setEnabled(False)
            self.btn_autorizar.setVisible(False)
        self._habilitar()

    def _habilitar(self) -> None:
        sel, _ = self._seleccion()
        self.btn_procesar.setEnabled(bool(self.autorizado_por and sel))

    def _procesar(self) -> None:
        sel, error = self._seleccion()
        if error or not sel:
            avisar(self, "Devolución", error or "Marca al menos un producto.", error=True)
            return
        total = sum((s["importe"] for s in sel), Decimal("0"))
        if not confirmar(self, "Procesar devolución",
                         f"Se devolverán {fmt.dinero(total)} con {self.reembolso.currentText().lower()}.", "Procesar"):
            return
        r = self.intentar(self.ctx.datos.procesar_devolucion, self.ticket["folio"], sel, self.motivo.currentText(),
                          self.reembolso.currentText(), self.autorizado_por)
        if r:
            avisar(self, "Devolución registrada", f"Se devolvieron {fmt.dinero(r['total'])}. "
                   "Lo que estaba en mal estado se registró como merma.")
            self._limpiar()

    def _limpiar(self) -> None:
        self.ctx.navegar("pos.devolucion")
