"""POS-02 · Cobro (flujo C): HU-06, HU-07a, HU-08, HU-16a, HU-36 y HU-38a.

Flujo de 3 toques: tocar el producto (toma el peso de la báscula), elegir el método
de pago y cobrar. El cobro lo registra sp_registrar_venta en una sola transacción.
"""
from decimal import Decimal

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QButtonGroup, QDialog, QFrame, QGridLayout, QInputDialog, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget,
)

from app import formato as fmt
from app.api_client import SesionExpirada
from app.datos import ErrorNegocio, NoConectado
from app.presenters.pos import Carrito, cambio, validar_cobro
from app.theme import C
from app.views.base import Contexto, PaginaBase
from app.widgets import (
    Alerta, Campo, Card, Col, Tabla, boton, boton_icono, combo, confirmar, dato, entrada, etiqueta, hbox, limpiar, texto, vbox,
)


class Bascula(QFrame):
    """Lectura de la báscula (simulador mientras llega el modelo real, HU-07a / R-01)."""

    def __init__(self, al_click):
        super().__init__()
        self.setFixedSize(150, 76)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Toca para capturar el peso a mano (simulador de báscula)")
        self.setStyleSheet(f"QFrame {{ background: {C.VERDE_SUAVE}; border-radius: 10px; }}"
                           f"QLabel {{ background: transparent; color: {C.VERDE_TEXTO}; }}")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(2)
        lay.addWidget(texto("Báscula", 12, QFont.Weight.ExtraBold, C.VERDE_TEXTO))
        self.valor = texto("0.000 kg", 26, QFont.Weight.DemiBold, C.VERDE_TEXTO, titulo=True)
        lay.addWidget(self.valor)
        self.al_click = al_click

    def mostrar(self, peso: Decimal) -> None:
        self.valor.setText(f"{peso:.3f} kg")

    def mousePressEvent(self, _):
        self.al_click()


class TicketDialogo(QDialog):
    """Vista del ticket: lo que imprime la impresora (simulada hasta tener el modelo, HU-16a)."""

    def __init__(self, padre: QWidget, venta: dict, caja: str, cajero: str, reimpresion: bool = False):
        super().__init__(padre)
        self.setWindowTitle("Ticket " + venta["folio"])
        self.setMinimumWidth(460)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 22, 24, 22)
        lay.setSpacing(12)
        if not reimpresion:
            lay.addWidget(Alerta(f"<b>Venta registrada.</b> Ticket {venta['folio']}.", "verde"))
            if venta["cambio"] > 0:
                lay.addWidget(etiqueta("Cambio", "KpiTitulo"))
                grande = texto(fmt.dinero(venta["cambio"]), 44, QFont.Weight.DemiBold, C.VERDE, titulo=True)
                lay.addWidget(grande)
        ticket = QPlainTextEdit(_texto_ticket(venta, caja, cajero, reimpresion))
        ticket.setReadOnly(True)
        ticket.setFont(QFont("Consolas", 11))
        ticket.setMinimumHeight(300)
        lay.addWidget(ticket)
        lay.addWidget(etiqueta("Impresora en modo simulador: el ticket se muestra en pantalla.", "Ayuda"))
        ok = boton("Nueva venta" if not reimpresion else "Cerrar", "primario", self.accept)
        ok.setMinimumHeight(48)
        ok.setDefault(True)
        lay.addWidget(ok)


def _texto_ticket(v: dict, caja: str, cajero: str, reimpresion: bool) -> str:
    ancho = 40
    lineas = ["FRUTERÍA FRUTIS".center(ancho), "Fresco y natural".center(ancho), "",
              f"Ticket {v['folio']}", f"{fmt.fecha_hora(v['fecha'])}  {caja}", f"Cajero: {cajero}", "-" * ancho]
    for r in v["renglones"]:
        lineas.append(r["nombre"][:ancho])
        det = f"  {fmt.cantidad(r['cantidad'], r['unidad'])} x {fmt.dinero(r['precio'])}"
        lineas.append(det + fmt.dinero(r["importe"]).rjust(ancho - len(det)))
    lineas += ["-" * ancho, "TOTAL".ljust(20) + fmt.dinero(v["total"]).rjust(ancho - 20), f"Pago: {v['metodo']}"]
    if v.get("recibido") and v["cambio"] >= 0 and v.get("es_efectivo"):
        lineas += ["Recibido".ljust(20) + fmt.dinero(v["recibido"]).rjust(ancho - 20),
                   "Cambio".ljust(20) + fmt.dinero(v["cambio"]).rjust(ancho - 20)]
    lineas += ["IVA tasa 0 % (frutas y verduras)", "", "¡Gracias por su compra!".center(ancho)]
    if reimpresion:
        lineas.insert(0, "*** REIMPRESIÓN ***".center(ancho))
    return "\n".join(lineas)


