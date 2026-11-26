"""Datos que vienen del middleware. Hoy existen /auth y /pos (middleware/README.md):
login, cobro, apertura, corte y devoluciones.

Las pantallas cuya ruta todavía no existe reciben `NoConectado` y lo muestran en un
aviso, en lugar de inventar datos.
"""
from datetime import datetime
from decimal import Decimal
from urllib.parse import quote

from app.api_client import ApiClient, ErrorApi, SesionExpirada
from app.datos import ErrorNegocio, NoConectado

# Ruta que falta en el middleware para cada operación todavía no conectada.
_RUTAS_PENDIENTES = {
    "resumen_inicio": "/reportes/resumen-del-dia",
    "clientes_credito_pos": "/finanzas/clientes-credito",
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


# Etiquetas de la pantalla de devolución (POS-04) -> valor del middleware.
REEMBOLSOS = {"Efectivo (sale de la caja)": "efectivo", "Reverso a tarjeta": "tarjeta",
              "Transferencia": "transferencia", "Abono a crédito": "credito"}
FALTAN_OBSERVACIONES = "Escriba las observaciones"


def _dec(v) -> Decimal:
    return Decimal(str(v)) if v is not None else Decimal("0")


def _concepto_venta(v: dict) -> str:
    nombre = v["metodo"].lower()
    if v["es_efectivo"]:
        return "Ventas en efectivo"
    if v["es_credito"]:
        return "Ventas a crédito"
    return f"Ventas con {nombre}" if nombre.startswith("tarjeta") else f"Ventas por {nombre}"


class DatosApi:
    es_demo = False

    def __init__(self, api: ApiClient, terminal: str):
        self.api = api
        self.terminal = terminal
        self.ultimo_ticket: dict | None = None
        self.peso_simulado = Decimal("0.800")
        self._caja: dict | None = None
        self._caja_corte: int | None = None
        self._administradores: dict[str, str] = {}
        # (folio del ticket, autorización firmada) que dio el Administrador para ese ticket.
        self._autorizacion: tuple[str, str] | None = None

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
        self._caja = self._caja_de(c)
        return self._caja

    @staticmethod
    def _caja_de(c: dict) -> dict:
        return dict(id_caja=c["id_caja"], nombre=f"Caja {c['id_caja']}", terminal=c["terminal"],
                    fondo_inicial=_dec(c["fondo_inicial"]),
                    fecha_apertura=datetime.fromisoformat(c["fecha_apertura"]), cajero=None)

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

    # ---------------------------------------------------------- apertura y corte (HU-15, HU-09)
    def cajas_disponibles(self) -> list[dict]:
        # La caja es la terminal donde corre la aplicación (FRUTIS_TERMINAL).
        return [dict(id_caja=self.terminal, nombre=f"Terminal {self.terminal}")]

    def datos_ultimo_corte(self, terminal: str) -> dict | None:
        try:
            c = self.api.get("/pos/cortes/ultimo", terminal=terminal or self.terminal)
        except SesionExpirada:
            raise
        except ErrorApi as exc:
            if exc.status == 404:
                return None
            raise ErrorNegocio(exc.mensaje) from exc
        return dict(fecha=datetime.fromisoformat(c["fecha_cierre"]), cajero=c["cajero"],
                    esperado=_dec(c["efectivo_esperado"]), contado=_dec(c["efectivo_contado"]),
                    observaciones=c["observaciones"] or "Sin observaciones")

    def abrir_caja(self, terminal: str, fondo: Decimal) -> dict:
        c = self._llamar(self.api.post, "/pos/cajas", dict(terminal=terminal or self.terminal, fondo_inicial=str(fondo)))
        self._caja = self._caja_de(c)
        return self._caja

    def resumen_corte(self) -> dict | None:
        try:
            r = self.api.get("/pos/cortes/actual")
        except SesionExpirada:
            raise
        except ErrorApi as exc:
            if exc.status in (403, 404):
                return None
            raise ErrorNegocio(exc.mensaje) from exc
        filas = [dict(concepto="Fondo inicial", tickets=None, importe=_dec(r["fondo_inicial"]))]
        filas += [dict(concepto=_concepto_venta(v), tickets=v["tickets"], importe=_dec(v["importe"])) for v in r["ventas"]]
        cobros, devoluciones = r["cobros_efectivo"], r["devoluciones_efectivo"]
        if cobros["cantidad"]:
            filas.append(dict(concepto="Cobros a clientes en efectivo", tickets=cobros["cantidad"],
                              importe=_dec(cobros["importe"])))
        filas.append(dict(concepto="Devoluciones en efectivo", tickets=devoluciones["cantidad"],
                          importe=-_dec(devoluciones["importe"])))
        self._caja_corte = r["id_caja"]
        return dict(filas=filas, esperado=_dec(r["efectivo_esperado"]),
                    desde=datetime.fromisoformat(r["fecha_apertura"]),
                    tickets=sum(v["tickets"] for v in r["ventas"]), caja=f"Caja {r['id_caja']}")

    def cerrar_caja(self, contado: Decimal, observaciones: str) -> dict:
        id_caja = self._caja_corte or (self.caja_actual() or {}).get("id_caja")
        if id_caja is None:
            raise ErrorNegocio("No hay una caja abierta.")
        cuerpo = dict(id_caja=id_caja, efectivo_contado=str(contado), observaciones=observaciones or None)
        try:
            r = self.api.post("/pos/cortes", cuerpo)
        except SesionExpirada:
            raise
        except ErrorApi as exc:
            if exc.status == 422 and any(str(e.get("campo", "")).endswith("observaciones") for e in exc.errores or []):
                raise ErrorNegocio("Las observaciones no pueden llevar comillas, punto y coma ni los signos < >.",
                                   campo="observaciones") from exc
            campo = "observaciones" if exc.mensaje.startswith(FALTAN_OBSERVACIONES) else None
            raise ErrorNegocio(exc.mensaje, campo=campo) from exc
        self._caja = None
        self._caja_corte = None
        return dict(contado=_dec(r["efectivo_contado"]), diferencia=_dec(r["diferencia"]),
                    esperado=_dec(r["efectivo_esperado"]))

    # ---------------------------------------------------------- devoluciones (HU-30, SC-02)
    def buscar_ticket(self, folio: str) -> dict:
        t = self._llamar(self.api.get, f"/pos/ventas/{quote(folio.strip().upper(), safe='')}")
        renglones = [dict(id_producto=r["id_producto"], nombre=r["nombre"], unidad=r["unidad_venta"],
                          cantidad=_dec(r["cantidad"]), precio=_dec(r["precio_unitario"]), importe=_dec(r["importe"]),
                          devuelto=_dec(r["devuelto"])) for r in t["renglones"]]
        return dict(folio=t["folio"], fecha=datetime.fromisoformat(t["fecha"]), metodo=t["metodo"],
                    es_credito=t["es_credito"], facturado=t["facturado"], total=_dec(t["total"]),
                    renglones=renglones, cliente=t["cliente"])

    def administradores(self) -> list[str]:
        filas = self._llamar(self.api.get, "/pos/devoluciones/administradores")
        self._administradores = {a["nombre_completo"]: a["usuario"] for a in filas}
        return list(self._administradores)

    def autorizar(self, nombre_admin: str, password: str, folio: str | None = None) -> str:
        if not folio:
            raise ErrorNegocio("Busca primero el ticket que se va a devolver.")
        usuario = self._administradores.get(nombre_admin)
        if usuario is None:
            raise ErrorNegocio("Elige un Administrador de la lista.")
        r = self._llamar(self.api.post, "/pos/devoluciones/autorizacion",
                         dict(usuario=usuario, password=password, folio_venta=folio))
        self._autorizacion = (folio, r["autorizacion"])
        return f"Autorizado por {r['autorizado_por']} a las {datetime.now():%H:%M}."

    def procesar_devolucion(self, folio: str, renglones: list[dict], motivo: str, reembolso: str, admin: str) -> dict:
        if self._autorizacion is None or self._autorizacion[0] != folio:
            raise ErrorNegocio("Falta la autorización del Administrador para este ticket.")
        caja = self._caja or self.caja_actual()
        if caja is None:
            raise ErrorNegocio("Abre la caja para registrar devoluciones.")
        cuerpo = dict(id_caja=caja["id_caja"], folio_venta=folio, motivo=motivo,
                      reembolso=REEMBOLSOS.get(reembolso, reembolso), autorizacion=self._autorizacion[1],
                      renglones=[dict(id_producto=r["id_producto"], cantidad=str(r["cantidad"]),
                                      estado="bueno" if r["buen_estado"] else "danado") for r in renglones])
        r = self._llamar(self.api.post, "/pos/devoluciones", cuerpo)
        self._autorizacion = None
        return dict(total=_dec(r["total"]), folio=r["folio"])
