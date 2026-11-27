"""Datos que vienen del middleware. Hoy existen /auth, /pos, parte de /inventario y de
/compras (middleware/README.md): login, cobro, apertura, corte, devoluciones, categorías,
productos, proveedores y lotes de compra.

Las pantallas cuya ruta todavía no existe reciben `NoConectado` y lo muestran en un
aviso, en lugar de inventar datos.
"""
from datetime import date, datetime
from decimal import Decimal
from urllib.parse import quote

from app.api_client import ApiClient, ErrorApi, SesionExpirada
from app.datos import ErrorNegocio, NoConectado

# Ruta que falta en el middleware para cada operación todavía no conectada.
_RUTAS_PENDIENTES = {
    "resumen_inicio": "/reportes/resumen-del-dia",
    "clientes_credito_pos": "/finanzas/clientes-credito",
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
    "existencias": "/inventario/existencias",
    "lotes_caducidad": "/inventario/lotes", "lotes_de_producto": "/inventario/lotes",
    "movimientos": "/inventario/movimientos", "previsualizar_precios": "/inventario/precios",
    "aplicar_precios": "/inventario/precios", "historial": "/inventario/precios/historial",
    "lista_mermas": "/inventario/mermas", "registrar_merma": "/inventario/mermas",
    "cajeros": "/reportes", "reporte": "/reportes",
    "lista_usuarios": "/admin/usuarios", "nombres_roles": "/admin/roles", "guardar_usuario": "/admin/usuarios",
    "roles": "/admin/roles", "permisos_de": "/admin/roles", "guardar_permisos": "/admin/roles", "crear_rol": "/admin/roles",
    "lista_auditoria": "/admin/auditoria", "configuracion_cajas": "/admin/cajas", "agregar_caja": "/admin/cajas",
    "activar_metodo": "/admin/metodos-pago", "guardar_dispositivos": "/admin/dispositivos",
}


# Filtro "Existencia" de productos (CAT-02) -> valor del middleware, y color de cada estado.
FILTRO_EXISTENCIA = {"Todas": "todas", "Bajo el mínimo": "bajo", "Por caducar": "por_caducar"}
TONO_ESTADO = {"Normal": "verde", "Bajo": "rojo", "Sin existencia": "rojo", "Por caducar": "naranja"}


# Estatus del proveedor (PRV-01) y motivos de merma de la base -> texto de pantalla.
ESTATUS_PROVEEDOR = {"Activos": "activos", "Inactivos": "inactivos", "Todos": "todos"}
MOTIVOS_MERMA = {"maduracion": "Maduración", "golpe": "Golpe", "caducidad": "Caducidad",
                 "devolucion": "Devolución en mal estado", "otro": "Otro"}
TONO_PAGO = {"Pagado": "verde", "Vencido": "rojo", "Pendiente": "naranja"}


