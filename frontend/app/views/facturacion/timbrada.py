"""FAC-02 · Factura timbrada: comprobante, descargas y reenvío."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QPixmap

from app import catalogos_sat as sat
from app import formato as fmt
from app.theme import RECURSOS, C
from app.views.base import Contexto, PaginaBase
from app.widgets import (
    Alerta, Badge, Card, Celda, Col, Tabla, avisar, boton, columnas, dato, etiqueta, hbox, rejilla, texto, vbox,
)


class FacturaTimbradaView(PaginaBase):
    def __init__(self, ctx: Contexto):
        super().__init__(ctx, "Facturación › Generar factura", "Factura timbrada", estado="", punto=None)

    def al_mostrar(self, folio: str = "", **_):
        f = self.intentar(self.ctx.datos.detalle_factura, folio)
        if not f:
            return
        self.lbl_titulo.setText(f"Factura {f['folio']} timbrada")
        self.lbl_estado.setVisible(False)
        self.zona_derecha.addWidget(Badge(f["estatus"], "verde" if f["estatus"] == "Vigente" else "rojo"))
        self.agregar(Alerta(f"✓&nbsp; El SAT recibió la factura. Ya se envió a <b>{f.get('correo') or f['cliente'].get('correo', '')}</b>.", "verde"))

        logo = etiqueta("")
        logo.setPixmap(QPixmap(str(RECURSOS / "img" / "avatar.png")).scaled(
            58, 58, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        emisor = vbox(texto("Frutería Frutis", 20, titulo=True, color=C.GUINDA, peso=QFont.Weight.DemiBold),
                      etiqueta("[RFC DEL EMISOR] · Régimen 612", "Muted"), espacio=0)
        uuid = vbox(texto("Folio fiscal (UUID)", 12, color=C.TEXTO_SUAVE), texto(f["uuid"], 14, QFont.Weight.ExtraBold),
                    etiqueta(f"Timbrado {fmt.fecha_hora(f.get('timbrado')) if f.get('timbrado') else fmt.fecha(f['fecha'])}", "Muted"),
                    espacio=2)
        for i in range(uuid.count()):
            uuid.itemAt(i).widget().setAlignment(Qt.AlignmentFlag.AlignRight)
        c = f["cliente"]
        t = Tabla([Col("Concepto", estirar=True), Col("Cantidad", "der"), Col("Precio", "der"), Col("Importe", "der")])
        t.poner_filas([[r["nombre"], fmt.cantidad(r["cantidad"], r["unidad"]), fmt.dinero(r["precio"]), fmt.dinero(r["importe"])]
                       for r in f["renglones"]],
                      total=[Celda("Total (IVA 0 %)", True), "", "", Celda(fmt.dinero(f["total"]), True)])
        comprobante = Card().agregar(
            hbox(logo, emisor, "stretch", uuid),
            rejilla([[dato("Receptor", f"{c['razon_social']}\n{c['rfc']} · CP {c.get('cp', '')}"),
                      dato("Uso de CFDI", sat.nombre(sat.USOS_CFDI, f["uso"])),
                      dato("Pago", f"{sat.nombre(sat.FORMAS_PAGO, f['forma'])} · {f['metodo_pago']}")],
                     [dato("Ticket", f["ticket"])]]),
            t)
        nota = lambda m: lambda: avisar(self, "Archivos de la factura", m)  # noqa: E731
        archivos = Card("Archivos").agregar(
            boton("Descargar PDF", "secundario", nota("El PDF y el XML los entrega el proveedor de timbrado (PAC) "
                                                      "desde el servidor; falta elegir el PAC (R-06).")),
            boton("Descargar XML", "secundario", nota("El XML timbrado se descarga desde el servidor (ruta /facturacion).")),
            boton("Reenviar por correo", "texto", nota(f"Se reenviará a {f.get('correo') or c.get('correo', '')}.")),
            boton("Nueva factura", "primario", lambda: self.ctx.navegar("fac.generar")),
            boton("Ver facturas emitidas", "texto", lambda: self.ctx.navegar("fac.emitidas")))
        archivos.setFixedWidth(270)
        self.agregar(columnas(comprobante, archivos, proporciones=[1, 0]))
        self.terminar()
