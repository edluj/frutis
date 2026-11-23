"""PRV-02 · Registrar lote de compra (flujo G, HU-11)."""
from datetime import date, timedelta
from decimal import Decimal

from PySide6.QtCore import QDate

from app import formato as fmt
from app.validaciones import cantidad_positiva, monto_positivo
from app.views.base import Contexto, PaginaBase
from app.widgets import (
    Alerta, Campo, Card, Celda, Col, Tabla, boton, boton_icono, combo, confirmar, entrada, etiqueta, hbox, rejilla,
    selector_fecha,
)

CONDICIONES = [("Contado", 0), ("Crédito 7 días", 7), ("Crédito 15 días", 15), ("Crédito 30 días", 30)]


def _qdate(q: QDate) -> date:
    return date(q.year(), q.month(), q.day())


class RegistrarLoteView(PaginaBase):
    def __init__(self, ctx: Contexto):
        super().__init__(ctx, "Proveedores y Compras", "Registrar lote de compra",
                         acciones=[boton("Ver lotes registrados", "secundario", lambda: ctx.navegar("compras.lotes"))])
        self.renglones: list[dict] = []
        self.folio = self.intentar(ctx.datos.siguiente_folio_lote) or "nuevo"
        proveedores = self.intentar(ctx.datos.proveedores_activos) or []
        self.productos = self.intentar(ctx.datos.lista_productos) or []

        self.proveedor = combo([(p["razon_social"], p) for p in proveedores])
        self.factura = entrada(max_len=40, placeholder="Ej. FS-88213")
        hoy = date.today()
        if ctx.datos.es_demo:
            from app.datos.demo import HOY
            hoy = HOY
        self.entrada_fecha = selector_fecha(hoy)
        self.condicion = combo(CONDICIONES)
        self.aviso_cxp = Alerta("", "naranja")
        self.campo_proveedor = Campo("Proveedor *", self.proveedor)
        self.agregar(Card("Datos del lote").agregar(
            rejilla([[(self.campo_proveedor, 2), Campo("Factura del proveedor", self.factura),
                      Campo("Fecha de entrada *", self.entrada_fecha), Campo("Condición *", self.condicion)]]),
            self.aviso_cxp))
        self.proveedor.currentIndexChanged.connect(self._condicion_del_proveedor)
        self.condicion.currentIndexChanged.connect(self._aviso)
        self.entrada_fecha.dateChanged.connect(self._aviso)

        # Productos
        self.tabla = Tabla([Col("Producto", estirar=True), Col("Cantidad", "der", ancho=130),
                            Col("Costo unitario", "der", ancho=140), Col("Caducidad", ancho=130),
                            Col("Subtotal", "der", ancho=130), Col("", "centro", ancho=64)], alto_fila=52)
        self.prod = combo([("Buscar producto", None)] + [(p["nombre"], p) for p in self.productos])
        self.prod.setEditable(True)
        self.prod.lineEdit().setPlaceholderText("Buscar producto")
        self.prod.setInsertPolicy(self.prod.InsertPolicy.NoInsert)
        self.cant = entrada(placeholder="Cantidad", alinear_derecha=True)
        self.costo = entrada(placeholder="Costo $", alinear_derecha=True)
        self.caducidad = selector_fecha(hoy + timedelta(days=7))
        self.error_renglon = etiqueta("", "Error")
        self.error_renglon.setVisible(False)
        captura = hbox((self.prod, 3), (self.cant, 1), (self.costo, 1), (self.caducidad, 1),
                       boton("Agregar", "secundario", self._agregar_renglon), espacio=10)
        self.cant.returnPressed.connect(self.costo.setFocus)
        self.costo.returnPressed.connect(self._agregar_renglon)
        self.tarjeta_prod = Card(f"Productos del lote {self.folio}",
                                 derecha=[boton("+ Agregar producto", "secundario", lambda: self.prod.setFocus())])
        self.tarjeta_prod.agregar(self.tabla, captura, self.error_renglon,
                                  etiqueta("Al guardar, el inventario sube por lote y el costo de cada producto se "
                                           "actualiza para el reporte de variación de costos.", "Muted", ajustar=True),
                                  hbox(boton("Guardar lote", "primario", self._guardar),
                                       boton("Cancelar", "texto", lambda: ctx.navegar("compras.lotes")), "stretch"))
        self.agregar(self.tarjeta_prod)
        self.terminar()
        self._condicion_del_proveedor()
        self._pintar()

    # ------------------------------------------------------------ cuenta por pagar
    def _condicion_del_proveedor(self, *_):
        p = self.proveedor.currentData()
        if p:
            i = self.condicion.findData(p["dias_credito"])
            self.condicion.setCurrentIndex(i if i >= 0 else 2)
        self._aviso()

    def _aviso(self, *_):
        dias = self.condicion.currentData() or 0
        if dias == 0:
            self.aviso_cxp.mostrar(f"Lote de contado: el pago del lote {self.folio} se registra como egreso al guardar.", "crema")
        else:
            vence = _qdate(self.entrada_fecha.date()) + timedelta(days=dias)
            larga = fmt.fecha_larga(vence).split(" ", 1)[1]
            self.aviso_cxp.mostrar(f"Se creará la cuenta por pagar del lote {self.folio} con vencimiento el <b>{larga}</b>.",
                                   "naranja")

    # ------------------------------------------------------------ renglones
    def _agregar_renglon(self) -> None:
        p = self.prod.currentData()
        if p is None:
            texto_ = self.prod.currentText().strip().lower()
            p = next((x for x in self.productos if x["nombre"].lower() == texto_), None)
        decimales = 3 if p and p["unidad_venta"] == "kg" else 0
        cantidad = cantidad_positiva(self.cant.text(), decimales)
        costo, _ = monto_positivo(self.costo.text())
        cad = _qdate(self.caducidad.date())
        error = None
        if p is None:
            error = "Elige un producto del catálogo."
        elif cantidad is None or costo is None:
            error = "Ingrese una cantidad y costo válidos."
        elif cad <= _qdate(self.entrada_fecha.date()):
            error = "La caducidad debe ser posterior a la fecha de entrada."
        for w, mal in ((self.cant, cantidad is None and p is not None), (self.costo, costo is None and p is not None)):
            w.setProperty("error", bool(error) and mal)
            w.style().polish(w)
        self.error_renglon.setText(error or "")
        self.error_renglon.setVisible(bool(error))
        if error:
            return
        self.renglones.append(dict(id_producto=p["id_producto"], nombre=p["nombre"], unidad=p["unidad_venta"],
                                   cantidad=cantidad, costo=costo, caducidad=cad))
        self.cant.clear()
        self.costo.clear()
        self.prod.setCurrentIndex(0)
        self.prod.setFocus()
        self._pintar()

    def _quitar(self, i: int) -> None:
        del self.renglones[i]
        self._pintar()

    def _pintar(self) -> None:
        filas = []
        for i, r in enumerate(self.renglones):
            sub = (r["cantidad"] * r["costo"]).quantize(Decimal("0.01"))
            filas.append([r["nombre"], fmt.cantidad(r["cantidad"], r["unidad"]), fmt.precio_unitario(r["costo"], r["unidad"]),
                          fmt.fecha(r["caducidad"]), fmt.dinero(sub), boton_icono("x", "Quitar", lambda i=i: self._quitar(i))])
        kilos = sum((r["cantidad"] for r in self.renglones if r["unidad"] == "kg"), Decimal("0"))
        total = sum(((r["cantidad"] * r["costo"]).quantize(Decimal("0.01")) for r in self.renglones), Decimal("0"))
        self.tabla.poner_filas(filas, total=[Celda("Total del lote", True), Celda(f"{kilos:,.3f} kg", True), "", "",
                                             Celda(fmt.dinero(total), True), ""])

    # ------------------------------------------------------------ guardar
    def _guardar(self) -> None:
        p = self.proveedor.currentData()
        if p is None:
            self.campo_proveedor.error("Elige el proveedor.")
            return
        if not self.renglones:
            self.error_renglon.setText("Agrega al menos un producto al lote.")
            self.error_renglon.setVisible(True)
            return
        total = sum(((r["cantidad"] * r["costo"]).quantize(Decimal("0.01")) for r in self.renglones), Decimal("0"))
        if not confirmar(self, "Guardar lote", f"Se registrará el lote {self.folio} de {p['razon_social']} "
                         f"por {fmt.dinero(total)}.", "Guardar lote"):
            return
        datos = dict(id_proveedor=p["id"], factura=self.factura.text().strip(), entrada=_qdate(self.entrada_fecha.date()),
                     dias=self.condicion.currentData(), renglones=self.renglones)
        folio = self.intentar(self.ctx.datos.registrar_lote, datos)
        if folio:
            self.ctx.navegar("compras.lote", folio=folio)
