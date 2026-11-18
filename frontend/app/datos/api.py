"""Datos que vienen del middleware. Hoy existen /auth y /pos (middleware/README.md).

Las pantallas cuya ruta todavía no existe reciben `NoConectado` y lo muestran en un
aviso, en lugar de inventar datos.
"""
from datetime import datetime
from decimal import Decimal

from app.api_client import ApiClient, ErrorApi, SesionExpirada
from app.datos import ErrorNegocio, NoConectado

# Ruta que falta en el middleware para cada operación todavía no conectada.
_RUTAS_PENDIENTES = {
    "resumen_inicio": "/reportes/resumen-del-dia",
    "cajas_disponibles": "/pos/cajas", "datos_ultimo_corte": "/pos/cortes", "abrir_caja": "/pos/cajas/abrir",
    "resumen_corte": "/pos/cortes", "cerrar_caja": "/pos/cortes", "clientes_credito_pos": "/finanzas/clientes-credito",
    "buscar_ticket": "/pos/ventas/{folio}", "administradores": "/pos/devoluciones",
    "autorizar": "/pos/devoluciones", "procesar_devolucion": "/pos/devoluciones",
    "lista_proveedores": "/compras/proveedores", "proveedores_activos": "/compras/proveedores",
    "guardar_proveedor": "/compras/proveedores", "siguiente_folio_lote": "/compras/lotes",
    "registrar_lote": "/compras/lotes", "lista_lotes": "/compras/lotes", "detalle_lote": "/compras/lotes/{folio}",
    "cuentas_por_pagar": "/compras/cuentas-por-pagar", "pagar_lote": "/compras/cuentas-por-pagar",
    "estado_cuenta_proveedor": "/compras/proveedores/{id}/estado-de-cuenta",
    "timbres_disponibles": "/facturacion", "ticket_para_factura": "/facturacion",
    "lista_clientes_fiscales": "/facturacion/clientes", "guardar_cliente_fiscal": "/facturacion/clientes",
    "timbrar": "/facturacion/facturas", "detalle_factura": "/facturacion/facturas",
    "lista_facturas": "/facturacion/facturas", "cancelar_factura": "/facturacion/facturas",
    "dashboard": "/finanzas/dashboard", "lista_gastos": "/finanzas/gastos", "registrar_gasto": "/finanzas/gastos",
    "flujo": "/finanzas/flujo", "lista_clientes_credito": "/finanzas/clientes-credito",
    "guardar_cliente_credito": "/finanzas/clientes-credito", "cuentas_por_cobrar": "/finanzas/cuentas-por-cobrar",
    "cajas_abiertas": "/pos/cajas", "registrar_cobro": "/finanzas/cobros",
    "estado_cuenta_cliente": "/finanzas/clientes-credito/{id}/estado-de-cuenta",
    "lista_categorias": "/inventario/categorias", "categorias_activas": "/inventario/categorias",
    "guardar_categoria": "/inventario/categorias", "lista_productos": "/inventario/productos",
    "guardar_producto": "/inventario/productos", "existencias": "/inventario/existencias",
    "lotes_caducidad": "/inventario/lotes", "lotes_de_producto": "/inventario/lotes",
    "movimientos": "/inventario/movimientos", "previsualizar_precios": "/inventario/precios",
    "aplicar_precios": "/inventario/precios", "historial": "/inventario/precios/historial",
    "lista_mermas": "/inventario/mermas", "registrar_merma": "/inventario/mermas",
    "cajeros": "/reportes", "reporte": "/reportes",
    "lista_usuarios": "/admin/usuarios", "nombres_roles": "/admin/roles", "guardar_usuario": "/admin/usuarios",
    "roles": "/admin/roles", "permisos_de": "/admin/roles", "guardar_permisos": "/admin/roles", "crear_rol": "/admin/roles",
    "lista_auditoria": "/admin/auditoria", "configuracion_cajas": "/admin/cajas", "agregar_caja": "/admin/cajas",
    "activar_metodo": "/admin/metodos-pago", "guardar_dispositivos": "/admin/dispositivos",
    "producto": "/inventario/productos",
}


