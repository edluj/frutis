"""FIN-05 · Cuentas por cobrar y registro de cobros (flujo N, HU-38b, sp_registrar_cobro)."""
from app import formato as fmt
from app.datos import ErrorNegocio
from app.theme import C
from app.validaciones import monto_positivo
from app.views.base import Contexto, PaginaBase
from app.widgets import (
    Badge, Campo, Card, Celda, Col, Kpi, Tabla, boton, columnas, combo, confirmar, entrada, etiqueta, fila_kpis, hbox,
)

METODOS = ["Efectivo", "Transferencia", "Tarjeta"]


class CuentasCobrarView(PaginaBase):
    def __init__(self, ctx: Contexto):
        super().__init__(ctx, "Finanzas", "Cuentas por cobrar",
                         acciones=[boton("Clientes de crédito", "secundario", lambda: ctx.navegar("fin.clientes"))])
        self.seleccion: dict | None = None
        self.k_total = Kpi("Por cobrar", "—")
        self.k_vencido = Kpi("Vencido", "—", color=C.ROJO)
        self.k_cobrado = Kpi("Cobrado en el mes", "—", color=C.VERDE)
        self.agregar(fila_kpis(self.k_total, self.k_vencido, self.k_cobrado))

        clientes = self.intentar(ctx.datos.lista_clientes_credito) or []
        self.cliente = combo([("Todos", None)] + [(c["nombre"], c["id"]) for c in clientes])
        self.estatus = combo(["Pendientes y vencidas", "Vencidas", "Pagadas", "Todas"])
        self.cliente.currentIndexChanged.connect(self._cargar)
        self.estatus.currentIndexChanged.connect(self._cargar)
        self.tabla = Tabla([Col("Ticket"), Col("Cliente", estirar=True), Col("Venta"), Col("Vence"), Col("Total", "der"),
                            Col("Saldo", "der"), Col("Estatus")])
        self.tabla.fila_elegida.connect(self._elegir)
        izq = Card().agregar(hbox(Campo("Cliente", self.cliente), Campo("Estatus", self.estatus)), self.tabla)

        self.sub = etiqueta("Toca una venta de la tabla para registrar su cobro.", "Muted", ajustar=True)
        self.monto = entrada(placeholder="$0.00")
        self.campo_monto = Campo("Monto recibido", self.monto)
        self.metodo = combo(METODOS)
        self.metodo.currentIndexChanged.connect(self._caja_segun_metodo)
        self.caja = combo(self.intentar(ctx.datos.cajas_abiertas) or ["Sin caja"])
        self.campo_caja = Campo("Caja que recibe", self.caja, "Un cobro en efectivo entra al corte de esa caja.")
        self.btn = boton("Registrar cobro", "primario", self._cobrar)
        self.btn.setMinimumHeight(46)
        self.panel = Card("Registrar cobro", margen=18).agregar(
            self.sub, self.campo_monto, Campo("Método", self.metodo), self.campo_caja, self.btn,
            boton("Ver estado de cuenta", "texto", self._estado))
        self.panel.setFixedWidth(320)
        for w in (self.monto, self.metodo, self.caja, self.btn):
            w.setEnabled(False)
        self.agregar(columnas(izq, self.panel, proporciones=[1, 0]))
        self.terminar()
        self._cargar()

    def _cargar(self, *_):
        r = self.intentar(self.ctx.datos.cuentas_por_cobrar, self.cliente.currentData(), self.estatus.currentText())
        if not r:
            return
        self.k_total.poner(fmt.dinero(r["total"]), f"{r['ventas']} ventas a crédito · {r['clientes']} clientes")
        v = r["vencidas"]
        self.k_vencido.poner(fmt.dinero(r["vencido"]), ", ".join(f"{x['cliente']} · {x['estatus'].split('· ')[-1]}" for x in v)
                             or "Nada vencido")
        self.k_cobrado.poner(fmt.dinero(r["cobrado_mes"]), f"De {fmt.dinero(r['vendido_credito'])} vendidos a crédito")
        tonos, filas = {}, []
        for i, f in enumerate(r["filas"]):
            if self.seleccion and f["ticket"] == self.seleccion["ticket"]:
                tonos[i] = "guinda"
            elif f["tono"] == "rojo":
                tonos[i] = "rojo"
            est = Celda(f["estatus"], True, C.ROJO) if f["tono"] == "rojo" else Badge(f["estatus"], f["tono"])
            filas.append([Celda(f["ticket"], True), f["cliente"], fmt.fecha(f["venta"]), fmt.fecha(f["vence"]),
                          fmt.dinero(f["total"]), fmt.dinero(f["saldo"]), est])
        self.tabla.poner_filas(filas, datos=r["filas"], tonos=tonos)

    def _elegir(self, fila: int) -> None:
        f = self.tabla.dato(fila)
        if not f:
            return
        self.seleccion = f
        self.sub.setText(f"{f['ticket']} · {f['cliente']} · saldo {fmt.dinero(f['saldo'])}")
        habilitar = f["saldo"] > 0 and self.ctx.sesion.puede("finanzas", "crear")
        for w in (self.monto, self.metodo, self.caja, self.btn):
            w.setEnabled(habilitar)
        self.monto.setText(f"{f['saldo']:.2f}" if habilitar else "")
        self.campo_monto.error(None)
        self._caja_segun_metodo()
        self._cargar()

    def _caja_segun_metodo(self, *_):
        efectivo = self.metodo.currentText() == "Efectivo"
        self.campo_caja.setVisible(efectivo)

    def _cobrar(self) -> None:
        f = self.seleccion
        monto, error = monto_positivo(self.monto.text())
        if error or monto > f["saldo"]:
            self.campo_monto.error(error or "El cobro no puede ser mayor al saldo.")
            return
        if not confirmar(self, "Registrar cobro", f"Se registrará un cobro de {fmt.dinero(monto)} a {f['cliente']} "
                         f"({f['ticket']}).", "Registrar cobro"):
            return
        try:
            saldo = self.intentar(self.ctx.datos.registrar_cobro, f["ticket"], monto, self.metodo.currentText(),
                                  self.caja.currentText(), mostrar_dialogo=False)
        except ErrorNegocio as exc:
            self.campo_monto.error(exc.mensaje)
            return
        if saldo is None:
            return
        self.sub.setText(f"Cobro registrado. {f['ticket']}: saldo restante {fmt.dinero(saldo)}.")
        for w in (self.monto, self.metodo, self.caja, self.btn):
            w.setEnabled(False)
        self.monto.clear()
        self.seleccion = None
        self._cargar()

    def _estado(self) -> None:
        if self.seleccion:
            self.ctx.navegar("fin.estado", id_cliente=self.seleccion["id_cliente"])
        elif self.cliente.currentData():
            self.ctx.navegar("fin.estado", id_cliente=self.cliente.currentData())
