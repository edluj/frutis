"""PRV-05 · Cuentas por pagar y registro de pagos (flujo H, HU-25)."""

from app import formato as fmt
from app.datos import ErrorNegocio
from app.theme import C
from app.validaciones import monto_positivo
from app.views.base import Contexto, PaginaBase
from app.widgets import (
    Campo, Card, Celda, Col, Kpi, Tabla, boton, columnas, combo, confirmar, entrada, etiqueta, fila_kpis, hbox,
)

METODOS = ["Transferencia", "Efectivo", "Cheque"]


class CuentasPagarView(PaginaBase):
    def __init__(self, ctx: Contexto):
        super().__init__(ctx, "Proveedores y Compras", "Cuentas por pagar")
        if ctx.datos.es_demo:
            from app.datos.demo import HOY
            self.poner_estado(f"Al {fmt.fecha_larga(HOY).split(' ', 1)[1]}")
        self.seleccion: dict | None = None
        self.k_total = Kpi("Total por pagar", "—")
        self.k_vencido = Kpi("Vencido", "—", color=C.ROJO)
        self.k_proximo = Kpi("Vence en 3 días o menos", "—", color=C.NARANJA)
        self.agregar(fila_kpis(self.k_total, self.k_vencido, self.k_proximo))

        proveedores = self.intentar(ctx.datos.proveedores_activos) or []
        self.proveedor = combo([("Todos", None)] + [(p["razon_social"], p["id"]) for p in proveedores])
        self.estatus = combo(["Pendientes y vencidas", "Vencidas", "Pagadas", "Todas"])
        self.proveedor.currentIndexChanged.connect(self._cargar)
        self.estatus.currentIndexChanged.connect(self._cargar)
        self.tabla = Tabla([Col("Lote"), Col("Proveedor", estirar=True), Col("Vence"), Col("Total", "der"),
                            Col("Saldo", "der"), Col("Estatus")])
        self.tabla.fila_elegida.connect(self._elegir)
        izq = Card().agregar(hbox(Campo("Proveedor", self.proveedor), Campo("Estatus", self.estatus)), self.tabla)

        # Panel de pago
        self.titulo_pago = etiqueta("Elige una cuenta", "CardTitulo")
        self.sub_pago = etiqueta("Toca una fila de la tabla para registrar su pago.", "Muted", ajustar=True)
        self.monto = entrada(placeholder="$0.00")
        self.monto.textChanged.connect(self._nota_monto)
        self.campo_monto = Campo("Monto", self.monto)
        self.metodo = combo(METODOS)
        self.referencia = entrada(placeholder="Ej. SPEI 0211-77812", max_len=60)
        self.btn_pagar = boton("Aplicar pago", "primario", self._pagar)
        self.btn_pagar.setMinimumHeight(46)
        self.btn_edo = boton("Ver estado de cuenta", "texto", self._estado_cuenta)
        self.panel = Card(margen=18).agregar(self.titulo_pago, self.sub_pago, self.campo_monto, Campo("Método", self.metodo),
                                             Campo("Referencia", self.referencia), self.btn_pagar, self.btn_edo)
        self.panel.setFixedWidth(320)
        puede = ctx.sesion.puede("compras", "crear")
        for w in (self.monto, self.metodo, self.referencia, self.btn_pagar):
            w.setEnabled(False)
        self._puede_pagar = puede
        self.agregar(columnas(izq, self.panel, proporciones=[1, 0]))
        self.terminar()

    def al_mostrar(self, lote: str | None = None, **_):
        self._cargar()
        if lote:
            for i, f in enumerate(self.tabla.datos):
                if f["lote"] == lote:
                    self._elegir(i)

    def _cargar(self, *_):
        r = self.intentar(self.ctx.datos.cuentas_por_pagar, self.proveedor.currentData(), self.estatus.currentText())
        if not r:
            return
        self.k_total.poner(fmt.dinero(r["total"]), f"{r['lotes']} lotes · {r['proveedores']} proveedores")
        self.k_vencido.poner(fmt.dinero(r["vencido"]), _resumen(r["vencidas"]))
        self.k_proximo.poner(fmt.dinero(r["proximo"]), _resumen(r["proximas"]))
        tonos = {}
        filas = []
        for i, f in enumerate(r["filas"]):
            if f["tono"] in ("rojo", "naranja"):
                tonos[i] = f["tono"]
            color = C.ROJO if f["tono"] == "rojo" else C.NARANJA_TEXTO if f["tono"] == "naranja" else None
            estatus = Celda(f["estatus"], True, color) if color else _badge(f)
            filas.append([Celda(f["lote"], True), f["proveedor"], fmt.fecha(f["vence"]), fmt.dinero(f["total"]),
                          fmt.dinero(f["saldo"]), estatus])
        self.tabla.poner_filas(filas, datos=r["filas"], tonos=tonos)
        self.seleccion = None

    def _elegir(self, fila: int) -> None:
        f = self.tabla.dato(fila)
        if not f:
            return
        self.tabla.selectRow(fila)
        self.seleccion = f
        self.titulo_pago.setText(f"Pago de {f['lote']}")
        self.sub_pago.setText(f"{f['proveedor']} · saldo {fmt.dinero(f['saldo'])}")
        habilitar = self._puede_pagar and f["saldo"] > 0
        for w in (self.monto, self.metodo, self.referencia, self.btn_pagar):
            w.setEnabled(habilitar)
        self.monto.setText(f"{f['saldo']:.2f}" if habilitar else "")
        self.campo_monto.error(None)

    def _nota_monto(self, *_):
        if not self.seleccion:
            return
        m = fmt.leer_dinero(self.monto.text())
        if m is not None and 0 < m < self.seleccion["saldo"]:
            self.campo_monto.ayuda = f"Pago parcial: quedará un saldo de {fmt.dinero(self.seleccion['saldo'] - m)}."
        else:
            self.campo_monto.ayuda = ""
        self.campo_monto.error(None)

    def _pagar(self) -> None:
        f = self.seleccion
        monto, error = monto_positivo(self.monto.text())
        if error or monto > f["saldo"]:
            self.campo_monto.error(error or "El pago no puede ser mayor al saldo.")
            return
        if not confirmar(self, "Aplicar pago", f"Se aplicará un pago de {fmt.dinero(monto)} al lote {f['lote']} "
                         f"de {f['proveedor']}.", "Aplicar pago"):
            return
        try:
            saldo = self.intentar(self.ctx.datos.pagar_lote, f["lote"], monto, self.metodo.currentText(),
                                  self.referencia.text().strip(), mostrar_dialogo=False)
        except ErrorNegocio as exc:
            self.campo_monto.error(exc.mensaje)
            return
        if saldo is None:
            return
        self.referencia.clear()
        self._cargar()
        self.titulo_pago.setText("Pago aplicado")
        self.sub_pago.setText(f"{f['lote']}: saldo restante {fmt.dinero(saldo)}. El pago se refleja como egreso.")
        for w in (self.monto, self.metodo, self.referencia, self.btn_pagar):
            w.setEnabled(False)
        self.monto.clear()

    def _estado_cuenta(self) -> None:
        f = self.seleccion
        provs = self.intentar(self.ctx.datos.proveedores_activos) or []
        destino = next((p["id"] for p in provs if f and p["razon_social"] == f["proveedor"]), self.proveedor.currentData())
        if destino:
            self.ctx.navegar("compras.estado", id_proveedor=destino)


def _resumen(filas: list[dict]) -> str:
    if not filas:
        return "Nada en este rango"
    provs = sorted({f["proveedor"] for f in filas})
    return f"{len(filas)} lote{'s' if len(filas) > 1 else ''} · {', '.join(provs)}"


def _badge(f: dict):
    from app.widgets import Badge
    return Badge(f["estatus"], f["tono"])