def _dec(v) -> Decimal:
    return Decimal(str(v)) if v is not None else Decimal("0")


class DatosApi:
    es_demo = False

    def __init__(self, api: ApiClient, terminal: str):
        self.api = api
        self.terminal = terminal
        self.ultimo_ticket: dict | None = None
        self.peso_simulado = Decimal("0.800")
        self._caja: dict | None = None

    def __getattr__(self, nombre: str):
        if nombre in _RUTAS_PENDIENTES:
            def pendiente(*_a, **_k):
                raise NoConectado(_RUTAS_PENDIENTES[nombre])
            return pendiente
        raise AttributeError(nombre)

    def _llamar(self, fn, *args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except SesionExpirada:
            raise
        except ErrorApi as exc:
            raise ErrorNegocio(exc.mensaje) from exc

    # ---------------------------------------------------------- sesión
    def login(self, usuario: str, password: str) -> dict:
        try:
            return self.api.login(usuario, password)["perfil"]
        except ErrorApi as exc:
            if exc.status in (401, 422):
                # Mensaje del flujo A del APR (HU-04).
                raise ErrorNegocio("Ingrese un usuario/contraseña correcta.") from exc
            raise ErrorNegocio(exc.mensaje) from exc

    def logout(self) -> None:
        self.api.logout()

    def estado_conexion(self) -> str:
        return "Conectado al servidor"

    def caja_de_sesion(self) -> str | None:
        caja = self.caja_actual()
        return caja["nombre"] if caja else None

    # ---------------------------------------------------------- punto de venta
    def caja_actual(self) -> dict | None:
        try:
            c = self.api.get("/pos/cajas/actual")
        except SesionExpirada:
            raise
        except ErrorApi as exc:
            if exc.status in (403, 404):
                return None
            raise ErrorNegocio(exc.mensaje) from exc
        self._caja = dict(id_caja=c["id_caja"], nombre=f"Caja {c['id_caja']}", terminal=c["terminal"],
                          fondo_inicial=_dec(c["fondo_inicial"]),
                          fecha_apertura=datetime.fromisoformat(c["fecha_apertura"]), cajero=None)
        return self._caja

    def productos_pos(self, busqueda: str | None = None, codigo: str | None = None, frecuentes: bool = False) -> list[dict]:
        filas = self._llamar(self.api.get, "/pos/productos", busqueda=busqueda, codigo=codigo,
                             frecuentes="true" if frecuentes else None)
        return [dict(f, precio_venta=_dec(f["precio_venta"]), existencia=_dec(f["existencia"])) for f in filas]

    def metodos_pago(self) -> list[dict]:
        return self._llamar(self.api.get, "/pos/metodos-pago")

    def leer_bascula(self) -> Decimal:
        # HU-07a: mientras llega el modelo real se usa el simulador (R-01).
        return self.peso_simulado

    def registrar_venta(self, id_caja: int, id_metodo: int, monto_recibido: Decimal, id_cliente: int | None,
                        carrito: list[dict]) -> dict:
        cuerpo = dict(id_caja=id_caja, id_metodo=id_metodo, monto_recibido=str(monto_recibido),
                      id_cliente_credito=id_cliente,
                      carrito=[dict(id_producto=r["id_producto"], cantidad=str(r["cantidad"])) for r in carrito])
        r = self._llamar(self.api.post, "/pos/ventas", cuerpo)
        salida = dict(folio=r["folio"], total=_dec(r["total"]), cambio=_dec(r["cambio"]))
        self.ultimo_ticket = dict(salida, recibido=monto_recibido, fecha=datetime.now(), metodo="", renglones=[])
        return salida

    def ticket_ultimo(self) -> dict | None:
        return self.ultimo_ticket
