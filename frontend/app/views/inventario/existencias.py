"""CAT-03 · Existencias y alertas de stock (HU-24)."""
from datetime import datetime

from PySide6.QtCore import Qt

from app import formato as fmt
from app.theme import C
from app.views.base import Contexto, PaginaBase
from app.widgets import Barra, Campo, Card, Celda, Col, Kpi, Tabla, boton, combo, entrada, etiqueta, fila_kpis, hbox


class ExistenciasView(PaginaBase):
    def __init__(self, ctx: Contexto):
        ahora = datetime.now()
        super().__init__(ctx, "Catálogo e Inventario", "Existencias",
                         estado=f"Actualizado {fmt.fecha_corta(ahora.date())}, {ahora:%H:%M}")
        self.k_valor = Kpi("Valor del inventario al costo", "—")
        self.k_bajo = Kpi("Bajo el mínimo", "—", color=C.ROJO)
        self.k_sin = Kpi("Sin existencia", "—", color=C.ROJO)
        ver = etiqueta(f'<a href="inv.lotes" style="color:{C.GUINDA}">Ver lotes</a>', rico=True)
        ver.linkActivated.connect(lambda r: ctx.navegar(r))
        self.k_cad = Kpi("Lotes por caducar (3 días)", "—", color=C.NARANJA, detalle_widget=ver)
        self.agregar(fila_kpis(self.k_valor, self.k_bajo, self.k_sin, self.k_cad))

        cats = self.intentar(ctx.datos.categorias_activas) or []
        self.buscar = entrada(placeholder="Nombre del producto")
        self.buscar.textChanged.connect(self._cargar)
        self.categoria = combo([("Todas", None)] + [(c["nombre"], c["id"]) for c in cats])
        self.mostrar = combo(["Todos", "Bajo el mínimo", "Sin existencia"])
        self.categoria.currentIndexChanged.connect(self._cargar)
        self.mostrar.currentIndexChanged.connect(self._cargar)
        self.tabla = Tabla([Col("Producto", estirar=True), Col("Existencia", "der"), Col("Mínimo", "der"),
                            Col("Contra el mínimo", ancho=170), Col("Venta diaria", "der"), Col("Alcanza para", "der"),
                            Col("Lotes", "der"), Col("Valor al costo", "der")])
        self.tabla.fila_elegida.connect(lambda f: self.tabla.dato(f) and ctx.navegar(
            "inv.movimientos", id_producto=self.tabla.dato(f)["id_producto"]))
        self.agregar(Card().agregar(
            hbox((Campo("Buscar producto", self.buscar), 2), (Campo("Categoría", self.categoria), 1),
                 (Campo("Mostrar", self.mostrar), 1), boton("Exportar", "secundario", self._exportar),
                 alinear=Qt.AlignmentFlag.AlignBottom),
            self.tabla,
            etiqueta("La barra llena equivale a tres veces el stock mínimo. La venta diaria es el promedio de los últimos "
                     "14 días. Toca un producto para ver sus movimientos.", "Muted", ajustar=True)))
        self.terminar()
        self._cargar()

    def _cargar(self, *_):
        r = self.intentar(self.ctx.datos.existencias, self.buscar.text().strip(), self.categoria.currentData(),
                          self.mostrar.currentText())
        if not r:
            return
        self.k_valor.poner(fmt.dinero(r["valor"]), f"{r['con_mov']} productos con movimiento")
        self.k_bajo.poner(str(len(r["bajos"])), ", ".join(f["nombre"] for f in r["bajos"]) or "Ninguno")
        self.k_sin.poner(str(len(r["sin"])), ", ".join(f["nombre"] for f in r["sin"]) or "Ninguno")
        self.k_cad.poner(str(r["caducar"]))
        filas, tonos = [], {}
        for i, f in enumerate(r["filas"]):
            u = f["unidad"]
            dec = 1 if u == "kg" else 0
            if f["bajo"]:
                tonos[i] = "rojo"
            frac = float(f["existencia"] / (f["minimo"] * 3)) if f["minimo"] else 1.0
            filas.append([Celda(f["nombre"], True), fmt.cantidad(f["existencia"], u, dec), f"{f['minimo']:.0f} {u}",
                          Barra(frac, C.ROJO if f["bajo"] else C.VERDE, ancho_min=130),
                          f"{f['diaria']:.0f} {u}" if f["diaria"] else "—",
                          f"{f['alcanza']:.1f} días" if f["alcanza"] is not None and f["existencia"] > 0 else "—",
                          str(f["lotes"]), fmt.dinero(f["valor"])])
        self.tabla.poner_filas(filas, datos=r["filas"], tonos=tonos)

    def _exportar(self) -> None:
        from app.exportar import exportar_tabla
        exportar_tabla(self, self.tabla, "Existencias", self.lbl_estado.text(), formato="xlsx")
