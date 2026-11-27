"""Datos que vienen del middleware. Hoy existen /auth, /pos, parte de /inventario y de
/compras (middleware/README.md): login, cobro, apertura, corte, devoluciones, categorías,
productos, mermas, proveedores, lotes de compra, clientes de crédito, usuarios y facturación
(con el PAC simulado de SC-05).

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
    "dashboard": "/finanzas/dashboard", "lista_gastos": "/finanzas/gastos", "registrar_gasto": "/finanzas/gastos",
    "flujo": "/finanzas/flujo", "cuentas_por_cobrar": "/finanzas/cuentas-por-cobrar",
    "cajas_abiertas": "/pos/cajas", "registrar_cobro": "/finanzas/cobros",
    "estado_cuenta_cliente": "/finanzas/clientes-credito/{id}/estado-de-cuenta",
    "cajeros": "/reportes", "reporte": "/reportes",
    "roles": "/admin/roles", "permisos_de": "/admin/roles", "guardar_permisos": "/admin/roles", "crear_rol": "/admin/roles",
    "lista_auditoria": "/admin/auditoria", "configuracion_cajas": "/admin/cajas", "agregar_caja": "/admin/cajas",
    "activar_metodo": "/admin/metodos-pago", "guardar_dispositivos": "/admin/dispositivos",
}


# Filtro "Existencia" de productos (CAT-02) -> valor del middleware, y color de cada estado.
FILTRO_EXISTENCIA = {"Todas": "todas", "Bajo el mínimo": "bajo", "Por caducar": "por_caducar"}
TONO_ESTADO = {"Normal": "verde", "Bajo": "rojo", "Sin existencia": "rojo", "Por caducar": "naranja"}


# Estatus del proveedor (PRV-01) y motivos de merma de la base -> texto de pantalla.
ESTATUS_PROVEEDOR = {"Activos": "activos", "Inactivos": "inactivos", "Todos": "todos"}
MOTIVOS_MERMA = {"maduracion": "Maduración", "golpe": "Golpe", "plaga": "Plaga u hongo", "caducidad": "Caducidad",
                 "devolucion": "Devolución en mal estado", "otro": "Otro"}
MOTIVO_DE_PANTALLA = {v: k for k, v in MOTIVOS_MERMA.items()}
MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre",
         "Noviembre", "Diciembre"]
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


# Estatus de los clientes de crédito (FIN-04).
FILTRO_CLIENTES = {"Activo": "activos", "Pago vencido": "activos", "Suspendido": "suspendidos"}


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

    # ---------------------------------------------------------- existencias y caducidades (HU-24)
    def lotes_caducidad(self, id_producto=None, dias: int = 7, id_proveedor=None) -> list[dict]:
        filas = self._llamar(self.api.get, "/inventario/lotes", dias=dias, id_producto=id_producto,
                             id_proveedor=id_proveedor)
        salida = []
        for f in filas:
            queda, unidad = _dec(f["queda"]), f["unidad_venta"]
            salida.append(dict(caducidad=date.fromisoformat(f["caducidad"]), dias=f["dias"], producto=f["producto"],
                               id_producto=f["id_producto"], lote=f["lote"], proveedor=f["proveedor"],
                               recibido=_dec(f["recibido"]), queda=queda, unidad=unidad,
                               queda_txt=f"{queda:.1f} kg" if unidad == "kg" else f"{queda:.0f} pza",
                               costo=_dec(f["costo"]),
                               tono="rojo" if f["dias"] <= 1 else "naranja" if f["dias"] <= 3 else "gris"))
        return salida

    def existencias(self, busqueda: str = "", id_categoria=None, mostrar: str = "Todos") -> dict:
        todos = []
        for f in self._llamar(self.api.get, "/inventario/existencias"):
            ex, diaria, minimo = _dec(f["existencia"]), _dec(f["venta_diaria"]), _dec(f["stock_minimo"])
            todos.append(dict(id_producto=f["id_producto"], id_categoria=f["id_categoria"], nombre=f["nombre"],
                              unidad="kg" if f["unidad_venta"] == "kg" else "pza", existencia=ex, minimo=minimo,
                              diaria=diaria, alcanza=(ex / diaria) if diaria else None, lotes=f["lotes"],
                              valor=_dec(f["valor"]), bajo=ex < minimo))
        filas = [f for f in todos
                 if (not busqueda or busqueda.lower() in f["nombre"].lower())
                 and (not id_categoria or f["id_categoria"] == id_categoria)
                 and not (mostrar == "Bajo el mínimo" and not f["bajo"])
                 and not (mostrar == "Sin existencia" and f["existencia"] > 0)]
        return dict(filas=filas, valor=sum((f["valor"] for f in todos), Decimal("0")),
                    con_mov=sum(1 for f in todos if f["lotes"]),
                    bajos=[f for f in todos if f["bajo"] and f["existencia"] > 0],
                    sin=[f for f in todos if f["existencia"] <= 0], caducar=len(self.lotes_caducidad(dias=3)))

    def movimientos(self, id_producto: int, desde: date, hasta: date, tipo: str = "Todos") -> dict:
        p = self.producto(id_producto)
        movs = [dict(fecha=date.fromisoformat(m["fecha"]), tipo=m["tipo"], cantidad=_dec(m["cantidad"]),
                     referencia=m["referencia"], usuario=m["usuario"],
                     tono={"Entrada": "verde", "Merma": "naranja", "Devolución": "verde"}.get(m["tipo"], "gris"))
                for m in self._llamar(self.api.get, f"/inventario/productos/{id_producto}/movimientos")]
        saldo = p["existencia"]
        for m in movs:  # llegan de hoy hacia atrás: existencia después de cada movimiento
            m["existencia"] = saldo
            saldo -= m["cantidad"]
        visibles = [m for m in movs if desde <= m["fecha"] <= hasta and (tipo == "Todos" or m["tipo"] == tipo.rstrip("s"))]
        entradas = sum((m["cantidad"] for m in visibles if m["tipo"] == "Entrada"), Decimal("0"))
        ventas = -sum((m["cantidad"] for m in visibles if m["tipo"] == "Venta"), Decimal("0"))
        mermas = -sum((m["cantidad"] for m in visibles if m["tipo"] == "Merma"), Decimal("0"))
        return dict(producto=p, unidad=p["unidad_venta"], movimientos=visibles, entradas=entradas,
                    lotes_entrada=sum(1 for m in visibles if m["tipo"] == "Entrada"),
                    ventas=ventas, importe_ventas=(ventas * p["precio_venta"]).quantize(Decimal("0.01")),
                    mermas=mermas, costo_mermas=(mermas * p["costo"]).quantize(Decimal("0.01")),
                    pct_merma=(mermas / entradas * 100) if entradas else Decimal("0"),
                    existencia=p["existencia"], minimo=p["stock_minimo"], bajo=p["existencia"] < p["stock_minimo"])

    # ---------------------------------------------------------- precios (HU-31)
    def previsualizar_precios(self, aplicar: str, id_categoria, id_producto, tipo: str, valor: Decimal) -> list[dict]:
        """Solo cálculo sobre los precios y costos vigentes: no guarda nada."""
        activos = [p for p in self.lista_productos() if p["activo"]]
        if aplicar == "Una categoría":
            prods = [p for p in activos if p["id_categoria"] == id_categoria]
        elif aplicar == "Un producto":
            prods = [p for p in activos if p["id_producto"] == id_producto]
        else:
            prods = activos
        filas = []
        for p in prods:
            actual = p["precio_venta"]
            if tipo == "Porcentaje de aumento":
                nuevo = actual * (1 + valor / 100)
            elif tipo == "Porcentaje de descuento":
                nuevo = actual * (1 - valor / 100)
            else:
                nuevo = valor
            nuevo = nuevo.quantize(Decimal("0.01"))
            margen = ((nuevo - p["costo"]) / nuevo * 100) if nuevo else Decimal("0")
            filas.append(dict(id_producto=p["id_producto"], nombre=p["nombre"], unidad=p["unidad_venta"], costo=p["costo"],
                              actual=actual, nuevo=nuevo, margen=margen, perdida=nuevo < p["costo"]))
        return filas

    def aplicar_precios(self, filas: list[dict], motivo: str) -> None:
        self._llamar(self.api.post, "/inventario/precios", dict(
            motivo=motivo, cambios=[dict(id_producto=f["id_producto"], precio_nuevo=str(f["nuevo"])) for f in filas]))

    def historial(self, id_producto: int) -> dict:
        p = self.producto(id_producto)
        cambios = [dict(fecha=datetime.fromisoformat(c["fecha"]), anterior=_dec(c["anterior"]), nuevo=_dec(c["nuevo"]),
                        usuario=c["usuario"], motivo=c["motivo"] or "", costo=p["costo"])
                   for c in self._llamar(self.api.get, f"/inventario/productos/{id_producto}/precios")]
        # La base no guarda el costo de cada fecha: la gráfica usa el costo vigente.
        puntos = [(f"{c['fecha'].day:02d} {MESES[c['fecha'].month - 1][:3].lower()}", c["nuevo"], p["costo"])
                  for c in reversed(cambios)]
        puntos.append(("Hoy", p["precio_venta"], p["costo"]))
        return dict(producto=p, cambios=cambios, puntos=puntos)

    # ---------------------------------------------------------- mermas (HU-17)
    def lotes_de_producto(self, id_producto: int) -> list[dict]:
        filas = self._llamar(self.api.get, f"/inventario/productos/{id_producto}/lotes")
        return [dict(lote=l["folio"], queda=_dec(l["queda"]), caducidad=date.fromisoformat(l["caducidad"]),
                     costo=_dec(l["costo"])) for l in filas]

    def lista_mermas(self, motivo: str = "Todos") -> dict:
        filas = self._llamar(self.api.get, "/inventario/mermas", motivo=MOTIVO_DE_PANTALLA.get(motivo))
        salida = [dict(fecha=date.fromisoformat(m["fecha"]), id_producto=m["id_producto"], producto=m["producto"],
                       unidad=m["unidad_venta"], lote=m["lote"], cantidad=_dec(m["cantidad"]),
                       motivo=MOTIVOS_MERMA.get(m["motivo"], m["motivo"]), costo=_dec(m["costo"]),
                       usuario=m["usuario"], obs=m["observaciones"] or "") for m in filas]
        hoy = date.today()
        mes = [f for f in salida if (f["fecha"].year, f["fecha"].month) == (hoy.year, hoy.month)]
        return dict(filas=salida, mes=MESES[hoy.month - 1],
                    kilos_mes=sum((f["cantidad"] for f in mes if f["unidad"] == "kg"), Decimal("0")),
                    costo_mes=sum((f["costo"] for f in mes), Decimal("0")))

    def registrar_merma(self, id_producto: int, lote: str, cantidad: Decimal, motivo: str, obs: str) -> Decimal:
        r = self._llamar(self.api.post, "/inventario/mermas", dict(
            id_producto=id_producto, folio_lote=lote, cantidad=str(cantidad),
            motivo=MOTIVO_DE_PANTALLA.get(motivo, "otro"), observaciones=obs or None))
        return _dec(r["costo"])

    # ---------------------------------------------------------- cuentas por pagar (HU-25)
    def cuentas_por_pagar(self, id_proveedor=None, estatus="Pendientes y vencidas") -> dict:
        filas = []
        for c in self._llamar(self.api.get, "/compras/cuentas-por-pagar", id_proveedor=id_proveedor):
            total, saldo, vence = _dec(c["total"]), _dec(c["saldo"]), date.fromisoformat(c["vence"])
            est, tono = _estatus_cxp(saldo, vence)
            if estatus == "Pendientes y vencidas" and saldo <= 0 or estatus == "Vencidas" and not est.startswith("Vencida"):
                continue
            if estatus == "Pagadas" and saldo > 0:
                continue
            filas.append(dict(lote=c["lote"], proveedor=c["proveedor"], vence=vence, total=total, saldo=saldo,
                              estatus=est, tono=tono))
        abiertas = [f for f in filas if f["saldo"] > 0]
        vencidas = [f for f in abiertas if f["estatus"].startswith("Vencida")]
        proximas = [f for f in abiertas if f["estatus"].startswith("Vence")]
        return dict(filas=filas, total=sum((f["saldo"] for f in abiertas), Decimal("0")), lotes=len(abiertas),
                    proveedores=len({f["proveedor"] for f in abiertas}),
                    vencido=sum((f["saldo"] for f in vencidas), Decimal("0")), vencidas=vencidas,
                    proximo=sum((f["saldo"] for f in proximas), Decimal("0")), proximas=proximas)

    def pagar_lote(self, folio: str, monto: Decimal, metodo: str, referencia: str) -> Decimal:
        r = self._llamar(self.api.post, f"/compras/cuentas-por-pagar/{quote(folio)}/pagos",
                         dict(monto=str(monto), metodo=metodo, referencia=referencia or None))
        return _dec(r["saldo"])

    def estado_cuenta_proveedor(self, id_proveedor: int, desde: date, hasta: date) -> dict:
        prov = next(p for p in self.lista_proveedores("", "Todos") if p["id"] == id_proveedor)
        movs = [dict(fecha=date.fromisoformat(m["fecha"]), movimiento=m["movimiento"], referencia=m["referencia"],
                     cargo=_dec(m["cargo"]), abono=_dec(m["abono"]))
                for m in self._llamar(self.api.get, f"/compras/proveedores/{id_proveedor}/estado-de-cuenta")]
        inicial = sum((m["cargo"] - m["abono"] for m in movs if m["fecha"] < desde), Decimal("0"))
        periodo = [m for m in movs if desde <= m["fecha"] <= hasta]
        saldo = inicial
        for m in periodo:
            saldo += m["cargo"] - m["abono"]
            m["saldo"] = saldo
        vencido = sum((f["saldo"] for f in self.cuentas_por_pagar(id_proveedor)["vencidas"]), Decimal("0"))
        return dict(proveedor=prov, inicial=inicial, movimientos=periodo,
                    compras=sum((m["cargo"] for m in periodo), Decimal("0")),
                    pagos=sum((m["abono"] for m in periodo), Decimal("0")),
                    n_compras=sum(1 for m in periodo if m["cargo"]), n_pagos=sum(1 for m in periodo if m["abono"]),
                    saldo=saldo, vencido=vencido)

    # ---------------------------------------------------------- crédito (HU-39, HU-38a)
    def clientes_credito_pos(self) -> list[dict]:
        return [dict(id=c["id_cliente_credito"], nombre=c["nombre"], limite=_dec(c["limite_credito"]), debe=_dec(c["debe"]),
                     disponible=_dec(c["disponible"]), dias=c["dias_credito"], vence=date.fromisoformat(c["vence"]),
                     vencido=c["vencido"]) for c in self._llamar(self.api.get, "/pos/clientes-credito")]

    def lista_clientes_credito(self, busqueda: str = "", estatus: str = "Todos") -> list[dict]:
        filas = self._llamar(self.api.get, "/finanzas/clientes-credito", busqueda=busqueda or None,
                             estatus=FILTRO_CLIENTES.get(estatus, "todos"))
        salida = []
        for c in filas:
            limite, debe = _dec(c["limite_credito"]), _dec(c["debe"])
            base = "Activo" if c["activo"] else "Suspendido"
            vista = "Pago vencido" if c["activo"] and c["vencido"] else base
            if estatus not in ("Todos", vista):
                continue
            salida.append(dict(id=c["id_cliente_credito"], nombre=c["nombre"], telefono=c["telefono"], limite=limite,
                               dias=c["dias_credito"], estatus=base, fiscal=c["rfc_fiscal"], debe=debe,
                               uso=float(debe / limite) if limite else 0, estatus_vista=vista))
        return salida

    def guardar_cliente_credito(self, datos: dict) -> None:
        cuerpo = dict(nombre=datos["nombre"], telefono=datos["telefono"], limite_credito=str(datos["limite"]),
                      dias_credito=datos["dias"], rfc_fiscal=datos.get("fiscal") or None,
                      activo=datos.get("estatus", "Activo") != "Suspendido")
        if datos.get("id"):
            self._llamar(self.api.put, f"/finanzas/clientes-credito/{datos['id']}", cuerpo)
        else:
            self._llamar(self.api.post, "/finanzas/clientes-credito", cuerpo)

    # ---------------------------------------------------------- usuarios (HU-18)
    def _roles(self) -> dict[str, int]:
        return {r["nombre"]: r["id_rol"] for r in self._llamar(self.api.get, "/admin/roles")}

    def nombres_roles(self) -> list[str]:
        return list(self._roles())

    def lista_usuarios(self, busqueda: str = "", rol: str = "Todos") -> list[dict]:
        id_rol = self._roles().get(rol) if rol != "Todos" else None
        filas = self._llamar(self.api.get, "/admin/usuarios", busqueda=busqueda or None, id_rol=id_rol)
        return [dict(id=u["id_usuario"], nombre=u["nombre_completo"], usuario=u["usuario"], correo=u["correo"],
                     rol=u["rol"], activo=u["activo"],
                     ultimo=datetime.fromisoformat(u["ultimo_acceso"]) if u["ultimo_acceso"] else None) for u in filas]

    def guardar_usuario(self, datos: dict) -> None:
        id_rol = self._roles().get(datos["rol"])
        if id_rol is None:
            raise ErrorNegocio("Elija un rol activo.", "rol")
        cuerpo = dict(nombre_completo=datos["nombre"], usuario=datos["usuario"], correo=datos["correo"], id_rol=id_rol,
                      activo=datos.get("activo", True), password=datos.get("password") or None)
        if datos.get("id"):
            self._llamar(self.api.put, f"/admin/usuarios/{datos['id']}", cuerpo)
        else:
            self._llamar(self.api.post, "/admin/usuarios", cuerpo)

    # ---------------------------------------------------------- facturación (HU-32, HU-12a, HU-33)
    def timbres_disponibles(self) -> tuple[int, int]:
        t = self._llamar(self.api.get, "/facturacion/timbres")
        return t["disponibles"], t["contratados"]

    @staticmethod
    def _concepto_de(c: dict) -> dict:
        return dict(nombre=c["nombre"], unidad=c["unidad_venta"], cantidad=_dec(c["cantidad"]),
                    precio=_dec(c["precio_unitario"]), importe=_dec(c["importe"]), clave_sat=c["clave_sat"])

    def ticket_para_factura(self, folio: str) -> dict:
        t = self._llamar(self.api.get, f"/facturacion/tickets/{quote(folio)}")
        return dict(folio=t["folio"], total=_dec(t["total"]), metodo=t["metodo"],
                    renglones=[self._concepto_de(c) for c in t["conceptos"]])

    def lista_clientes_fiscales(self, busqueda: str = "") -> list[dict]:
        return [dict(id=c["id_cliente"], rfc=c["rfc"], razon_social=c["razon_social"], regimen=c["regimen_fiscal"],
                     cp=c["codigo_postal"], correo=c["correo"], facturas=c["facturas"])
                for c in self._llamar(self.api.get, "/facturacion/clientes", busqueda=busqueda or None)]

    def guardar_cliente_fiscal(self, datos: dict, original: str | None = None) -> None:
        cuerpo = dict(rfc=datos["rfc"], razon_social=datos["razon_social"], regimen_fiscal=datos["regimen"],
                      codigo_postal=datos["cp"], correo=datos["correo"])
        actual = next((c for c in self.lista_clientes_fiscales(original) if c["rfc"] == original), None) if original else None
        if actual:
            self._llamar(self.api.put, f"/facturacion/clientes/{actual['id']}", cuerpo)
        else:
            self._llamar(self.api.post, "/facturacion/clientes", cuerpo)

    def _factura_de(self, f: dict) -> dict:
        timbrado = datetime.fromisoformat(f["fecha_timbrado"]) if f["fecha_timbrado"] else None
        return dict(folio=f["folio"], fecha=timbrado.date() if timbrado else date.today(), timbrado=timbrado,
                    rfc=f["rfc"], uuid=f["uuid"] or "", total=_dec(f["total"]), estatus=f["estatus"],
                    ticket=f["folio_venta"], uso=f["uso_cfdi"], forma=f["forma_pago"], metodo_pago=f["metodo_pago"],
                    correo=f["correo"], cliente=dict(razon_social=f["razon_social"], rfc=f["rfc"], cp=f["codigo_postal"],
                                                     correo=f["correo"]),
                    renglones=[self._concepto_de(c) for c in f["conceptos"]])

    def timbrar(self, datos: dict) -> dict:
        cuerpo = dict(folio_venta=datos["ticket"], rfc=datos["rfc"], regimen_fiscal=datos["regimen"],
                      codigo_postal=datos["cp"], uso_cfdi=datos["uso"], forma_pago=datos["forma"],
                      metodo_pago=datos["metodo_pago"], correo=datos["correo"])
        return self._factura_de(self._llamar(self.api.post, "/facturacion/facturas", cuerpo))

    def detalle_factura(self, folio: str) -> dict:
        return self._factura_de(self._llamar(self.api.get, f"/facturacion/facturas/{quote(folio)}"))

    def lista_facturas(self, texto: str = "", desde=None, hasta=None, estatus: str = "Todas") -> list[dict]:
        filas = self._llamar(self.api.get, "/facturacion/facturas", texto=texto or None,
                             desde=desde.isoformat() if desde else None, hasta=hasta.isoformat() if hasta else None,
                             estatus=estatus.rstrip("s") if estatus != "Todas" else "Todas")
        return [dict(self._factura_de(f), cliente=f["razon_social"]) for f in filas]

    def cancelar_factura(self, folio: str, motivo: str, sustituto: str) -> None:
        self._llamar(self.api.post, f"/facturacion/facturas/{quote(folio)}/cancelacion",
                     dict(motivo=motivo[:2], folio_sustituto=sustituto.strip().upper() or None))

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
