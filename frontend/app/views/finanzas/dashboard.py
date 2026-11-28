"""FIN-01 · Dashboard financiero: ingresos contra egresos (flujo L, HU-27)."""
from app import formato as fmt
from app.theme import C
from app.views.base import Contexto, PaginaBase
from app.widgets import (
    Card, Celda, Col, GraficaBarras, Kpi, Tabla, boton, columnas, combo, etiqueta, fila_kpis, hbox, leyenda,
)


class DashboardView(PaginaBase):
    def __init__(self, ctx: Contexto):
        self.periodo = combo(["Octubre 2026", "Septiembre 2026", "Agosto 2026"] if ctx.datos.es_demo else fmt.meses_recientes(3))
        super().__init__(ctx, "Finanzas", "Dashboard financiero", acciones=[etiqueta("Periodo", "Etiqueta"), self.periodo])
        if ctx.datos.es_demo:
            self.lbl_estado.setVisible(False)
            self.punto.setVisible(False)
        d = self.intentar(ctx.datos.dashboard, self.periodo.currentText())
        if not d:
            self.terminar()
            return
        self.agregar(fila_kpis(
            Kpi("Ingresos (ventas)", fmt.dinero(d["ingresos"]), f"{d['tickets']:,} tickets"),
            Kpi("Egresos", fmt.dinero(d["egresos"]),
                f"Compras {fmt.dinero(d['compras'])[:-3]} · gastos {fmt.dinero(d['gastos'])[:-3]}"),
            Kpi("Utilidad", fmt.dinero(d["utilidad"]), "Antes de impuestos", C.VERDE if d["utilidad"] >= 0 else C.ROJO),
            Kpi("Margen", fmt.porcentaje(d["margen"]), f"Mes anterior: {fmt.porcentaje(d['margen_anterior'])}"),
        ))
        grafica = GraficaBarras([(s, f"Utilidad {fmt.dinero(i - e)[:-3]}", (i, e)) for s, i, e in d["semanas"]],
                                [C.VERDE, C.CAFE], alto=300)
        g = Card("Ingresos contra egresos por semana", derecha=[envolver_leyenda()]).agregar(grafica)

        t = Tabla([Col("Concepto", estirar=True), Col("Importe", "der"), Col("% de egresos", "der")])
        t.poner_filas([[c["concepto"], fmt.dinero(c["importe"]), fmt.porcentaje(c["pct"])] for c in d["conceptos"]],
                      total=[Celda("Total", True), Celda(fmt.dinero(d["egresos"]), True), Celda("100 %", True)])
        dinero = Card("¿En qué se fue el dinero?").agregar(t)
        if ctx.sesion.puede("finanzas", "crear"):
            dinero.agregar(hbox(boton("Registrar gasto", "secundario", lambda: ctx.navegar("fin.gastos")), "stretch"))
        self.agregar(columnas(g, dinero))
        self.terminar()


def envolver_leyenda():
    from app.widgets import envolver
    return envolver(leyenda((C.VERDE, "Ingresos"), (C.CAFE, "Egresos")))
