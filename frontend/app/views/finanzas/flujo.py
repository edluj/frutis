"""FIN-03 · Flujo de efectivo del periodo (flujo N, HU-37, reporte 5)."""
from app import formato as fmt
from app.theme import C
from app.views.base import Contexto, PaginaBase
from app.widgets import BarrasSimples, Card, Celda, Col, Tabla, boton, columnas, combo, etiqueta


class FlujoView(PaginaBase):
    def __init__(self, ctx: Contexto):
        self.periodo = combo(["Octubre 2026", "Septiembre 2026"])
        super().__init__(ctx, "Finanzas", "Flujo de efectivo",
                         acciones=[self.periodo, boton("Exportar reporte 5", "secundario", self._exportar)])
        if ctx.datos.es_demo:
            self.lbl_estado.setVisible(False)
            self.punto.setVisible(False)
        f = self.intentar(ctx.datos.flujo, self.periodo.currentText())
        if not f:
            self.terminar()
            return
        entradas = f["ventas"] + f["cobros"]
        salidas = f["pagos_proveedores"] + f["gastos"]
        final = f["inicial"] + entradas - salidas
        self.resumen = Tabla([Col("Concepto", estirar=True), Col("Importe", "der", ancho=140)])
        self.resumen.poner_filas([
            ["Saldo inicial del periodo", fmt.dinero(f["inicial"])],
            [Celda("+ Entradas", True, C.VERDE_TEXTO), Celda(fmt.dinero(entradas), True, C.VERDE_TEXTO)],
            ["      Ventas cobradas (efectivo, tarjeta y transferencia)", fmt.dinero(f["ventas"])],
            ["      Cobros a clientes de crédito", fmt.dinero(f["cobros"])],
            [Celda("− Salidas", True, C.ROJO), Celda(fmt.dinero(salidas), True, C.ROJO)],
            ["      Pagos a proveedores", fmt.dinero(f["pagos_proveedores"])],
            ["      Gastos operativos", fmt.dinero(f["gastos"])],
        ], total=[Celda("Saldo final del periodo", True), Celda(fmt.dinero(final), True)])
        nota = etiqueta(f'Las ventas a crédito ({fmt.dinero(f["credito"])}) entran al flujo hasta que el cliente paga. '
                        f'Ver <a href="fin.cxc" style="color:{C.GUINDA}">cuentas por cobrar</a>.', "Muted", rico=True,
                        ajustar=True)
        nota.linkActivated.connect(lambda r: ctx.navegar(r))
        izq = Card("Resumen del periodo").agregar(self.resumen, nota)

        semanas = Tabla([Col("Semana", estirar=True), Col("Entradas", "der"), Col("Salidas", "der"), Col("Saldo", "der")])
        saldo = f["inicial"]
        filas, saldos = [], []
        for nombre, e, s in f["semanas"]:
            saldo += e - s
            saldos.append(float(saldo))
            filas.append([nombre, fmt.dinero(e), fmt.dinero(s), fmt.dinero(saldo)])
        semanas.poner_filas(filas)
        der = Card("Por semana").agregar(semanas, etiqueta("Saldo al cierre de cada semana", "Etiqueta"),
                                         BarrasSimples(saldos, ["#E8B8BC", "#C9737B", "#A63F4B", C.GUINDA]))
        self.agregar(columnas(izq, der))
        self.terminar()

    def _exportar(self) -> None:
        from app.exportar import exportar_tabla
        exportar_tabla(self, self.resumen, "Flujo de efectivo", self.periodo.currentText())