class CobroView(PaginaBase):
    persistente = True  # el carrito sobrevive si el cajero consulta otra pantalla

    def __init__(self, ctx: Contexto):
        self.btn_corte = boton("Corte de caja", "secundario", lambda: ctx.navegar("pos.corte"))
        self.btn_devolucion = boton("Devolución", "secundario", lambda: ctx.navegar("pos.devolucion"))
        super().__init__(ctx, "Punto de Venta", "Cobro", estado="", acciones=[self.btn_corte, self.btn_devolucion],
                         punto=C.NARANJA if ctx.datos.es_demo else C.VERDE)
        self.carrito = Carrito()
        self.caja: dict | None = None
        self.metodos: list[dict] = []
        self.metodo: dict | None = None
        self.clientes: list[dict] = []
        self.ultima_venta: dict | None = None
        self.productos: list[dict] = []
        self.peso = Decimal("0")
        self.recibido = None
        self.cliente_combo = None
        self.nombre_metodo = "Efectivo"

        # ---------- columna izquierda: productos y carrito
        self.busqueda = entrada(placeholder="Código de barras o nombre del producto", max_len=120)
        self.busqueda.setAccessibleName("Buscar producto")
        self.busqueda.returnPressed.connect(self._buscar)
        self.busqueda.textEdited.connect(self._filtrar_en_vivo)
        self.campo_busqueda = Campo("Escanea el código o busca por nombre", self.busqueda)
        self.bascula = Bascula(self._capturar_peso)
        self.titulo_rejilla = etiqueta("Productos frecuentes", "Etiqueta")
        self.rejilla = QGridLayout()
        self.rejilla.setSpacing(10)
        tarjeta_productos = Card().agregar(
            hbox((self.campo_busqueda, 1), self.bascula, espacio=12, alinear=Qt.AlignmentFlag.AlignBottom),
            self.titulo_rejilla, self.rejilla)

        self.tabla = Tabla([Col("Producto", estirar=True), Col("Cantidad", "der", ancho=120), Col("Precio", "der", ancho=120),
                            Col("Importe", "der", ancho=110), Col("", "centro", ancho=60)], alto_fila=52)
        self.tabla.cellDoubleClicked.connect(self._editar_cantidad)
        self.vacio = etiqueta("Escanea o toca un producto para agregarlo a la venta.", "Muted")
        self.vacio.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.vacio.setMinimumHeight(80)
        izquierda = vbox(tarjeta_productos, self.tabla, self.vacio, "stretch", espacio=16)

        # ---------- columna derecha: total y pago
        panel = Card(margen=16, espacio=10)
        panel.setFixedWidth(330)
        self.lbl_total_titulo = etiqueta("Total a pagar · 0 productos", "KpiTitulo")
        self.lbl_total = texto("$0.00", 46, QFont.Weight.DemiBold, C.GUINDA, titulo=True)
        panel.agregar(self.lbl_total_titulo, self.lbl_total,
                      etiqueta("Incluye IVA · frutas y verduras tasa 0 %", "Muted"))
        panel.lay.addSpacing(4)
        panel.agregar(etiqueta("Método de pago", "Etiqueta"))
        self.grupo_metodos = QButtonGroup(self)
        self.botones_metodo: dict[str, QPushButton] = {}
        g = QGridLayout()
        g.setSpacing(8)
        for i, nombre in enumerate(["Efectivo", "Tarjeta", "Transferencia", "Crédito"]):
            b = QPushButton(nombre)
            b.setProperty("tipo", "opcion")
            b.setCheckable(True)
            b.setMinimumHeight(48)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, n=nombre: self._elegir_metodo(n))
            self.grupo_metodos.addButton(b)
            self.botones_metodo[nombre] = b
            g.addWidget(b, i // 2, i % 2)
        panel.agregar(g)

        self.detalle_pago = QFrame()
        self.detalle_pago.setStyleSheet(f"QFrame#DetallePago {{ background: {C.CREMA}; border-radius: 10px; }}")
        self.detalle_pago.setObjectName("DetallePago")
        self.lay_detalle = QVBoxLayout(self.detalle_pago)
        self.lay_detalle.setContentsMargins(12, 12, 12, 12)
        self.lay_detalle.setSpacing(8)
        panel.agregar(self.detalle_pago)

        self.error_cobro = etiqueta("", "Error", ajustar=True)
        self.error_cobro.setVisible(False)
        self.btn_cobrar = QPushButton("Cobrar")
        self.btn_cobrar.setProperty("tipo", "primario")
        self.btn_cobrar.setMinimumHeight(60)
        self.btn_cobrar.setStyleSheet("font-family: 'Fredoka'; font-size: 20px; font-weight: 600;")
        self.btn_cobrar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_cobrar.clicked.connect(self._cobrar)
        panel.agregar(self.error_cobro, self.btn_cobrar)
        self.btn_cancelar = boton("Cancelar venta", "texto", self._cancelar_venta)
        self.btn_reimprimir = boton("Reimprimir último ticket", "texto", self._reimprimir)
        for b in (self.btn_cancelar, self.btn_reimprimir):
            b.setStyleSheet("text-align: left; padding-left: 12px;")
            b.setMinimumHeight(44)
            panel.agregar(b)

        derecha = vbox(panel, "stretch")
        self.agregar(hbox((izquierda, 1), derecha, espacio=16))

        self.reloj = QTimer(self)
        self.reloj.setInterval(700)
        self.reloj.timeout.connect(self._leer_bascula)

    # ------------------------------------------------------------ ciclo de vida
    def al_mostrar(self, **_):
        self.caja = self.intentar(self.ctx.datos.caja_actual)
        if not self.caja:
            if not self.aviso.isVisible():
                self.ctx.navegar("pos.apertura")
            return
        self.lbl_migas.setText(f"Punto de Venta · {self.caja['nombre']}")
        self.poner_estado(f"{self.caja['nombre']} · Terminal {self.caja['terminal']}",
                          C.NARANJA if self.ctx.datos.es_demo else C.VERDE)
        self.metodos = self.intentar(self.ctx.datos.metodos_pago) or []
        try:
            self.clientes = self.ctx.datos.clientes_credito_pos()
        except NoConectado:
            self.clientes = []
            self.botones_metodo["Crédito"].setEnabled(False)
            self.botones_metodo["Crédito"].setToolTip("Falta la ruta /finanzas/clientes-credito en el middleware.")
        except (ErrorNegocio, SesionExpirada):
            self.clientes = []
        self._cargar_productos(frecuentes=True)
        if self.metodo is None:
            self._elegir_metodo("Efectivo")
        self._pintar_carrito()
        self._leer_bascula()
        self.reloj.start()
        self.busqueda.setFocus()

    def hideEvent(self, e):
        self.reloj.stop()
        super().hideEvent(e)

    # ------------------------------------------------------------ productos
    def _cargar_productos(self, frecuentes: bool = False, busqueda: str | None = None) -> None:
        self.productos = self.intentar(self.ctx.datos.productos_pos, busqueda=busqueda, frecuentes=frecuentes) or []
        self.titulo_rejilla.setText("Productos frecuentes" if frecuentes else
                                    f"Resultados para “{busqueda}” · {len(self.productos)}")
        limpiar(self.rejilla)
        for i, p in enumerate(self.productos[:12]):
            b = QPushButton()
            b.setProperty("tipo", "producto")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setMinimumHeight(72)
            lay = vbox(texto(p["nombre"], 14, QFont.Weight.ExtraBold, ajustar=True),
                       texto(fmt.precio_unitario(p["precio_venta"], p["unidad_venta"]), 13, color=C.TEXTO_SUAVE),
                       espacio=4, margen=0)
            lay.setContentsMargins(4, 2, 4, 2)
            for j in range(lay.count()):
                lay.itemAt(j).widget().setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            b.setLayout(lay)
            b.setAccessibleName(p["nombre"])
            b.clicked.connect(lambda _=False, prod=p: self._agregar(prod))
            self.rejilla.addWidget(b, i // 4, i % 4)
        if not self.productos:
            self.rejilla.addWidget(etiqueta("No se encontró ningún producto.", "Muted"), 0, 0, 1, 4)

    def _filtrar_en_vivo(self, texto_: str) -> None:
        t = texto_.strip()
        if not t:
            self._cargar_productos(frecuentes=True)
        elif len(t) >= 3 and not t.isdigit():
            self._cargar_productos(busqueda=t)

    def _buscar(self) -> None:
        t = self.busqueda.text().strip()
        if not t:
            return
        exacto = self.intentar(self.ctx.datos.productos_pos, codigo=t) or []
        if exacto:  # lector de códigos: agrega directo
            self._agregar(exacto[0])
            self.busqueda.clear()
            self._cargar_productos(frecuentes=True)
            return
        self._cargar_productos(busqueda=t)
        if len(self.productos) == 1:
            self._agregar(self.productos[0])
            self.busqueda.clear()
            self._cargar_productos(frecuentes=True)

    # ------------------------------------------------------------ báscula
    def _leer_bascula(self) -> None:
        try:
            self.peso = self.ctx.datos.leer_bascula()
        except (NoConectado, ErrorNegocio, SesionExpirada):
            self.peso = Decimal("0")
        self.bascula.mostrar(self.peso)

    def _capturar_peso(self) -> None:
        valor, ok = QInputDialog.getDouble(self, "Báscula", "Peso en kg (captura manual o simulador):",
                                           float(self.peso), 0, 999, 3)
        if ok:
            self.ctx.datos.peso_simulado = Decimal(str(round(valor, 3)))
            self._leer_bascula()

    # ------------------------------------------------------------ carrito
    def _agregar(self, producto: dict) -> None:
        self._mensaje(None)
        if producto["unidad_venta"] == "kg":
            self._leer_bascula()
            if self.peso <= 0:
                self._mensaje("Coloque el producto en la báscula (o toque la báscula para capturar el peso).")
                return
            cantidad = self.peso
        else:
            cantidad = Decimal("1")
        try:
            self.carrito.agregar(producto, cantidad)
        except ValueError as exc:
            self._mensaje(str(exc))
            return
        self._pintar_carrito()

    def _editar_cantidad(self, fila: int, _col: int) -> None:
        if fila >= len(self.carrito):
            return
        r = self.carrito.renglones[fila]
        decimales = 3 if r.por_peso else 0
        valor, ok = QInputDialog.getDouble(self, r.nombre, f"Cantidad ({'kg' if r.por_peso else 'piezas'}):",
                                           float(r.cantidad), 0.001 if r.por_peso else 1, 9999, decimales)
        if ok:
            try:
                self.carrito.cambiar_cantidad(fila, Decimal(str(round(valor, decimales))))
            except ValueError as exc:
                self._mensaje(str(exc))
            self._pintar_carrito()

    def _quitar(self, indice: int) -> None:
        self.carrito.quitar(indice)
        self._pintar_carrito()

    def _pintar_carrito(self) -> None:
        filas = []
        for i, r in enumerate(self.carrito.renglones):
            filas.append([r.nombre, fmt.cantidad(r.cantidad, r.unidad), fmt.precio_unitario(r.precio, r.unidad),
                          fmt.dinero(r.importe), boton_icono("x", f"Quitar {r.nombre}", lambda i=i: self._quitar(i))])
        self.tabla.poner_filas(filas)
        self.tabla.setVisible(bool(filas))
        self.vacio.setVisible(not filas)
        n = len(self.carrito)
        self.lbl_total_titulo.setText(f"Total a pagar · {n} producto{'s' if n != 1 else ''}")
        self.lbl_total.setText(fmt.dinero(self.carrito.total))
        self._actualizar_pago()

    # ------------------------------------------------------------ pago
    def _metodo_por_nombre(self, nombre: str, tarjeta: str = "débito") -> dict | None:
        for m in self.metodos:
            if nombre == "Efectivo" and m["es_efectivo"] or nombre == "Crédito" and m["es_credito"]:
                return m
            if nombre == "Transferencia" and m["nombre"].lower().startswith("transferencia"):
                return m
            if nombre == "Tarjeta" and tarjeta in m["nombre"].lower():
                return m
        if nombre == "Tarjeta":
            return next((m for m in self.metodos if "tarjeta" in m["nombre"].lower()), None)
        return None

    def _elegir_metodo(self, nombre: str) -> None:
        self.nombre_metodo = nombre
        self.botones_metodo[nombre].setChecked(True)
        self.metodo = self._metodo_por_nombre(nombre)
        limpiar(self.lay_detalle)
        self.recibido = None
        self.cliente_combo = None
        if nombre == "Efectivo":
            self.recibido = entrada(placeholder="$0.00", alinear_derecha=True)
            self.recibido.setAccessibleName("Monto recibido")
            self.recibido.textChanged.connect(lambda *_: self._actualizar_pago())
            self.recibido.returnPressed.connect(self._cobrar)
            rapidos = hbox(espacio=6)
            for etiqueta_, monto in [("Exacto", None), ("$200", 200), ("$500", 500), ("$1,000", 1000)]:
                b = boton(etiqueta_, "opcion", lambda m=monto: self._monto_rapido(m))
                b.setMinimumHeight(36)
                b.setStyleSheet("padding: 6px 8px; font-size: 13px;")
                rapidos.addWidget(b)
            self.lbl_cambio = texto("Cambio: —", 16, QFont.Weight.ExtraBold, C.TEXTO)
            self.lay_detalle.addWidget(Campo("Monto recibido", self.recibido))
            self.lay_detalle.addLayout(rapidos)
            self.lay_detalle.addWidget(self.lbl_cambio)
        elif nombre == "Tarjeta":
            seg = hbox(espacio=6)
            self.grupo_tarjeta = QButtonGroup(self.detalle_pago)
            for t in ("Débito", "Crédito"):
                b = boton(t, "opcion", lambda t=t: self._tipo_tarjeta(t))
                b.setCheckable(True)
                b.setChecked(t == "Débito")
                self.grupo_tarjeta.addButton(b)
                seg.addWidget(b)
            self.lay_detalle.addWidget(etiqueta("Tipo de tarjeta", "Etiqueta"))
            self.lay_detalle.addLayout(seg)
            self.lay_detalle.addWidget(etiqueta("Cobra en la terminal bancaria y confirma aquí cuando sea aprobado.",
                                                "Muted", ajustar=True))
        elif nombre == "Transferencia":
            self.lay_detalle.addWidget(etiqueta("Confirma que la transferencia ya se refleja en la cuenta antes de cobrar.",
                                                "Muted", ajustar=True))
        else:
            clientes = [c for c in self.clientes]
            self.cliente_combo = combo([("Elige un cliente", None)] + [(c["nombre"], c["id"]) for c in clientes])
            self.cliente_combo.currentIndexChanged.connect(lambda *_: self._mostrar_cliente())
            self.lay_detalle.addWidget(Campo("Cliente de crédito", self.cliente_combo))
            self.info_cliente = QVBoxLayout()
            self.info_cliente.setSpacing(6)
            self.lay_detalle.addLayout(self.info_cliente)
            if self.clientes:
                self.cliente_combo.setCurrentIndex(1)
        self.btn_cobrar.setText({"Efectivo": "Cobrar en efectivo", "Tarjeta": "Cobrar con tarjeta",
                                 "Transferencia": "Cobrar con transferencia", "Crédito": "Cobrar a crédito"}[nombre])
        self._actualizar_pago()

    def _tipo_tarjeta(self, tipo: str) -> None:
        self.metodo = self._metodo_por_nombre("Tarjeta", tipo.lower())

    def _monto_rapido(self, monto) -> None:
        self.recibido.setText(f"{self.carrito.total:.2f}" if monto is None else f"{monto:.2f}")
        self.recibido.setFocus()

    def _cliente(self) -> dict | None:
        if self.cliente_combo is None or self.cliente_combo.currentData() is None:
            return None
        return next(c for c in self.clientes if c["id"] == self.cliente_combo.currentData())

    def _mostrar_cliente(self) -> None:
        limpiar(self.info_cliente)
        c = self._cliente()
        if c:
            fila = hbox(dato("Límite", fmt.dinero(c["limite"])), dato("Debe", fmt.dinero(c["debe"])),
                        dato("Disponible", fmt.dinero(c["disponible"]), C.VERDE_TEXTO, negrita=True), espacio=8)
            self.info_cliente.addLayout(fila)
            nota = f"Vence el {fmt.fecha_corta(c['vence'])} ({c['dias']} días de crédito)."
            if c.get("vencido"):
                nota += " Tiene un pago vencido."
            self.info_cliente.addWidget(etiqueta(nota, "Muted", ajustar=True))
        self._actualizar_pago()

    def _recibido(self) -> Decimal | None:
        return fmt.leer_dinero(self.recibido.text()) if self.recibido is not None else None

    def _actualizar_pago(self) -> None:
        if self.recibido is not None:
            c = cambio(self.carrito.total, self._recibido())
            if c is None:
                self.lbl_cambio.setText("Cambio: —")
                self.lbl_cambio.setStyleSheet(f"color: {C.TEXTO};")
            elif c < 0:
                self.lbl_cambio.setText("El monto recibido es insuficiente.")
                self.lbl_cambio.setStyleSheet(f"color: {C.ROJO}; font-size: 13px;")
            else:
                self.lbl_cambio.setText(f"Cambio: {fmt.dinero(c)}")
                self.lbl_cambio.setStyleSheet(f"color: {C.VERDE_TEXTO};")
        self.btn_cobrar.setEnabled(not self.carrito.vacio)

    def _mensaje(self, texto_: str | None) -> None:
        self.error_cobro.setText(texto_ or "")
        self.error_cobro.setVisible(bool(texto_))

    def _cobrar(self) -> None:
        recibido = self._recibido()
        cliente = self._cliente()
        error = validar_cobro(self.carrito, self.metodo, recibido, cliente)
        if error:
            self._mensaje(error)
            return
        self._mensaje(None)
        self.btn_cobrar.setEnabled(False)
        try:
            r = self.ctx.datos.registrar_venta(
                self.caja["id_caja"], self.metodo["id_metodo"],
                recibido if self.metodo["es_efectivo"] else Decimal("0"),
                cliente["id"] if cliente else None, self.carrito.para_api())
        except ErrorNegocio as exc:
            self._mensaje(exc.mensaje)
            self.btn_cobrar.setEnabled(True)
            return
        except SesionExpirada:
            self.ctx.sesion_expirada()
            return
        self.ultima_venta = dict(
            r, fecha=_ahora(self.ctx), metodo=self.metodo["nombre"], es_efectivo=self.metodo["es_efectivo"],
            recibido=recibido or Decimal("0"),
            renglones=[dict(nombre=x.nombre, unidad=x.unidad, cantidad=x.cantidad, precio=x.precio, importe=x.importe)
                       for x in self.carrito.renglones])
        self.carrito.vaciar()
        self.clientes = self.intentar(self.ctx.datos.clientes_credito_pos) or self.clientes
        self._elegir_metodo("Efectivo")
        self._pintar_carrito()
        TicketDialogo(self, self.ultima_venta, self.caja["nombre"], self.ctx.sesion.nombre_completo).exec()
        self.busqueda.setFocus()

    def _cancelar_venta(self) -> None:
        if self.carrito.vacio:
            return
        if confirmar(self, "Cancelar venta", "¿Cancelar la venta en proceso? Se quitarán todos los productos.",
                     "Sí, cancelar venta", peligro=True):
            self.carrito.vaciar()
            self._pintar_carrito()
            self._mensaje(None)

    def _reimprimir(self) -> None:
        if not self.ultima_venta:
            self._mensaje("Todavía no hay un ticket en este turno.")
            return
        TicketDialogo(self, self.ultima_venta, self.caja["nombre"], self.ctx.sesion.nombre_completo, reimpresion=True).exec()


def _ahora(ctx):
    from datetime import datetime
    if ctx.datos.es_demo:
        from app.datos.demo import HOY
        return datetime.combine(HOY, datetime.now().time())
    return datetime.now()