def _estatus_cxp(saldo: Decimal, vence: date | None) -> tuple[str, str]:
    """Mismo texto que el modo demostración para la cuenta por pagar de un lote."""
    if saldo <= 0 or vence is None:
        return "Pagado", "verde"
    dias = (vence - date.today()).days
    if dias < 0:
        return f"Vencida · {-dias} días", "rojo"
    if dias <= 3:
        return (f"Vence en {dias} días" if dias != 1 else "Vence mañana"), "naranja"
    return "Pendiente", "gris"


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
            raise ErrorNegocio(exc.mensaje, exc.campo) from exc

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

    # ---------------------------------------------------------- catálogo (HU-22, HU-10)
    @staticmethod
    def _categoria_de(c: dict) -> dict:
        return dict(id=c["id_categoria"], nombre=c["nombre"], descripcion=c["descripcion"] or "",
                    activa=c["activo"], productos=c["productos_activos"])

    def lista_categorias(self, busqueda: str = "") -> list[dict]:
        filas = self._llamar(self.api.get, "/inventario/categorias", busqueda=busqueda or None)
        return [self._categoria_de(c) for c in filas]

    def categorias_activas(self) -> list[dict]:
        return [self._categoria_de(c) for c in self._llamar(self.api.get, "/inventario/categorias", activas=True)]

    def guardar_categoria(self, datos: dict) -> None:
        cuerpo = dict(nombre=datos["nombre"], descripcion=datos.get("descripcion") or None,
                      activo=datos.get("activa", True))
        if datos.get("id"):
            self._llamar(self.api.put, f"/inventario/categorias/{datos['id']}", cuerpo)
        else:
            self._llamar(self.api.post, "/inventario/categorias", cuerpo)

    @staticmethod
    def _producto_de(p: dict) -> dict:
        return dict(p, unidad_venta="kg" if p["unidad_venta"] == "kg" else "pza",
                    precio_venta=_dec(p["precio_venta"]), costo=_dec(p["costo_actual"]),
                    tasa_iva=_dec(p["tasa_iva"]), stock_minimo=_dec(p["stock_minimo"]),
                    existencia=_dec(p["existencia"]), tono=TONO_ESTADO[p["estado"]])

    def lista_productos(self, busqueda: str = "", id_categoria=None, existencia: str = "Todas") -> list[dict]:
        filas = self._llamar(self.api.get, "/inventario/productos", busqueda=busqueda or None,
                             id_categoria=id_categoria, existencia=FILTRO_EXISTENCIA.get(existencia, "todas"))
        return [self._producto_de(p) for p in filas]

    def producto(self, id_producto: int) -> dict:
        return next(p for p in self.lista_productos() if p["id_producto"] == id_producto)

    def guardar_producto(self, datos: dict) -> None:
        cuerpo = dict(codigo_barras=datos["codigo_barras"], nombre=datos["nombre"], id_categoria=datos["id_categoria"],
                      unidad_venta="kg" if datos["unidad_venta"] == "kg" else "pieza",
                      precio_venta=str(datos["precio_venta"]), stock_minimo=str(datos["stock_minimo"]),
                      activo=datos.get("activo", True))
        if datos.get("id_producto"):
            # Al editar se conservan los campos que la pantalla no muestra.
            actual = self.producto(datos["id_producto"])
            cuerpo.update(tasa_iva=str(actual["tasa_iva"]), es_frecuente=actual["es_frecuente"])
            self._llamar(self.api.put, f"/inventario/productos/{datos['id_producto']}", cuerpo)
        else:
            self._llamar(self.api.post, "/inventario/productos", cuerpo)

    # ---------------------------------------------------------- compras (HU-23, HU-11)
    @staticmethod
    def _proveedor_de(p: dict) -> dict:
        return dict(p, id=p["id_proveedor"], correo=p["correo"] or "", direccion=p["direccion"] or "",
                    saldo=_dec(p["saldo"]))

    def lista_proveedores(self, busqueda: str = "", estatus: str = "Activos") -> list[dict]:
        filas = self._llamar(self.api.get, "/compras/proveedores", busqueda=busqueda or None,
                             estatus=ESTATUS_PROVEEDOR.get(estatus, "activos"))
        return [self._proveedor_de(p) for p in filas]

    def proveedores_activos(self) -> list[dict]:
        return self.lista_proveedores()

    def guardar_proveedor(self, datos: dict) -> bool:
        cuerpo = dict(razon_social=datos["razon_social"], rfc=datos["rfc"], telefono=datos["telefono"],
                      correo=datos.get("correo") or None, direccion=datos.get("direccion") or None,
                      dias_credito=datos["dias_credito"], activo=datos.get("activo", True))
        if datos.get("id"):
            self._llamar(self.api.put, f"/compras/proveedores/{datos['id']}", cuerpo)
        else:
            self._llamar(self.api.post, "/compras/proveedores", cuerpo)
        return True

    def siguiente_folio_lote(self) -> str:
        return self._llamar(self.api.get, "/compras/lotes/siguiente-folio")["folio"]

    def registrar_lote(self, datos: dict) -> str:
        cuerpo = dict(id_proveedor=datos["id_proveedor"], factura=datos.get("factura") or None,
                      entrada=datos["entrada"].isoformat(), dias_credito=datos["dias"] or 0,
                      renglones=[dict(id_producto=r["id_producto"], cantidad=str(r["cantidad"]), costo=str(r["costo"]),
                                      caducidad=r["caducidad"].isoformat()) for r in datos["renglones"]])
        return self._llamar(self.api.post, "/compras/lotes", cuerpo)["folio"]

    def lista_lotes(self, id_proveedor=None, desde=None, hasta=None, pago="Todos") -> dict:
        filas = []
        for f in self._llamar(self.api.get, "/compras/lotes", id_proveedor=id_proveedor,
                              desde=desde.isoformat() if desde else None, hasta=hasta.isoformat() if hasta else None,
                              pago=pago):
            dias = f["dias_credito"]
            filas.append(dict(folio=f["folio"], proveedor=f["proveedor"], entrada=date.fromisoformat(f["entrada"]),
                              productos=f["productos"], total=_dec(f["total"]), kilos=_dec(f["kilos"]),
                              condicion="Contado" if dias == 0 else f"Crédito {dias} días", pago=f["pago"],
                              tono=TONO_PAGO[f["pago"]], saldo=_dec(f["saldo"]),
                              caducidad=date.fromisoformat(f["caducidad"])))
        total = sum((f["total"] for f in filas), Decimal("0"))
        kilos = sum((f["kilos"] for f in filas), Decimal("0"))
        pendientes = [f for f in filas if f["pago"] != "Pagado"]
        return dict(filas=filas, total=total, kilos=kilos, proveedores=len({f["proveedor"] for f in filas}),
                    costo_promedio=(total / kilos if kilos else Decimal("0")), pendientes=len(pendientes),
                    por_pagar=sum((f["saldo"] for f in pendientes), Decimal("0")))

    def detalle_lote(self, folio: str) -> dict:
        d = self._llamar(self.api.get, f"/compras/lotes/{quote(folio)}")
        productos = [dict(r, unidad=r["unidad_venta"], recibido=_dec(r["recibido"]), costo=_dec(r["costo"]),
                          vendido=_dec(r["vendido"]), merma=_dec(r["merma"]), existencia=_dec(r["existencia"]),
                          caducidad=date.fromisoformat(r["caducidad"])) for r in d["productos"]]
        mermas = [dict(fecha=date.fromisoformat(m["fecha"]), producto=m["producto"], cantidad=_dec(m["cantidad"]),
                       motivo=MOTIVOS_MERMA.get(m["motivo"], m["motivo"]), costo=_dec(m["costo"])) for m in d["mermas"]]
        entrada = date.fromisoformat(d["entrada"])
        vence = date.fromisoformat(d["vence"]) if d["vence"] else None
        saldo = _dec(d["saldo"])
        estatus, tono = _estatus_cxp(saldo, vence)
        return dict(folio=d["folio"], proveedor=d["proveedor"], entrada=entrada, factura=d["factura"] or "",
                    total=_dec(d["total"]), dias=d["dias_credito"], vence=vence or entrada,
                    recibido=sum((p["recibido"] for p in productos), Decimal("0")),
                    vendido=sum((p["vendido"] for p in productos), Decimal("0")),
                    merma=sum((p["merma"] for p in productos), Decimal("0")),
                    costo_merma=sum((m["costo"] for m in mermas), Decimal("0")),
                    productos=productos, mermas=mermas, pagado=_dec(d["pagado"]), saldo=saldo,
                    estatus=estatus, tono=tono)
