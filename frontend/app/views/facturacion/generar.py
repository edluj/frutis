"""FAC-01 · Generar factura CFDI a partir de un ticket (flujo I, HU-12a)."""

from app import catalogos_sat as sat
from app import formato as fmt
from app.datos import ErrorNegocio
from app.theme import C
from app.validaciones import error_correo, error_cp, error_rfc
from app.views.base import Contexto, PaginaBase
from app.widgets import Campo, Card, Celda, Col, Tabla, boton, combo, confirmar, entrada, etiqueta, hbox, rejilla


class GenerarFacturaView(PaginaBase):
    def __init__(self, ctx: Contexto):
        super().__init__(ctx, "Facturación", "Generar factura", estado="")
        timbres = self.intentar(ctx.datos.timbres_disponibles)
        if timbres:
            self.poner_estado(f"Internet disponible · {timbres[0]:,} de {timbres[1]:,} timbres",
                              C.NARANJA if timbres[0] < timbres[1] * 0.2 else C.VERDE)
        self.ticket: dict | None = None
        self.clientes = self.intentar(ctx.datos.lista_clientes_fiscales) or []

        self.folio = entrada(placeholder="V00001042", max_len=12)
        self.folio.returnPressed.connect(self._cargar_ticket)
        self.folio.editingFinished.connect(self._cargar_ticket)
        self.campo_folio = Campo("Ticket de venta *", self.folio)
        self.cliente = combo([("Elige un cliente o captura sus datos", None)] +
                             [(f"{c['razon_social']} · {c['rfc']}", c) for c in self.clientes])
        self.cliente.currentIndexChanged.connect(self._llenar_cliente)
        self.rfc = entrada(max_len=13)
        self.regimen = combo(sat.REGIMENES)
        self.cp = entrada(max_len=5)
        self.uso = combo(sat.USOS_CFDI, "G03")
        self.forma = combo(sat.FORMAS_PAGO)
        self.metodo = combo(sat.METODOS_PAGO)
        self.correo = entrada(max_len=120)
        self.campos = {"rfc": Campo("RFC", self.rfc), "cp": Campo("Código postal", self.cp),
                       "correo": Campo("Enviar a", self.correo)}
        nuevo = boton("+ Cliente nuevo", "texto", lambda: ctx.navegar("fac.clientes", nuevo="1"))
        self.agregar(Card("Ticket y cliente").agregar(rejilla([
            [self.campo_folio, (Campo("Cliente (datos fiscales guardados)", self.cliente), 2), nuevo],
            [self.campos["rfc"], Campo("Régimen fiscal", self.regimen), self.campos["cp"], Campo("Uso de CFDI", self.uso)],
            [Campo("Forma de pago", self.forma), Campo("Método de pago", self.metodo), (self.campos["correo"], 2)],
        ])))

        self.tabla = Tabla([Col("Clave SAT"), Col("Producto", estirar=True), Col("Cantidad", "der"), Col("Precio", "der"),
                            Col("IVA", "der"), Col("Importe", "der")])
        self.vacio = etiqueta("Escribe el número de ticket para ver sus conceptos.", "Muted")
        self.error = etiqueta("", "Error", ajustar=True)
        self.error.setVisible(False)
        self.conceptos = Card("Conceptos del ticket")
        self.btn_timbrar = boton("Timbrar factura", "primario", self._timbrar)
        self.btn_timbrar.setEnabled(False)
        self.conceptos.agregar(self.vacio, self.tabla, self.error,
                               hbox(self.btn_timbrar, boton("Guardar borrador", "texto", self._borrador), "stretch"),
                               etiqueta("Un ticket solo se factura una vez. Si no hay internet, la factura se guarda como "
                                        "borrador para timbrarla después.", "Muted", ajustar=True))
        self.tabla.setVisible(False)
        self.agregar(self.conceptos)
        self.terminar()

    def al_mostrar(self, ticket: str | None = None, **_):
        if ticket:
            self.folio.setText(ticket)
            self._cargar_ticket()

    def _llenar_cliente(self, *_):
        c = self.cliente.currentData()
        if not c:
            return
        self.rfc.setText(c["rfc"])
        self.regimen.setCurrentIndex(max(0, self.regimen.findData(c["regimen"])))
        self.cp.setText(c["cp"])
        self.correo.setText(c["correo"])
        for campo in self.campos.values():
            campo.error(None)

    def _cargar_ticket(self) -> None:
        folio = self.folio.text().strip().upper()
        if not folio or (self.ticket and self.ticket["folio"] == folio):
            return
        self.campo_folio.error(None)
        try:
            t = self.intentar(self.ctx.datos.ticket_para_factura, folio, mostrar_dialogo=False)
        except ErrorNegocio as exc:
            self.campo_folio.error(exc.mensaje)
            self.ticket = None
            self.tabla.setVisible(False)
            self.vacio.setVisible(True)
            self.btn_timbrar.setEnabled(False)
            return
        if not t:
            return
        self.ticket = t
        self.conceptos.titulo_lbl.setText(f"Conceptos del ticket · {fmt.fecha_corta(t['fecha'].date())}")
        forma = sat.FORMA_POR_METODO.get(t["metodo"], "99")
        self.forma.setCurrentIndex(max(0, self.forma.findData(forma)))
        self.metodo.setCurrentIndex(1 if t["metodo"].startswith("Crédito") else 0)
        self.tabla.poner_filas(
            [[r["clave_sat"], r["nombre"], fmt.cantidad(r["cantidad"], r["unidad"]), fmt.dinero(r["precio"]), "0 %",
              fmt.dinero(r["importe"])] for r in t["renglones"]],
            total=["", Celda(f"Subtotal {fmt.dinero(t['total'])} · IVA $0.00", True), "", "", "", Celda(fmt.dinero(t["total"]), True)])
        self.tabla.setVisible(True)
        self.vacio.setVisible(False)
        self.btn_timbrar.setEnabled(True)

    def _validar(self) -> bool:
        errores = {"rfc": error_rfc(self.rfc.text().strip().upper()), "cp": error_cp(self.cp.text()),
                   "correo": error_correo(self.correo.text())}
        return not any([self.campos[k].error(v) for k, v in errores.items()])

    def _timbrar(self) -> None:
        if not self.ticket or not self._validar():
            return
        if not confirmar(self, "Timbrar factura", f"Se timbrará la factura del ticket {self.ticket['folio']} por "
                         f"{fmt.dinero(self.ticket['total'])} a nombre de {self.rfc.text().upper()}.", "Timbrar"):
            return
        datos = dict(ticket=self.ticket["folio"], rfc=self.rfc.text().strip().upper(), regimen=self.regimen.currentData(),
                     cp=self.cp.text().strip(), uso=self.uso.currentData(), forma=self.forma.currentData(),
                     metodo_pago=self.metodo.currentData(), correo=self.correo.text().strip())
        f = self.intentar(self.ctx.datos.timbrar, datos)
        if f:
            self.ctx.navegar("fac.timbrada", folio=f["folio"])

    def _borrador(self) -> None:
        self.error.setText("Los borradores se guardan en el servidor; la ruta /facturacion/borradores todavía no existe.")
        self.error.setVisible(True)
