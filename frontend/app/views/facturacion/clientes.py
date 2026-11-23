"""FAC-04 · Datos fiscales de clientes (flujo K, HU-32)."""
from app import catalogos_sat as sat
from app.datos import ErrorNegocio
from app.validaciones import error_correo, error_cp, error_obligatorio, error_rfc
from app.views.base import Contexto, PaginaBase
from app.widgets import Campo, Card, Col, Tabla, boton, boton_icono, combo, entrada, hbox, rejilla


class ClientesFiscalesView(PaginaBase):
    def __init__(self, ctx: Contexto):
        super().__init__(ctx, "Facturación", "Datos fiscales de clientes", estado=ctx.datos.estado_conexion())
        self.original: str | None = None
        self.buscar = entrada(placeholder="Buscar por RFC o razón social")
        self.buscar.textChanged.connect(self._cargar)
        nuevo = boton("+ Nuevo cliente", "primario", self._nuevo)
        nuevo.setVisible(ctx.sesion.puede("facturacion", "crear"))
        from PySide6.QtCore import Qt
        self.tabla = Tabla([Col("RFC"), Col("Razón social", estirar=True), Col("Régimen"), Col("C.P."), Col("Correo"),
                            Col("Facturas", "der"), Col("", "centro", ancho=70)])
        self.agregar(Card().agregar(hbox((Campo("Buscar por RFC o razón social", self.buscar), 1), nuevo,
                                         alinear=Qt.AlignmentFlag.AlignBottom), self.tabla))

        self.rfc = entrada(max_len=13)
        self.razon = entrada(max_len=150)
        self.regimen = combo(sat.REGIMENES)
        self.cp = entrada(max_len=5)
        self.correo = entrada(max_len=120)
        self.campos = {"rfc": Campo("RFC *", self.rfc), "razon": Campo("Razón social *", self.razon),
                       "regimen": Campo("Régimen fiscal *", self.regimen), "cp": Campo("Código postal *", self.cp),
                       "correo": Campo("Correo *", self.correo)}
        c = self.campos
        self.form = Card("Nuevo cliente").agregar(
            rejilla([[c["rfc"], (c["razon"], 2), c["regimen"]], [c["cp"], (c["correo"], 3)]]),
            hbox(boton("Guardar", "primario", self._guardar), boton("Cancelar", "texto", lambda: self.form.setVisible(False)),
                 "stretch"))
        self.form.setVisible(False)
        self.agregar(self.form)
        self.terminar()
        self._cargar()

    def al_mostrar(self, nuevo: str | None = None, **_):
        if nuevo:
            self._nuevo()

    def _cargar(self, *_):
        filas = self.intentar(self.ctx.datos.lista_clientes_fiscales, self.buscar.text().strip()) or []
        puede = self.ctx.sesion.puede("facturacion", "editar")
        self.tabla.poner_filas([[c["rfc"], c["razon_social"], c["regimen"], c["cp"], c["correo"], str(c["facturas"]),
                                 boton_icono("lapiz", "Editar", lambda c=c: self._editar(c)) if puede else ""]
                                for c in filas])

    def _nuevo(self) -> None:
        self.original = None
        self.form.titulo_lbl.setText("Nuevo cliente")
        for w in (self.rfc, self.razon, self.cp, self.correo):
            w.clear()
        for campo in self.campos.values():
            campo.error(None)
        self.form.setVisible(True)
        self.rfc.setFocus()

    def _editar(self, c: dict) -> None:
        self.original = c["rfc"]
        self.form.titulo_lbl.setText(f"Editar · {c['razon_social']}")
        self.rfc.setText(c["rfc"])
        self.razon.setText(c["razon_social"])
        self.regimen.setCurrentIndex(max(0, self.regimen.findData(c["regimen"])))
        self.cp.setText(c["cp"])
        self.correo.setText(c["correo"])
        for campo in self.campos.values():
            campo.error(None)
        self.form.setVisible(True)

    def _guardar(self) -> None:
        rfc = self.rfc.text().strip().upper()
        errores = {"rfc": error_rfc(rfc), "razon": error_obligatorio(self.razon.text(), "La razón social", 150),
                   "cp": error_cp(self.cp.text()), "correo": error_correo(self.correo.text())}
        if any([self.campos[k].error(v) for k, v in errores.items()]):
            return
        datos = dict(rfc=rfc, razon_social=self.razon.text().strip(), regimen=self.regimen.currentData(),
                     cp=self.cp.text().strip(), correo=self.correo.text().strip())
        try:
            self.intentar(self.ctx.datos.guardar_cliente_fiscal, datos, self.original, mostrar_dialogo=False)
        except ErrorNegocio as exc:
            self.campos.get(exc.campo or "rfc", self.campos["rfc"]).error(exc.mensaje)
            return
        if self.aviso.isVisible():
            return
        self.form.setVisible(False)
        self._cargar()
