"""CAT-04 · Lotes y caducidades (FEFO, HU-24)."""
from app import formato as fmt
from app.views.base import Contexto, PaginaBase
from app.widgets import Alerta, Badge, Campo, Card, Celda, Col, Tabla, boton, combo, hbox


class LotesCaducidadView(PaginaBase):
    def __init__(self, ctx: Contexto):
        super().__init__(ctx, "Catálogo e Inventario", "Lotes y caducidades",
                         acciones=[boton("Registrar merma", "secundario", lambda: ctx.navegar("inv.mermas"))])
        self.agregar(Alerta("El cobro descuenta primero el lote que caduca antes. Revisa a diario los lotes en naranja y "
                            "rojo para ofertarlos o registrarlos como merma.", "naranja"))
        productos = self.intentar(ctx.datos.lista_productos) or []
        proveedores = self.intentar(ctx.datos.proveedores_activos) or []
        self.producto = combo([("Todos", None)] + [(p["nombre"], p["id_producto"]) for p in productos])
        self.dias = combo([("Próximos 3 días", 3), ("Próximos 7 días", 7), ("Próximos 15 días", 15), ("Todos", 3650)], 7)
        self.proveedor = combo([("Todos", None)] + [(p["razon_social"], p["id"]) for p in proveedores])
        for c in (self.producto, self.dias, self.proveedor):
            c.currentIndexChanged.connect(self._cargar)
        self.tabla = Tabla([Col("Caducidad"), Col("Producto", estirar=True), Col("Lote"), Col("Proveedor"),
                            Col("Recibido", "der"), Col("Queda", "der"), Col("Costo de lo que queda", "der"), Col("")])
        self.agregar(Card().agregar(hbox(Campo("Producto", self.producto), Campo("Caducan en", self.dias),
                                         Campo("Proveedor", self.proveedor)), self.tabla))
        self.terminar()
        self._cargar()

    def _cargar(self, *_):
        filas = self.intentar(self.ctx.datos.lotes_caducidad, self.producto.currentData(), self.dias.currentData(),
                              self.proveedor.currentData()) or []
        puede = self.ctx.sesion.puede("inventario", "crear")
        salida = []
        for f in filas:
            cuando = "hoy" if f["dias"] == 0 else "mañana" if f["dias"] == 1 else f"{f['dias']} días"
            u = f["unidad"]
            salida.append([
                Badge(f"{f['caducidad']:%d/%m} · {cuando}", f["tono"]), Celda(f["producto"], True),
                boton(f["lote"], "link", lambda f=f: self.ctx.navegar("compras.lote", folio=f["lote"]))
                if self.ctx.sesion.puede("compras") else f["lote"],
                f["proveedor"], fmt.cantidad(f["recibido"], u, 1 if u == "kg" else 0), f["queda_txt"], fmt.dinero(f["costo"]),
                boton("Merma", "link", lambda f=f: self.ctx.navegar("inv.mermas", id_producto=f["id_producto"], lote=f["lote"]))
                if puede else ""])
        self.tabla.poner_filas(salida, datos=filas)
