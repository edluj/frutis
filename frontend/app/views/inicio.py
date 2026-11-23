"""ACC-02 · Inicio: resumen del día, módulos permitidos y alertas."""
from datetime import datetime

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QGridLayout, QPushButton

from app import formato as fmt
from app.iconos import icono
from app.theme import C
from app.views.base import Contexto, PaginaBase
from app.widgets import Card, Kpi, columnas, etiqueta, fila_kpis


class InicioView(PaginaBase):
    def __init__(self, ctx: Contexto):
        ahora = datetime.now()
        if ctx.datos.es_demo:
            from app.datos.demo import HOY
            ahora = datetime.combine(HOY, ahora.time())
        super().__init__(ctx, fmt.fecha_larga(ahora.date()), f"{fmt.saludo(ahora)}, {ctx.sesion.primer_nombre}")
        estado = ctx.datos.estado_conexion()
        if ctx.sesion.caja:
            estado += f" · {ctx.sesion.caja} abierta"
        self.poner_estado(estado, C.NARANJA if ctx.datos.es_demo else C.VERDE)

        r = self.intentar(ctx.datos.resumen_inicio)
        if r:
            caja = r["caja"]
            self.agregar(fila_kpis(
                Kpi("Ventas de hoy", fmt.dinero(r["ventas_hoy"]),
                    f"{r['tickets']} tickets · ticket promedio {fmt.dinero(r['ticket_promedio'])}"),
                Kpi("Caja", "Abierta" if caja["abierta"] else "Cerrada", caja["detalle"],
                    C.VERDE if caja["abierta"] else C.TEXTO_SUAVE),
                Kpi("Lotes por caducar (3 días)", str(r["caducar"]), r["caducar_detalle"], C.NARANJA),
                Kpi("Por cobrar a crédito", fmt.dinero(r["por_cobrar"]), r["por_cobrar_detalle"]),
            ))

        modulos = Card("Módulos")
        grid = QGridLayout()
        grid.setSpacing(14)
        for i, (clave, nombre, ic) in enumerate(ctx.sesion.modulos_menu):
            b = QPushButton(nombre)
            b.setProperty("tipo", "modulo")
            b.setIcon(icono(ic, C.GUINDA, 24))
            b.setIconSize(QSize(24, 24))
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setMinimumHeight(96)
            b.clicked.connect(lambda _=False, c=clave: self._abrir(c))
            grid.addWidget(b, i // 2, i % 2)
        modulos.agregar(grid)

        alertas = Card("Alertas")
        if r:
            for etiqueta_, texto_, tono in r["alertas"]:
                alertas.agregar(_alerta(etiqueta_, texto_, tono))
            if not r["alertas"]:
                alertas.agregar(etiqueta("Sin alertas por ahora.", "Muted"))
        else:
            alertas.agregar(etiqueta("Las alertas aparecerán cuando el servidor exponga el resumen del día.", "Muted",
                                     ajustar=True))
        self.agregar(columnas(modulos, alertas))
        self.terminar()

    def _abrir(self, modulo: str) -> None:
        from app.views.shell import INICIO_MODULO
        self.ctx.navegar("pos" if modulo == "pos" else INICIO_MODULO[modulo])


def _alerta(prefijo: str, texto_: str, tono: str):
    fondo, color = (C.NARANJA_SUAVE, C.NARANJA_TEXTO) if tono == "naranja" else (C.ROJO_SUAVE, C.ROJO)
    html = (f"<table><tr><td style='padding-right:12px'><b>{prefijo}</b></td><td>{texto_}</td></tr></table>"
            if prefijo else f"<b>{texto_}</b>")
    lbl = etiqueta(html, rico=True, ajustar=True)
    lbl.setStyleSheet(f"background: {fondo}; color: {color}; border-radius: 10px; padding: 12px 14px; font-size: 14px;")
    return lbl
