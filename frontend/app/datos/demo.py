"""Datos de demostración en memoria, tomados del lienzo de diseño UX/UI.

Las reglas que aquí se simulan (FEFO, límite de crédito, cobros no mayores al saldo,
solo el Administrador autoriza devoluciones...) las hace en realidad la base de datos
y el middleware; este módulo solo permite recorrer las pantallas sin servidor.
Nada de lo capturado en modo demostración se guarda.
"""
from copy import deepcopy
from datetime import date, datetime, timedelta
from decimal import Decimal as D

from app.datos import ErrorNegocio
from app.validaciones import error_correo, error_rfc

PASSWORD_DEMO = "Frutis2026!"
# Fecha de referencia del lienzo de diseño (lunes 2 de noviembre de 2026).
HOY = date(2026, 11, 2)
AHORA = datetime(2026, 11, 2, 10, 12)

_PERMISOS_BASE = {  # mismo arreglo que database/seed.sql
    "Administrador": {m: (1, 1, 1, 1) for m in ("pos", "compras", "facturacion", "finanzas", "inventario", "reportes", "admin")},
    "Cajero": {"pos": (1, 1, 0, 0), "inventario": (1, 0, 0, 0)},
    "Compras": {"compras": (1, 1, 1, 1), "inventario": (1, 1, 1, 0), "reportes": (1, 0, 0, 0)},
    "Contador": {"facturacion": (1, 1, 1, 1), "finanzas": (1, 1, 1, 1), "reportes": (1, 0, 0, 0), "pos": (1, 0, 0, 0)},
}
_ESPECIALES_BASE = {
    "Cajero": {"credito": True, "devoluciones": False, "cortes": False},
    "Compras": {"credito": False, "devoluciones": False, "cortes": False},
    "Contador": {"credito": False, "devoluciones": False, "cortes": True},
    "Administrador": {"credito": True, "devoluciones": True, "cortes": True},
}


def _d(dd: int, mm: int, aa: int = 2026) -> date:
    return date(aa, mm, dd)


class DatosDemo:
    es_demo = True

    def __init__(self):
        self.sesion_usuario: dict | None = None
        self._cargar()

    # ================================================================ datos iniciales
    def _cargar(self) -> None:
        self.usuarios = [
            dict(id=1, nombre="Ana López", usuario="alopez", correo="ana.lopez@frutis.mx", rol="Administrador",
                 ultimo=datetime(2026, 11, 2, 10, 12), activo=True),
            dict(id=2, nombre="Mario Pérez", usuario="mperez", correo="mario.perez@frutis.mx", rol="Cajero",
                 ultimo=datetime(2026, 11, 2, 7, 58), activo=True),
            dict(id=3, nombre="Carmen Ruiz", usuario="cruiz", correo="carmen.ruiz@frutis.mx", rol="Contador",
                 ultimo=datetime(2026, 10, 30, 18, 40), activo=True),
            dict(id=4, nombre="Luis Gómez", usuario="lgomez", correo="luis.gomez@frutis.mx", rol="Compras",
                 ultimo=datetime(2026, 10, 31, 21, 4), activo=False),
        ]
        self.permisos = deepcopy(_PERMISOS_BASE)
        self.especiales = deepcopy(_ESPECIALES_BASE)

        self.categorias = [
            dict(id=1, nombre="Frutas", descripcion="Frutas frescas de temporada", activa=True),
            dict(id=2, nombre="Verduras", descripcion="Verduras y hortalizas", activa=True),
            dict(id=3, nombre="Hierbas y chiles", descripcion="Cilantro, perejil, chiles frescos", activa=True),
            dict(id=4, nombre="Abarrotes", descripcion="Frutos secos y semillas", activa=False),
        ]
        p = lambda i, cod, nom, cat, u, precio, costo, minimo, frec, diaria, clave: dict(  # noqa: E731
            id_producto=i, codigo_barras=cod, nombre=nom, id_categoria=cat, unidad_venta=u,
            precio_venta=D(precio), costo=D(costo), stock_minimo=D(minimo), es_frecuente=frec,
            venta_diaria=D(diaria), clave_sat=clave, activo=True,
        )
        self.productos = [
            p(1, "7501001", "Manzana Gala", 1, "kg", "42.00", "30.00", 20, True, 12, "50301700"),
            p(2, "7501002", "Plátano Tabasco", 1, "kg", "24.00", "16.00", 40, True, 25, "50301500"),
            p(3, "7501003", "Fresa", 1, "kg", "48.00", "30.00", 10, True, 8, "50301900"),
            p(4, "7501004", "Aguacate Hass", 1, "kg", "85.00", "62.00", 15, True, 6, "50301600"),
            p(5, "7501010", "Jitomate saladet", 2, "kg", "28.00", "14.00", 20, True, 9, "50401800"),
            p(6, "7501012", "Zanahoria", 2, "kg", "18.00", "10.00", 15, True, 5, "50401700"),
            p(7, "7501015", "Limón sin semilla", 1, "kg", "32.00", "14.00", 10, True, 4, "50302300"),
            p(8, "7501020", "Piña miel", 1, "pza", "35.00", "20.00", 10, True, 3, "50302000"),
            p(9, "7501021", "Mandarina", 1, "kg", "22.00", "24.00", 15, False, 0, "50302100"),
            p(10, "7501030", "Mango Ataulfo", 1, "kg", "38.00", "22.00", 15, False, 0, "50302200"),
        ]
        self.proveedores = [
            dict(id=1, razon_social="Hortalizas del Valle", rfc="HVA010203AB1", telefono="55 1234 5678",
                 correo="ventas@hvalle.mx", dias_credito=15, direccion="Central de Abasto, nave I", activo=True),
            dict(id=2, razon_social="Frutas Selectas SA", rfc="FSE990101XY2", telefono="55 8765 4321",
                 correo="pedidos@fselectas.mx", dias_credito=30, direccion="Central de Abasto, nave F", activo=True),
            dict(id=3, razon_social="Plátanos de Tabasco", rfc="PTA120415QW3", telefono="993 310 2244",
                 correo="ventas@ptabasco.mx", dias_credito=7, direccion="Villahermosa, Tabasco", activo=True),
            dict(id=4, razon_social="Distribuidora La Huerta", rfc="DLH080930RT5", telefono="55 2233 4455",
                 correo="", dias_credito=15, direccion="", activo=False),
        ]
        r = lambda prod, rec, costo, cad, vend=0, merma=0: dict(  # noqa: E731
            id_producto=prod, recibido=D(str(rec)), costo=D(costo), caducidad=cad, vendido=D(str(vend)), merma=D(str(merma)))
        self.lotes = [
            dict(folio="L-0229", id_proveedor=1, entrada=_d(3, 10), factura="A-4302", dias=15, renglones=[
                r(3, 30, "30.00", _d(3, 11), 24, 3.5), r(1, 100, "29.00", _d(20, 10), 100)]),
            dict(folio="L-0231", id_proveedor=1, entrada=_d(10, 10), factura="A-4355", dias=15, renglones=[
                r(1, 60, "30.00", _d(4, 11), 44.5), r(6, 100, "10.00", _d(15, 11), 66), r(7, 100, "14.00", _d(30, 10), 100)]),
            dict(folio="L-0232", id_proveedor=3, entrada=_d(17, 10), factura="T-2210", dias=0, renglones=[
                r(2, 120, "17.00", _d(26, 10), 120)]),
            dict(folio="L-0233", id_proveedor=2, entrada=_d(20, 10), factura="FS-88102", dias=15, renglones=[
                r(8, 30, "20.00", _d(5, 11), 22), r(1, 30, "30.00", _d(10, 11)), r(9, 25, "24.00", _d(29, 10), 25),
                r(6, 5, "10.00", _d(1, 11), 5)]),
            dict(folio="L-0234", id_proveedor=3, entrada=_d(24, 10), factura="T-2244", dias=0, renglones=[
                r(2, 120, "16.00", _d(3, 11), 98)]),
            dict(folio="L-0235", id_proveedor=1, entrada=_d(25, 10), factura="A-4411", dias=15, renglones=[
                r(5, 120, "14.00", _d(5, 11), 96, 12), r(4, 60, "62.00", _d(9, 11), 38.5, 2.5)]),
            dict(folio="L-0236", id_proveedor=2, entrada=_d(2, 11), factura="FS-88213", dias=30, renglones=[
                r(3, 40, "30.00", _d(6, 11)), r(10, 80, "22.00", _d(12, 11)), r(7, 50, "14.00", _d(20, 11))]),
            dict(folio="L-0237", id_proveedor=3, entrada=_d(1, 11), factura="T-2301", dias=0, renglones=[
                r(2, 100, "16.00", _d(9, 11), 2)]),
        ]
        # Pagos a proveedores (contado se paga al recibir).
        self.pagos_proveedor = [
            dict(lote="L-0229", fecha=_d(18, 10), monto=D("3800.00"), metodo="Transferencia", referencia="SPEI 1810-55120"),
            dict(lote="L-0232", fecha=_d(17, 10), monto=D("2040.00"), metodo="Efectivo", referencia="Contado"),
            dict(lote="L-0234", fecha=_d(24, 10), monto=D("1920.00"), metodo="Efectivo", referencia="Contado"),
            dict(lote="L-0237", fecha=_d(1, 11), monto=D("1600.00"), metodo="Efectivo", referencia="Contado"),
        ]
        self.mermas = [
            dict(fecha=_d(31, 10), id_producto=5, lote="L-0235", cantidad=D("8.0"), motivo="Maduración", usuario="alopez", obs=""),
            dict(fecha=_d(31, 10), id_producto=3, lote="L-0229", cantidad=D("2.5"), motivo="Maduración", usuario="alopez", obs=""),
            dict(fecha=_d(29, 10), id_producto=5, lote="L-0235", cantidad=D("4.0"), motivo="Golpe", usuario="mperez", obs=""),
            dict(fecha=_d(28, 10), id_producto=4, lote="L-0235", cantidad=D("2.5"), motivo="Maduración", usuario="alopez", obs=""),
            dict(fecha=_d(28, 10), id_producto=3, lote="L-0229", cantidad=D("1.0"), motivo="Devolución en mal estado", usuario="mperez", obs=""),
        ]
        # Ventas diarias agregadas (historial para movimientos de inventario).
        self.ventas_dia = [
            dict(fecha=f, id_producto=5, cantidad=D(c), tickets=t) for f, c, t in [
                (_d(26, 10), "22.0", 52), (_d(27, 10), "18.5", 44), (_d(28, 10), "16.0", 40), (_d(29, 10), "14.0", 35),
                (_d(30, 10), "12.5", 31), (_d(31, 10), "9.0", 26), (_d(1, 11), "4.0", 11)]
        ]
        self.metodos = [
            dict(id_metodo=1, nombre="Efectivo", clave_sat="01", es_efectivo=True, es_credito=False, activo=True),
            dict(id_metodo=2, nombre="Tarjeta de débito", clave_sat="28", es_efectivo=False, es_credito=False, activo=True),
            dict(id_metodo=3, nombre="Tarjeta de crédito", clave_sat="04", es_efectivo=False, es_credito=False, activo=True),
            dict(id_metodo=4, nombre="Transferencia", clave_sat="03", es_efectivo=False, es_credito=False, activo=True),
            dict(id_metodo=5, nombre="Crédito de la tienda", clave_sat="99", es_efectivo=False, es_credito=True, activo=True),
        ]
        self.cajas = [
            dict(id_caja=1, nombre="Caja 1 · Mostrador", corto="Caja 1", terminal="POS-1", ip="192.168.1.12"),
            dict(id_caja=2, nombre="Caja 2 · Entrada", corto="Caja 2", terminal="POS-2", ip="192.168.1.13"),
        ]
        # Turno abierto de la Caja 1 (con los totales del lienzo como base).
        self.turno = dict(
            id_caja=1, cajero="Mario Pérez", usuario="mperez", fondo=D("1000.00"),
            desde=datetime(2026, 11, 2, 7, 58),
            base={"efectivo": (78, D("9860.50")), "tarjeta": (31, D("6240.00")), "transferencia": (15, D("2320.00")),
                  "credito": (2, D("350.00")), "devoluciones": (1, D("186.00"))},
        )
        self.ultimo_corte = dict(
            fecha=datetime(2026, 10, 31, 21, 4), cajero="Luis Gómez", esperado=D("10674.50"),
            contado=D("10650.00"), observaciones="Faltante por cambio mal entregado",
        )
        self.siguiente_folio = 1044
        self.ultimo_ticket: dict | None = None
        t = lambda folio, fecha, metodo, renglones, cliente=None, facturado=False: dict(  # noqa: E731
            folio=folio, fecha=fecha, metodo=metodo, cliente=cliente, facturado=facturado,
            renglones=[dict(id_producto=i, cantidad=D(c), precio=D(pr)) for i, c, pr in renglones], devuelto={})
        self.tickets = {
            "V00001031": t("V00001031", datetime(2026, 10, 31, 9, 12), "Efectivo",
                           [(3, "1.000", "48.00"), (2, "2.000", "24.00"), (8, "2", "35.00")]),
            "V00001042": t("V00001042", datetime(2026, 10, 31, 12, 40), "Efectivo",
                           [(1, "1.250", "42.00"), (2, "2.000", "24.00")]),
            "V00001043": t("V00001043", datetime(2026, 11, 2, 10, 31), "Crédito",
                           [(1, "1.250", "42.00"), (2, "2.000", "24.00"), (4, "0.800", "85.00")], cliente=3),
        }
        self.clientes_credito = [
            dict(id=1, nombre="Cocina Económica Rosy", telefono="55 3388 1200", limite=D("3000.00"), dias=15, estatus="Activo", fiscal=None),
            dict(id=2, nombre="Restaurante El Huerto", telefono="55 4021 8890", limite=D("1500.00"), dias=7, estatus="Activo", fiscal=None),
            dict(id=3, nombre="Fonda Doña Lupe", telefono="55 6610 4471", limite=D("1000.00"), dias=15, estatus="Activo", fiscal="LUGO750312HM4"),
            dict(id=4, nombre="Hotel Plaza Centro", telefono="55 1902 3344", limite=D("5000.00"), dias=30, estatus="Suspendido", fiscal=None),
        ]
        self.cxc = [
            dict(ticket="V00000902", id_cliente=1, venta=_d(8, 10), dias=15, total=D("1200.00")),
            dict(ticket="V00000988", id_cliente=2, venta=_d(20, 10), dias=7, total=D("780.00")),
            dict(ticket="V00001010", id_cliente=1, venta=_d(25, 10), dias=15, total=D("2600.00")),
            dict(ticket="V00001037", id_cliente=3, venta=_d(1, 11), dias=15, total=D("350.00")),
        ]
        self.cobros = [
            dict(ticket="V00000902", fecha=_d(22, 10), monto=D("1200.00"), metodo="Efectivo", caja="Caja 1"),
            dict(ticket="V00001010", fecha=_d(30, 10), monto=D("600.00"), metodo="Transferencia", caja=None),
        ]
        self.clientes_fiscales = [
            dict(rfc="RSO100518KJ3", razon_social="Restaurante El Sol", regimen="601", cp="06600", correo="pagos@elsol.mx"),
            dict(rfc="RAJU800101AB2", razon_social="Juan Ramos", regimen="612", cp="03100", correo="juan.ramos@correo.mx"),
            dict(rfc="LUGO750312HM4", razon_social="Fonda Doña Lupe", regimen="626", cp="06700", correo="donalupe@correo.mx"),
        ]
        self.facturas = [
            dict(folio="F-0012", fecha=_d(24, 10), rfc="RSO100518KJ3", uuid="3C77D0A1-9B21-4C55-8E10-2F7A61D04E2B",
                 total=D("2350.00"), estatus="Vigente", ticket="V00000990", uso="G03", forma="01", metodo_pago="PUE"),
            dict(folio="F-0011", fecha=_d(22, 10), rfc="RAJU800101AB2", uuid="5B22E9F0-1D4A-4F87-A3C2-6E0B88C391AA",
                 total=D("540.00"), estatus="Cancelada", ticket="V00000975", uso="G03", forma="01", metodo_pago="PUE"),
            dict(folio="F-0010", fecha=_d(15, 10), rfc="LUGO750312HM4", uuid="1D09A4B7-66E2-4B90-9F41-0C7D2A51C3E0",
                 total=D("1180.00"), estatus="Vigente", ticket="V00000940", uso="G03", forma="99", metodo_pago="PPD"),
        ]
        self.timbres = (963, 1000)
        self.gastos = [
            dict(fecha=_d(31, 10), concepto="Sueldos", detalle="Segunda quincena (4 personas)", metodo="Transferencia", monto=D("19000.00"), comprobante=True, usuario="alopez"),
            dict(fecha=_d(22, 10), concepto="Mantenimiento", detalle="Calibración de báscula", metodo="Efectivo", monto=D("2400.00"), comprobante=True, usuario="alopez"),
            dict(fecha=_d(20, 10), concepto="Luz", detalle="Bimestre sep-oct", metodo="Transferencia", monto=D("3200.00"), comprobante=True, usuario="alopez"),
            dict(fecha=_d(15, 10), concepto="Sueldos", detalle="Primera quincena (4 personas)", metodo="Transferencia", monto=D("19000.00"), comprobante=True, usuario="alopez"),
            dict(fecha=_d(12, 10), concepto="Agua", detalle="Octubre", metodo="Efectivo", monto=D("450.00"), comprobante=False, usuario="alopez"),
            dict(fecha=_d(8, 10), concepto="Gas", detalle="Tanque estacionario", metodo="Efectivo", monto=D("1100.00"), comprobante=True, usuario="alopez"),
            dict(fecha=_d(1, 10), concepto="Renta", detalle="Local octubre", metodo="Transferencia", monto=D("12000.00"), comprobante=True, usuario="alopez"),
        ]
        self.historial_precios = {
            3: [
                dict(fecha=datetime(2026, 10, 25, 9, 31), anterior=D("45.00"), nuevo=D("48.00"), costo=D("30.00"), motivo="Ajuste individual", usuario="alopez"),
                dict(fecha=datetime(2026, 10, 1, 8, 10), anterior=D("42.00"), nuevo=D("45.00"), costo=D("28.00"), motivo="Frutas +7 %", usuario="alopez"),
                dict(fecha=datetime(2026, 9, 15, 8, 2), anterior=D("48.00"), nuevo=D("42.00"), costo=D("26.00"), motivo="Temporada alta", usuario="alopez"),
                dict(fecha=datetime(2026, 8, 1, 8, 0), anterior=D("52.00"), nuevo=D("48.00"), costo=D("34.00"), motivo="Ajuste individual", usuario="alopez"),
            ],
        }
        self.dispositivos = {
            1: dict(bascula_modelo="[MODELO POR CONFIRMAR]", puerto="COM3 · 9600 baudios",
                    impresora_modelo="[MODELO POR CONFIRMAR]", papel="80 mm", lector="Teclado (USB)"),
        }
        self.peso_simulado = D("0.800")
        self.auditoria = [
            dict(fecha=datetime(2026, 11, 2, 11, 5), usuario="alopez", modulo="Facturación", accion="Timbrado", tono="gris",
                 detalle="Factura F-0013 · ticket V00001042 · $100.50", ip="192.168.1.10"),
            dict(fecha=datetime(2026, 11, 2, 10, 47), usuario="alopez", modulo="Punto de Venta", accion="Devolución autorizada", tono="naranja",
                 detalle="Ticket V00001031 · Fresa 0.500 kg · $24.00 · va a merma", ip="192.168.1.12"),
            dict(fecha=datetime(2026, 11, 2, 10, 31), usuario="mperez", modulo="Punto de Venta", accion="Venta a crédito", tono="gris",
                 detalle="Ticket V00001043 · Fonda Doña Lupe · $168.50", ip="192.168.1.12"),
            dict(fecha=datetime(2026, 11, 2, 9, 20), usuario="alopez", modulo="Proveedores", accion="Lote registrado", tono="gris",
                 detalle="L-0236 · Frutas Selectas SA · $3,660.00", ip="192.168.1.10"),
            dict(fecha=datetime(2026, 11, 2, 7, 58), usuario="mperez", modulo="Punto de Venta", accion="Apertura de caja", tono="naranja",
                 detalle="Caja 1 · fondo $1,000.00", ip="192.168.1.12"),
            dict(fecha=datetime(2026, 11, 2, 7, 55), usuario="mperez", modulo="Acceso", accion="Inicio de sesión", tono="verde",
                 detalle="Terminal POS-1", ip="192.168.1.12"),
            dict(fecha=datetime(2026, 11, 1, 19, 12), usuario="desconocido", modulo="Acceso", accion="Intento fallido", tono="rojo",
                 detalle='Usuario "admin" · 3 intentos', ip="192.168.1.23"),
            dict(fecha=datetime(2026, 10, 31, 21, 30), usuario="alopez", modulo="Administración", accion="Usuario desactivado", tono="rojo",
                 detalle="lgomez · rol Compras", ip="192.168.1.10"),
            dict(fecha=datetime(2026, 10, 31, 21, 4), usuario="lgomez", modulo="Punto de Venta", accion="Corte de caja", tono="naranja",
                 detalle="Caja 1 · diferencia −$24.50", ip="192.168.1.12"),
            dict(fecha=datetime(2026, 10, 31, 17, 45), usuario="alopez", modulo="Catálogo", accion="Merma registrada", tono="gris",
                 detalle="Jitomate saladet 8.0 kg · L-0235 · $112.00", ip="192.168.1.10"),
        ]

    # ================================================================ utilidades internas
    def _ahora(self) -> datetime:
        return datetime.combine(HOY, datetime.now().time()).replace(microsecond=0)

    def _auditar(self, modulo: str, accion: str, detalle: str, tono: str = "gris") -> None:
        usuario = self.sesion_usuario["usuario"] if self.sesion_usuario else "desconocido"
        self.auditoria.insert(0, dict(fecha=self._ahora(), usuario=usuario, modulo=modulo, accion=accion,
                                      tono=tono, detalle=detalle, ip="127.0.0.1"))

    def producto(self, id_producto: int) -> dict:
        return next(p for p in self.productos if p["id_producto"] == id_producto)

    def _proveedor(self, id_proveedor: int) -> dict:
        return next(p for p in self.proveedores if p["id"] == id_proveedor)

    def _categoria(self, id_categoria: int) -> dict:
        return next(c for c in self.categorias if c["id"] == id_categoria)

    def _cliente(self, id_cliente: int) -> dict:
        return next(c for c in self.clientes_credito if c["id"] == id_cliente)

    @staticmethod
    def _queda(r: dict) -> D:
        return r["recibido"] - r["vendido"] - r["merma"]

    def existencia(self, id_producto: int) -> D:
        """La existencia se calcula por lotes (HU-24)."""
        return sum((self._queda(r) for lote in self.lotes for r in lote["renglones"]
                    if r["id_producto"] == id_producto), D("0"))

    def _lotes_con_existencia(self, id_producto: int) -> list[tuple[dict, dict]]:
        pares = [(l, r) for l in self.lotes for r in l["renglones"]
                 if r["id_producto"] == id_producto and self._queda(r) > 0]
        return sorted(pares, key=lambda par: par[1]["caducidad"])  # FEFO

    def _usuario_actual(self) -> str:
        return self.sesion_usuario["usuario"] if self.sesion_usuario else "demo"

    # ================================================================ sesión
    def login(self, usuario: str, password: str) -> dict:
        u = next((x for x in self.usuarios if x["usuario"] == usuario), None)
        if u is None or not u["activo"] or password != PASSWORD_DEMO:
            self.auditoria.insert(0, dict(fecha=self._ahora(), usuario=usuario or "desconocido", modulo="Acceso",
                                          accion="Intento fallido", tono="rojo", detalle="Credenciales incorrectas", ip="127.0.0.1"))
            raise ErrorNegocio("Ingrese un usuario/contraseña correcta.")
        self.sesion_usuario = u
        u["ultimo"] = self._ahora()
        self._auditar("Acceso", "Inicio de sesión", "Terminal POS-1 (demostración)", "verde")
        return self._perfil(u)

    def _perfil(self, u: dict) -> dict:
        permisos = [
            dict(modulo=m, puede_ver=bool(v[0]), puede_crear=bool(v[1]), puede_editar=bool(v[2]), puede_eliminar=bool(v[3]))
            for m, v in self.permisos.get(u["rol"], {}).items()
        ]
        return dict(id_usuario=u["id"], usuario=u["usuario"], nombre_completo=u["nombre"], rol=u["rol"], permisos=permisos)

    def logout(self) -> None:
        if self.sesion_usuario:
            self._auditar("Acceso", "Cierre de sesión", "Terminal POS-1 (demostración)")
        self.sesion_usuario = None

    def estado_conexion(self) -> str:
        return "Modo demostración · sin servidor"

    def caja_de_sesion(self) -> str | None:
        if self.turno and self.sesion_usuario and self.turno["usuario"] == self.sesion_usuario["usuario"]:
            return self.cajas[self.turno["id_caja"] - 1]["corto"]
        return "Caja 1" if self.sesion_usuario and self.sesion_usuario["rol"] == "Administrador" else None

    # ================================================================ inicio
    def resumen_inicio(self) -> dict:
        corte = self.resumen_corte() if self.turno else None
        ventas = sum((f["importe"] for f in corte["filas"] if f["concepto"].startswith("Ventas")), D("0")) if corte else D("0")
        tickets = corte["tickets"] if corte else 0
        por_caducar = [x for x in self.lotes_caducidad(dias=3)]
        nombres = sorted({x["producto"] for x in por_caducar})
        cxc = self.cuentas_por_cobrar()
        alertas = []
        for x in por_caducar[:1]:
            alertas.append(("Caducidad", f"{x['producto']}, lote {x['lote']}: {x['queda_txt']} caducan "
                            f"{'mañana' if x['dias'] == 1 else 'en ' + str(x['dias']) + ' días'}.", "naranja"))
        for c in self.cuentas_por_pagar()["filas"]:
            if c["estatus"] in ("Pendiente",) or c["estatus"].startswith("Vence"):
                alertas.append(("Por pagar", f"{c['proveedor']}, lote {c['lote']}: ${c['saldo']:,.2f} vence el "
                                f"{c['vence'].day} {['ene','feb','mar','abr','may','jun','jul','ago','sep','oct','nov','dic'][c['vence'].month-1]}.", "naranja"))
                break
        for p in self.existencias()["filas"]:
            if D("0") < p["existencia"] < p["minimo"]:
                alertas.append(("", f"Stock bajo: {p['nombre']} tiene {p['existencia']:.1f} {p['unidad']} "
                                f"(mínimo {p['minimo']:.0f} {p['unidad']}).", "rojo"))
                break
        for c in cxc["filas"]:
            if c["estatus"].startswith("Vencida"):
                alertas.append(("", f"Cobro vencido: {c['cliente']} debe ${c['saldo']:,.2f} desde el "
                                f"{c['vence'].day} {['ene','feb','mar','abr','may','jun','jul','ago','sep','oct','nov','dic'][c['vence'].month-1]}.", "rojo"))
                break
        clientes_deben = {c["cliente"] for c in cxc["filas"]}
        vencidos = sum(1 for c in cxc["filas"] if c["estatus"].startswith("Vencida"))
        return dict(
            ventas_hoy=ventas, tickets=tickets, ticket_promedio=(ventas / tickets if tickets else D("0")),
            caja=dict(abierta=bool(self.turno),
                      detalle=(f"{self.cajas[self.turno['id_caja'] - 1]['corto']} · desde las "
                               f"{self.turno['desde'].hour}:{self.turno['desde'].minute:02d} · {self.turno['cajero']}")
                      if self.turno else "Ninguna caja abierta"),
            caducar=len(por_caducar),
            caducar_detalle=(", ".join(nombres[:2]) + (f" y {len(nombres) - 2} productos más" if len(nombres) > 2 else "")) or "Sin lotes por caducar",
            por_cobrar=cxc["total"], por_cobrar_detalle=f"{len(clientes_deben)} clientes · {vencidos} vencido",
            alertas=alertas,
        )

    # ================================================================ punto de venta
    def cajas_disponibles(self) -> list[dict]:
        return deepcopy(self.cajas)

    def caja_actual(self) -> dict | None:
        if not self.turno:
            return None
        caja = self.cajas[self.turno["id_caja"] - 1]
        return dict(id_caja=caja["id_caja"], nombre=caja["corto"], terminal=caja["terminal"],
                    fondo_inicial=self.turno["fondo"], fecha_apertura=self.turno["desde"], cajero=self.turno["cajero"])

    def datos_ultimo_corte(self, id_caja: int) -> dict:
        return dict(self.ultimo_corte)

    def abrir_caja(self, id_caja: int, fondo: D) -> dict:
        if self.turno:
            raise ErrorNegocio("Ya hay una caja abierta en esta terminal.")
        if fondo < 0:
            raise ErrorNegocio("Ingrese un fondo inicial válido.")
        u = self.sesion_usuario
        self.turno = dict(id_caja=id_caja, cajero=u["nombre"], usuario=u["usuario"], fondo=fondo, desde=self._ahora(),
                          base={k: (0, D("0")) for k in ("efectivo", "tarjeta", "transferencia", "credito", "devoluciones")})
        self._auditar("Punto de Venta", "Apertura de caja", f"{self.cajas[id_caja - 1]['corto']} · fondo ${fondo:,.2f}", "naranja")
        return self.caja_actual()

    def productos_pos(self, busqueda: str | None = None, codigo: str | None = None, frecuentes: bool = False) -> list[dict]:
        salida = []
        for p in self.productos:
            if not p["activo"]:
                continue
            if codigo and p["codigo_barras"] != codigo:
                continue
            if frecuentes and not p["es_frecuente"]:
                continue
            if busqueda and busqueda.lower() not in p["nombre"].lower() and busqueda not in p["codigo_barras"]:
                continue
            salida.append(dict(id_producto=p["id_producto"], codigo_barras=p["codigo_barras"], nombre=p["nombre"],
                               unidad_venta=p["unidad_venta"], precio_venta=p["precio_venta"],
                               existencia=self.existencia(p["id_producto"]), es_frecuente=p["es_frecuente"]))
        return salida

    def metodos_pago(self) -> list[dict]:
        return [dict(m) for m in self.metodos if m["activo"]]

    def leer_bascula(self) -> D:
        return self.peso_simulado

    def clientes_credito_pos(self) -> list[dict]:
        salida = []
        for c in self.clientes_credito:
            if c["estatus"] == "Suspendido":
                continue
            debe = self._debe(c["id"])
            salida.append(dict(id=c["id"], nombre=c["nombre"], limite=c["limite"], debe=debe,
                               disponible=c["limite"] - debe, dias=c["dias"],
                               vence=HOY + timedelta(days=c["dias"]), vencido=self._tiene_vencido(c["id"])))
        return salida

    def registrar_venta(self, id_caja: int, id_metodo: int, monto_recibido: D, id_cliente: int | None,
                        carrito: list[dict]) -> dict:
        """Simula sp_registrar_venta: todo o nada."""
        if not self.turno:
            raise ErrorNegocio("No hay una caja abierta.")
        metodo = next(m for m in self.metodos if m["id_metodo"] == id_metodo)
        total = D("0")
        for r in carrito:
            p = self.producto(r["id_producto"])
            if self.existencia(p["id_producto"]) < r["cantidad"]:
                raise ErrorNegocio(f"Producto sin existencia suficiente: {p['nombre']}.")
            total += (p["precio_venta"] * r["cantidad"]).quantize(D("0.01"))
        if metodo["es_efectivo"] and monto_recibido < total:
            raise ErrorNegocio("El monto recibido es insuficiente.")
        if metodo["es_credito"]:
            if not id_cliente:
                raise ErrorNegocio("Elija el cliente de crédito.")
            c = next(x for x in self.clientes_credito_pos() if x["id"] == id_cliente)
            if total > c["disponible"]:
                raise ErrorNegocio(f"La venta excede el crédito disponible del cliente ({c['disponible']:,.2f}).")
        # Descuento FEFO por lote.
        for r in carrito:
            pendiente = r["cantidad"]
            for _, renglon in self._lotes_con_existencia(r["id_producto"]):
                toma = min(pendiente, self._queda(renglon))
                renglon["vendido"] += toma
                pendiente -= toma
                if pendiente <= 0:
                    break
        folio = f"V{self.siguiente_folio:08d}"
        self.siguiente_folio += 1
        clave = "efectivo" if metodo["es_efectivo"] else "credito" if metodo["es_credito"] else (
            "transferencia" if metodo["nombre"] == "Transferencia" else "tarjeta")
        n, imp = self.turno["base"][clave]
        self.turno["base"][clave] = (n + 1, imp + total)
        ticket = dict(folio=folio, fecha=self._ahora(), metodo=metodo["nombre"], cliente=id_cliente, facturado=False,
                      renglones=[dict(id_producto=r["id_producto"], cantidad=r["cantidad"],
                                      precio=self.producto(r["id_producto"])["precio_venta"]) for r in carrito],
                      devuelto={})
        self.tickets[folio] = ticket
        if metodo["es_credito"]:
            dias = self._cliente(id_cliente)["dias"]
            self.cxc.append(dict(ticket=folio, id_cliente=id_cliente, venta=HOY, dias=dias, total=total))
            self._auditar("Punto de Venta", "Venta a crédito", f"Ticket {folio} · {self._cliente(id_cliente)['nombre']} · ${total:,.2f}")
        else:
            self._auditar("Punto de Venta", "Venta", f"Ticket {folio} · {metodo['nombre']} · ${total:,.2f}")
        cambio = (monto_recibido - total) if metodo["es_efectivo"] else D("0")
        self.ultimo_ticket = dict(folio=folio, total=total, cambio=cambio, metodo=metodo["nombre"],
                                  recibido=monto_recibido, fecha=ticket["fecha"], renglones=self._renglones_ticket(ticket))
        return dict(folio=folio, total=total, cambio=cambio)

    def _renglones_ticket(self, ticket: dict) -> list[dict]:
        salida = []
        for r in ticket["renglones"]:
            p = self.producto(r["id_producto"])
            salida.append(dict(id_producto=p["id_producto"], nombre=p["nombre"], unidad=p["unidad_venta"],
                               cantidad=r["cantidad"], precio=r["precio"], clave_sat=p["clave_sat"],
                               importe=(r["precio"] * r["cantidad"]).quantize(D("0.01")),
                               devuelto=ticket["devuelto"].get(p["id_producto"], D("0"))))
        return salida

    def ticket_ultimo(self) -> dict | None:
        return self.ultimo_ticket

    def resumen_corte(self) -> dict:
        b = self.turno["base"]
        filas = [
            dict(concepto="Fondo inicial", tickets=None, importe=self.turno["fondo"]),
            dict(concepto="Ventas en efectivo", tickets=b["efectivo"][0], importe=b["efectivo"][1]),
            dict(concepto="Ventas con tarjeta", tickets=b["tarjeta"][0], importe=b["tarjeta"][1]),
            dict(concepto="Ventas por transferencia", tickets=b["transferencia"][0], importe=b["transferencia"][1]),
            dict(concepto="Ventas a crédito", tickets=b["credito"][0], importe=b["credito"][1]),
            dict(concepto="Devoluciones en efectivo", tickets=b["devoluciones"][0], importe=-b["devoluciones"][1]),
        ]
        esperado = self.turno["fondo"] + b["efectivo"][1] - b["devoluciones"][1]
        tickets = sum(b[k][0] for k in ("efectivo", "tarjeta", "transferencia", "credito"))
        return dict(filas=filas, esperado=esperado, desde=self.turno["desde"], tickets=tickets,
                    caja=self.cajas[self.turno["id_caja"] - 1]["corto"])

    def cerrar_caja(self, contado: D, observaciones: str) -> dict:
        resumen = self.resumen_corte()
        diferencia = contado - resumen["esperado"]
        if diferencia != 0 and not observaciones.strip():
            raise ErrorNegocio("Escriba las observaciones: hay diferencia en el arqueo.", campo="observaciones")
        self.ultimo_corte = dict(fecha=self._ahora(), cajero=self.turno["cajero"], esperado=resumen["esperado"],
                                 contado=contado, observaciones=observaciones or "Sin observaciones")
        self._auditar("Punto de Venta", "Corte de caja", f"{resumen['caja']} · diferencia ${diferencia:,.2f}", "naranja")
        self.turno = None
        return dict(resumen=resumen, contado=contado, diferencia=diferencia)

    def buscar_ticket(self, folio: str) -> dict:
        t = self.tickets.get(folio.strip().upper())
        if t is None:
            raise ErrorNegocio("No existe un ticket con ese número.")
        renglones = self._renglones_ticket(t)
        return dict(folio=t["folio"], fecha=t["fecha"], metodo=t["metodo"], facturado=t["facturado"],
                    total=sum((r["importe"] for r in renglones), D("0")), renglones=renglones,
                    cliente=self._cliente(t["cliente"])["nombre"] if t["cliente"] else None)

    def administradores(self) -> list[str]:
        return [u["nombre"] for u in self.usuarios if u["rol"] == "Administrador" and u["activo"]]

    def autorizar(self, nombre_admin: str, password: str, folio: str | None = None) -> str:
        """Solo un Administrador activo autoriza (SC-02, trigger en la base)."""
        u = next((x for x in self.usuarios if x["nombre"] == nombre_admin), None)
        if u is None or u["rol"] != "Administrador" or not u["activo"] or password != PASSWORD_DEMO:
            raise ErrorNegocio("Contraseña del Administrador incorrecta.")
        return f"Autorizado por {u['nombre']} a las {self._ahora():%H:%M}."

    def procesar_devolucion(self, folio: str, renglones: list[dict], motivo: str, reembolso: str, admin: str) -> dict:
        t = self.tickets[folio]
        total = D("0")
        detalle = []
        for r in renglones:
            prod = self.producto(r["id_producto"])
            vendido = next(x for x in t["renglones"] if x["id_producto"] == r["id_producto"])
            ya = t["devuelto"].get(r["id_producto"], D("0"))
            if r["cantidad"] <= 0 or r["cantidad"] + ya > vendido["cantidad"]:
                raise ErrorNegocio(f"La cantidad a devolver de {prod['nombre']} no es válida.")
            t["devuelto"][r["id_producto"]] = ya + r["cantidad"]
            importe = (vendido["precio"] * r["cantidad"]).quantize(D("0.01"))
            total += importe
            pares = self._lotes_con_existencia(r["id_producto"]) or [
                (l, x) for l in self.lotes for x in l["renglones"] if x["id_producto"] == r["id_producto"]]
            lote, renglon = pares[0]
            if r["buen_estado"]:
                renglon["vendido"] -= r["cantidad"]
            else:
                self.mermas.insert(0, dict(fecha=HOY, id_producto=r["id_producto"], lote=lote["folio"], cantidad=r["cantidad"],
                                           motivo="Devolución en mal estado", usuario=self._usuario_actual(), obs=motivo))
            detalle.append(f"{prod['nombre']} {r['cantidad']}")
        if reembolso.startswith("Efectivo") and self.turno:
            n, imp = self.turno["base"]["devoluciones"]
            self.turno["base"]["devoluciones"] = (n + 1, imp + total)
        self._auditar("Punto de Venta", "Devolución autorizada", f"Ticket {folio} · {', '.join(detalle)} · ${total:,.2f} · {admin}", "naranja")
        return dict(total=total)

    # ================================================================ proveedores y compras
    def _pagado_lote(self, folio: str) -> D:
        return sum((p["monto"] for p in self.pagos_proveedor if p["lote"] == folio), D("0"))

    def _total_lote(self, lote: dict) -> D:
        return sum(((r["recibido"] * r["costo"]).quantize(D("0.01")) for r in lote["renglones"]), D("0"))

    def _estatus_cxp(self, lote: dict) -> tuple[str, str]:
        saldo = self._total_lote(lote) - self._pagado_lote(lote["folio"])
        if saldo <= 0:
            return "Pagado", "verde"
        vence = lote["entrada"] + timedelta(days=lote["dias"])
        dias = (vence - HOY).days
        if dias < 0:
            return f"Vencida · {-dias} días", "rojo"
        if dias <= 3:
            return f"Vence en {dias} días" if dias != 1 else "Vence mañana", "naranja"
        return "Pendiente", "gris"

    def saldo_proveedor(self, id_proveedor: int) -> D:
        return sum((self._total_lote(l) - self._pagado_lote(l["folio"]) for l in self.lotes
                    if l["id_proveedor"] == id_proveedor), D("0"))

    def lista_proveedores(self, busqueda: str = "", estatus: str = "Activos") -> list[dict]:
        salida = []
        for p in self.proveedores:
            if estatus == "Activos" and not p["activo"] or estatus == "Inactivos" and p["activo"]:
                continue
            if busqueda and busqueda.lower() not in p["razon_social"].lower() and busqueda.upper() not in p["rfc"]:
                continue
            salida.append(dict(p, saldo=self.saldo_proveedor(p["id"])))
        return salida

    def proveedores_activos(self) -> list[dict]:
        return [p for p in self.proveedores if p["activo"]]

    def guardar_proveedor(self, datos: dict) -> None:
        if error := error_rfc(datos["rfc"], solo_moral=False):
            raise ErrorNegocio(error, "rfc")
        if any(p["rfc"] == datos["rfc"] and p["id"] != datos.get("id") for p in self.proveedores):
            raise ErrorNegocio("Ya existe un proveedor con ese RFC.", "rfc")
        if datos.get("correo") and (error := error_correo(datos["correo"])):
            raise ErrorNegocio(error, "correo")
        if datos.get("id"):
            p = self._proveedor(datos["id"])
            if not datos.get("activo", True) and self.saldo_proveedor(p["id"]) > 0:
                raise ErrorNegocio("No se puede dar de baja: tiene saldo por pagar.", "estatus")
            p.update(datos)
            self._auditar("Proveedores", "Proveedor editado", f"{p['razon_social']} · {p['rfc']}")
        else:
            datos = dict(datos, id=max(p["id"] for p in self.proveedores) + 1, activo=True)
            self.proveedores.append(datos)
            self._auditar("Proveedores", "Proveedor registrado", f"{datos['razon_social']} · {datos['rfc']}")

    def siguiente_folio_lote(self) -> str:
        return f"L-{max(int(l['folio'][2:]) for l in self.lotes) + 1:04d}"

    def registrar_lote(self, datos: dict) -> str:
        folio = self.siguiente_folio_lote()
        lote = dict(folio=folio, id_proveedor=datos["id_proveedor"], entrada=datos["entrada"], factura=datos["factura"],
                    dias=datos["dias"], renglones=[dict(id_producto=r["id_producto"], recibido=r["cantidad"], costo=r["costo"],
                                                        caducidad=r["caducidad"], vendido=D("0"), merma=D("0"))
                                                   for r in datos["renglones"]])
        self.lotes.append(lote)
        for r in datos["renglones"]:
            self.producto(r["id_producto"])["costo"] = r["costo"]
        total = self._total_lote(lote)
        if datos["dias"] == 0:
            self.pagos_proveedor.append(dict(lote=folio, fecha=datos["entrada"], monto=total, metodo="Efectivo", referencia="Contado"))
        self._auditar("Proveedores", "Lote registrado", f"{folio} · {self._proveedor(datos['id_proveedor'])['razon_social']} · ${total:,.2f}")
        return folio

    def lista_lotes(self, id_proveedor=None, desde=None, hasta=None, pago="Todos") -> dict:
        filas = []
        for l in sorted(self.lotes, key=lambda x: x["folio"], reverse=True):
            if id_proveedor and l["id_proveedor"] != id_proveedor:
                continue
            if desde and l["entrada"] < desde or hasta and l["entrada"] > hasta:
                continue
            est, tono = self._estatus_cxp(l)
            est_pago = "Pagado" if est == "Pagado" else "Vencido" if est.startswith("Vencida") else "Pendiente"
            if pago != "Todos" and est_pago != pago:
                continue
            filas.append(dict(folio=l["folio"], proveedor=self._proveedor(l["id_proveedor"])["razon_social"],
                              entrada=l["entrada"], productos=len(l["renglones"]), total=self._total_lote(l),
                              condicion="Contado" if l["dias"] == 0 else f"Crédito {l['dias']} días",
                              pago=est_pago, tono={"Pagado": "verde", "Vencido": "rojo"}.get(est_pago, "naranja"),
                              caducidad=min(r["caducidad"] for r in l["renglones"]),
                              kilos=sum((r["recibido"] for r in l["renglones"]), D("0"))))
        total = sum((f["total"] for f in filas), D("0"))
        kilos = sum((f["kilos"] for f in filas), D("0"))
        pendientes = [f for f in filas if f["pago"] != "Pagado"]
        return dict(filas=filas, total=total, kilos=kilos, proveedores=len({f["proveedor"] for f in filas}),
                    costo_promedio=(total / kilos if kilos else D("0")), pendientes=len(pendientes),
                    por_pagar=sum((self._total_lote(next(l for l in self.lotes if l["folio"] == f["folio"]))
                                   - self._pagado_lote(f["folio"]) for f in pendientes), D("0")))

    def detalle_lote(self, folio: str) -> dict:
        l = next(x for x in self.lotes if x["folio"] == folio)
        recibido = sum((r["recibido"] for r in l["renglones"]), D("0"))
        vendido = sum((r["vendido"] for r in l["renglones"]), D("0"))
        merma = sum((r["merma"] for r in l["renglones"]), D("0"))
        costo_merma = sum(((r["merma"] * r["costo"]).quantize(D("0.01")) for r in l["renglones"]), D("0"))
        productos = []
        for r in l["renglones"]:
            p = self.producto(r["id_producto"])
            dias = (r["caducidad"] - HOY).days
            productos.append(dict(nombre=p["nombre"], unidad=p["unidad_venta"], recibido=r["recibido"], costo=r["costo"],
                                  vendido=r["vendido"], merma=r["merma"], existencia=self._queda(r),
                                  caducidad=r["caducidad"], dias=dias))
        mermas = [dict(m, producto=self.producto(m["id_producto"])["nombre"],
                       costo=(m["cantidad"] * next(r["costo"] for r in l["renglones"] if r["id_producto"] == m["id_producto"])).quantize(D("0.01")))
                  for m in self.mermas if m["lote"] == folio]
        est, tono = self._estatus_cxp(l)
        total = self._total_lote(l)
        return dict(folio=folio, proveedor=self._proveedor(l["id_proveedor"])["razon_social"], entrada=l["entrada"],
                    factura=l["factura"], total=total, recibido=recibido, dias=l["dias"],
                    vendido=vendido, merma=merma, costo_merma=costo_merma, productos=productos, mermas=mermas,
                    vence=l["entrada"] + timedelta(days=l["dias"]), pagado=self._pagado_lote(folio),
                    saldo=total - self._pagado_lote(folio), estatus=est, tono=tono)

    def cuentas_por_pagar(self, id_proveedor=None, estatus="Pendientes y vencidas") -> dict:
        filas = []
        for l in sorted(self.lotes, key=lambda x: x["entrada"] + timedelta(days=x["dias"])):
            if l["dias"] == 0:
                continue
            total = self._total_lote(l)
            saldo = total - self._pagado_lote(l["folio"])
            est, tono = self._estatus_cxp(l)
            if estatus == "Pendientes y vencidas" and saldo <= 0 or estatus == "Vencidas" and not est.startswith("Vencida"):
                continue
            if estatus == "Pagadas" and saldo > 0:
                continue
            if id_proveedor and l["id_proveedor"] != id_proveedor:
                continue
            filas.append(dict(lote=l["folio"], proveedor=self._proveedor(l["id_proveedor"])["razon_social"],
                              vence=l["entrada"] + timedelta(days=l["dias"]), total=total, saldo=saldo, estatus=est, tono=tono))
        abiertas = [f for f in filas if f["saldo"] > 0]
        vencidas = [f for f in abiertas if f["estatus"].startswith("Vencida")]
        proximas = [f for f in abiertas if f["estatus"].startswith("Vence")]
        return dict(filas=filas, total=sum((f["saldo"] for f in abiertas), D("0")), lotes=len(abiertas),
                    proveedores=len({f["proveedor"] for f in abiertas}),
                    vencido=sum((f["saldo"] for f in vencidas), D("0")), vencidas=vencidas,
                    proximo=sum((f["saldo"] for f in proximas), D("0")), proximas=proximas)

    def pagar_lote(self, folio: str, monto: D, metodo: str, referencia: str) -> D:
        l = next(x for x in self.lotes if x["folio"] == folio)
        saldo = self._total_lote(l) - self._pagado_lote(folio)
        if monto <= 0:
            raise ErrorNegocio("Ingrese un monto válido.", "monto")
        if monto > saldo:
            raise ErrorNegocio("El pago no puede ser mayor al saldo.", "monto")
        self.pagos_proveedor.append(dict(lote=folio, fecha=HOY, monto=monto, metodo=metodo, referencia=referencia or "—"))
        self._auditar("Proveedores", "Pago a proveedor", f"{folio} · ${monto:,.2f} · {metodo}")
        return saldo - monto

    def estado_cuenta_proveedor(self, id_proveedor: int, desde: date, hasta: date) -> dict:
        prov = self._proveedor(id_proveedor)
        movs = []
        for l in self.lotes:
            if l["id_proveedor"] == id_proveedor:
                movs.append(dict(fecha=l["entrada"], movimiento=f"Compra lote {l['folio']}", referencia=f"Factura {l['factura']}",
                                 cargo=self._total_lote(l), abono=D("0")))
                movs += [dict(fecha=p["fecha"], movimiento=f"Pago lote {l['folio']}", referencia=p["referencia"],
                              cargo=D("0"), abono=p["monto"]) for p in self.pagos_proveedor if p["lote"] == l["folio"]]
        movs.sort(key=lambda m: m["fecha"])
        inicial = sum((m["cargo"] - m["abono"] for m in movs if m["fecha"] < desde), D("0"))
        periodo = [m for m in movs if desde <= m["fecha"] <= hasta]
        saldo = inicial
        for m in periodo:
            saldo += m["cargo"] - m["abono"]
            m["saldo"] = saldo
        vencido = sum((f["saldo"] for f in self.cuentas_por_pagar(id_proveedor)["vencidas"]), D("0"))
        return dict(proveedor=prov, inicial=inicial, movimientos=periodo,
                    compras=sum((m["cargo"] for m in periodo), D("0")), pagos=sum((m["abono"] for m in periodo), D("0")),
                    n_compras=sum(1 for m in periodo if m["cargo"]), n_pagos=sum(1 for m in periodo if m["abono"]),
                    saldo=saldo, vencido=vencido)

    # ================================================================ facturación
    def timbres_disponibles(self) -> tuple[int, int]:
        return self.timbres

    def ticket_para_factura(self, folio: str) -> dict:
        t = self.buscar_ticket(folio)
        if t["facturado"]:
            raise ErrorNegocio("Este ticket ya fue facturado. Un ticket solo se factura una vez.", "ticket")
        return t

    def lista_clientes_fiscales(self, busqueda: str = "") -> list[dict]:
        salida = []
        for c in self.clientes_fiscales:
            if busqueda and busqueda.upper() not in c["rfc"] and busqueda.lower() not in c["razon_social"].lower():
                continue
            salida.append(dict(c, facturas=sum(1 for f in self.facturas if f["rfc"] == c["rfc"])))
        return salida

    def guardar_cliente_fiscal(self, datos: dict, original: str | None = None) -> None:
        if error := error_rfc(datos["rfc"]):
            raise ErrorNegocio(error, "rfc")
        if datos["rfc"] != original and any(c["rfc"] == datos["rfc"] for c in self.clientes_fiscales):
            raise ErrorNegocio("El cliente ya se encuentra registrado.", "rfc")
        if original:
            c = next(x for x in self.clientes_fiscales if x["rfc"] == original)
            c.update(datos)
            self._auditar("Facturación", "Cliente fiscal editado", datos["rfc"])
        else:
            self.clientes_fiscales.append(dict(datos))
            self._auditar("Facturación", "Cliente fiscal registrado", f"{datos['rfc']} · {datos['razon_social']}")

    def timbrar(self, datos: dict) -> dict:
        t = self.tickets[datos["ticket"]]
        if t["facturado"]:
            raise ErrorNegocio("Este ticket ya fue facturado. Un ticket solo se factura una vez.")
        total = sum(((r["precio"] * r["cantidad"]).quantize(D("0.01")) for r in t["renglones"]), D("0"))
        folio = f"F-{max(int(f['folio'][2:]) for f in self.facturas) + 1:04d}"
        uuid = "8A1F3C2E-77B4-4D19-9E0A-5B2C6D3E91F7" if folio == "F-0013" else f"{folio[2:]}D3E91F7-77B4-4D19-9E0A-5B2C6D3E91F7"[:36]
        factura = dict(folio=folio, fecha=HOY, rfc=datos["rfc"], uuid=uuid, total=total, estatus="Vigente",
                       ticket=datos["ticket"], uso=datos["uso"], forma=datos["forma"], metodo_pago=datos["metodo_pago"],
                       correo=datos["correo"], timbrado=self._ahora())
        self.facturas.insert(0, factura)
        t["facturado"] = True
        self.timbres = (self.timbres[0] - 1, self.timbres[1])
        self._auditar("Facturación", "Timbrado", f"Factura {folio} · ticket {datos['ticket']} · ${total:,.2f}")
        return self.detalle_factura(folio)

    def detalle_factura(self, folio: str) -> dict:
        f = next(x for x in self.facturas if x["folio"] == folio)
        c = next((x for x in self.clientes_fiscales if x["rfc"] == f["rfc"]), dict(razon_social=f["rfc"], cp="", rfc=f["rfc"]))
        t = self.tickets.get(f["ticket"])
        return dict(f, cliente=c, renglones=self._renglones_ticket(t) if t else [])

    def lista_facturas(self, texto: str = "", desde=None, hasta=None, estatus: str = "Todas") -> list[dict]:
        salida = []
        for f in self.facturas:
            c = next((x for x in self.clientes_fiscales if x["rfc"] == f["rfc"]), None)
            nombre = c["razon_social"] if c else f["rfc"]
            if texto and texto.upper() not in f["folio"] and texto.upper() not in f["rfc"]:
                continue
            if desde and f["fecha"] < desde or hasta and f["fecha"] > hasta:
                continue
            if estatus != "Todas" and f["estatus"] != estatus.rstrip("s"):
                continue
            salida.append(dict(f, cliente=nombre))
        return salida

    def cancelar_factura(self, folio: str, motivo: str, sustituto: str) -> None:
        f = next(x for x in self.facturas if x["folio"] == folio)
        if motivo.startswith("01") and not sustituto.strip():
            raise ErrorNegocio("El motivo 01 requiere el folio que la sustituye.", "sustituto")
        if sustituto and not any(x["folio"] == sustituto.strip().upper() for x in self.facturas):
            raise ErrorNegocio("No existe una factura con ese folio.", "sustituto")
        f["estatus"] = "Cancelada"
        self._auditar("Facturación", "Factura cancelada", f"{folio} · motivo {motivo[:2]} · sustituye {sustituto or '—'}", "rojo")

    # ================================================================ finanzas
    def dashboard(self, periodo: str) -> dict:
        gastos = sum((g["monto"] for g in self.gastos if g["fecha"].month == 10), D("0"))
        compras = D("196400.00")
        ingresos = D("318240.00")
        egresos = compras + gastos
        utilidad = ingresos - egresos
        conceptos = {}
        for g in self.gastos:
            if g["fecha"].month == 10:
                clave = "Luz, agua y gas" if g["concepto"] in ("Luz", "Agua", "Gas") else g["concepto"]
                conceptos[clave] = conceptos.get(clave, D("0")) + g["monto"]
        filas = [("Compras a proveedores", compras)] + sorted(conceptos.items(), key=lambda kv: -kv[1])
        return dict(ingresos=ingresos, tickets=1382, egresos=egresos, compras=compras, gastos=gastos,
                    utilidad=utilidad, margen=(utilidad / ingresos * 100), margen_anterior=D("18.9"),
                    semanas=[("Sem 1", 72800, 58900), ("Sem 2", 78300, 62910), ("Sem 3", 81100, 64700), ("Sem 4", 86040, 67040)],
                    conceptos=[dict(concepto=c, importe=i, pct=i / egresos * 100) for c, i in filas])

    def lista_gastos(self, concepto: str = "Todos", desde=None, hasta=None) -> dict:
        filas = [g for g in self.gastos
                 if (concepto == "Todos" or g["concepto"] == concepto)
                 and (not desde or g["fecha"] >= desde) and (not hasta or g["fecha"] <= hasta)]
        return dict(filas=filas, total=sum((g["monto"] for g in filas), D("0")))

    def registrar_gasto(self, datos: dict) -> None:
        if datos["monto"] <= 0:
            raise ErrorNegocio("Ingrese un monto válido.", "monto")
        self.gastos.insert(0, dict(datos, usuario=self._usuario_actual()))
        self.gastos.sort(key=lambda g: g["fecha"], reverse=True)
        self._auditar("Finanzas", "Gasto registrado", f"{datos['concepto']} · ${datos['monto']:,.2f}")

    def flujo(self, periodo: str) -> dict:
        return dict(
            inicial=D("25000.00"), ventas=D("312400.00"), cobros=D("2710.00"),
            pagos_proveedores=D("189630.00"), gastos=sum((g["monto"] for g in self.gastos if g["fecha"].month == 10), D("0")),
            credito=D("5840.00"),
            semanas=[("1 al 7 oct", D("70800.00"), D("60100.00")), ("8 al 14 oct", D("76200.00"), D("59980.00")),
                     ("15 al 21 oct", D("79610.00"), D("61200.00")), ("22 al 31 oct", D("88500.00"), D("65500.00"))],
        )

    def _cobrado(self, ticket: str) -> D:
        return sum((c["monto"] for c in self.cobros if c["ticket"] == ticket), D("0"))

    def _debe(self, id_cliente: int) -> D:
        return sum((c["total"] - self._cobrado(c["ticket"]) for c in self.cxc if c["id_cliente"] == id_cliente), D("0"))

    def _tiene_vencido(self, id_cliente: int) -> bool:
        return any(c["id_cliente"] == id_cliente and c["total"] > self._cobrado(c["ticket"])
                   and c["venta"] + timedelta(days=c["dias"]) < HOY for c in self.cxc)

    def lista_clientes_credito(self, busqueda: str = "", estatus: str = "Todos") -> list[dict]:
        salida = []
        for c in self.clientes_credito:
            est = "Pago vencido" if c["estatus"] == "Activo" and self._tiene_vencido(c["id"]) else c["estatus"]
            if estatus != "Todos" and est != estatus:
                continue
            if busqueda and busqueda.lower() not in c["nombre"].lower():
                continue
            debe = self._debe(c["id"])
            salida.append(dict(c, debe=debe, uso=float(debe / c["limite"]) if c["limite"] else 0, estatus_vista=est))
        return salida

    def guardar_cliente_credito(self, datos: dict) -> None:
        if datos["limite"] <= 0:
            raise ErrorNegocio("El límite de crédito debe ser mayor a 0.", "limite")
        if datos["dias"] <= 0:
            raise ErrorNegocio("Los días de crédito son obligatorios.", "dias")
        if datos.get("id"):
            self._cliente(datos["id"]).update(datos)
            self._auditar("Finanzas", "Cliente de crédito editado", f"{datos['nombre']} · {datos['estatus']}")
        else:
            datos = dict(datos, id=max(c["id"] for c in self.clientes_credito) + 1)
            self.clientes_credito.append(datos)
            self._auditar("Finanzas", "Cliente de crédito registrado", f"{datos['nombre']} · límite ${datos['limite']:,.2f}")

    def cuentas_por_cobrar(self, id_cliente=None, estatus: str = "Pendientes y vencidas") -> dict:
        filas = []
        for c in sorted(self.cxc, key=lambda x: x["venta"]):
            saldo = c["total"] - self._cobrado(c["ticket"])
            vence = c["venta"] + timedelta(days=c["dias"])
            if saldo <= 0:
                est, tono = "Pagada", "verde"
            elif vence < HOY:
                est, tono = f"Vencida · {(HOY - vence).days} días", "rojo"
            elif saldo < c["total"]:
                est, tono = "Pago parcial", "naranja"
            else:
                est, tono = "Pendiente", "gris"
            if estatus == "Pendientes y vencidas" and saldo <= 0 or estatus == "Vencidas" and tono != "rojo":
                continue
            if estatus == "Pagadas" and saldo > 0:
                continue
            if id_cliente and c["id_cliente"] != id_cliente:
                continue
            filas.append(dict(ticket=c["ticket"], id_cliente=c["id_cliente"], cliente=self._cliente(c["id_cliente"])["nombre"],
                              venta=c["venta"], vence=vence, total=c["total"], saldo=saldo, estatus=est, tono=tono))
        abiertas = [f for f in filas if f["saldo"] > 0]
        vencidas = [f for f in abiertas if f["tono"] == "rojo"]
        return dict(filas=filas, total=sum((f["saldo"] for f in abiertas), D("0")), ventas=len(abiertas),
                    clientes=len({f["cliente"] for f in abiertas}), vencido=sum((f["saldo"] for f in vencidas), D("0")),
                    vencidas=vencidas, cobrado_mes=sum((c["monto"] for c in self.cobros if c["fecha"].month == 10), D("0")),
                    vendido_credito=D("5840.00"))

    def cajas_abiertas(self) -> list[str]:
        cajas = [f"{c['corto']} · abierta" for c in self.cajas if self.turno and self.turno["id_caja"] == c["id_caja"]]
        return cajas + ["Sin caja (no entra al corte)"]

    def registrar_cobro(self, ticket: str, monto: D, metodo: str, caja: str | None) -> D:
        """Simula sp_registrar_cobro: rechaza cobros mayores al saldo."""
        c = next(x for x in self.cxc if x["ticket"] == ticket)
        saldo = c["total"] - self._cobrado(ticket)
        if monto <= 0:
            raise ErrorNegocio("Ingrese un monto válido.", "monto")
        if monto > saldo:
            raise ErrorNegocio("El cobro no puede ser mayor al saldo.", "monto")
        self.cobros.append(dict(ticket=ticket, fecha=HOY, monto=monto, metodo=metodo,
                                caja=caja.split(" · ")[0] if caja and metodo == "Efectivo" and "abierta" in caja else None))
        if metodo == "Efectivo" and self.turno and caja and "abierta" in caja:
            n, imp = self.turno["base"]["efectivo"]
            self.turno["base"]["efectivo"] = (n, imp + monto)
        self._auditar("Finanzas", "Cobro registrado", f"{ticket} · {self._cliente(c['id_cliente'])['nombre']} · ${monto:,.2f}")
        return saldo - monto

    def estado_cuenta_cliente(self, id_cliente: int, desde: date, hasta: date) -> dict:
        cli = self._cliente(id_cliente)
        movs = []
        for c in self.cxc:
            if c["id_cliente"] != id_cliente:
                continue
            movs.append(dict(fecha=c["venta"], movimiento="Compra a crédito", referencia=f"Ticket {c['ticket']}", cargo=c["total"], abono=D("0")))
            for co in self.cobros:
                if co["ticket"] == c["ticket"]:
                    nombre = "Cobro en efectivo" + (f" · {co['caja']}" if co["caja"] else "") if co["metodo"] == "Efectivo" else f"Cobro por {co['metodo'].lower()}"
                    movs.append(dict(fecha=co["fecha"], movimiento=nombre, referencia=f"Ticket {c['ticket']}", cargo=D("0"), abono=co["monto"]))
        movs.sort(key=lambda m: m["fecha"])
        inicial = sum((m["cargo"] - m["abono"] for m in movs if m["fecha"] < desde), D("0"))
        periodo = [m for m in movs if desde <= m["fecha"] <= hasta]
        saldo = inicial
        for m in periodo:
            saldo += m["cargo"] - m["abono"]
            m["saldo"] = saldo
        abiertas = [f for f in self.cuentas_por_cobrar(id_cliente)["filas"] if f["saldo"] > 0]
        return dict(cliente=cli, inicial=inicial, movimientos=periodo, saldo=saldo,
                    compras=sum((m["cargo"] for m in periodo), D("0")), pagos=sum((m["abono"] for m in periodo), D("0")),
                    n_compras=sum(1 for m in periodo if m["cargo"]), n_pagos=sum(1 for m in periodo if m["abono"]),
                    disponible=cli["limite"] - self._debe(id_cliente),
                    vence=min((f["vence"] for f in abiertas), default=None),
                    estatus="Pago vencido" if self._tiene_vencido(id_cliente) else cli["estatus"])

    # ================================================================ catálogo e inventario
    def lista_categorias(self, busqueda: str = "") -> list[dict]:
        return [dict(c, productos=sum(1 for p in self.productos if p["id_categoria"] == c["id"] and p["activo"]))
                for c in self.categorias if not busqueda or busqueda.lower() in c["nombre"].lower()]

    def categorias_activas(self) -> list[dict]:
        return [c for c in self.categorias if c["activa"]]

    def guardar_categoria(self, datos: dict) -> None:
        if any(c["nombre"].lower() == datos["nombre"].lower() and c["id"] != datos.get("id") for c in self.categorias):
            raise ErrorNegocio("Ya existe una categoría con ese nombre.", "nombre")
        if datos.get("id"):
            activos = sum(1 for p in self.productos if p["id_categoria"] == datos["id"] and p["activo"])
            if not datos["activa"] and activos:
                raise ErrorNegocio(f"No se puede dar de baja: tiene {activos} productos activos.", "estatus")
            self._categoria(datos["id"]).update(datos)
            self._auditar("Catálogo", "Categoría editada", datos["nombre"])
        else:
            self.categorias.append(dict(datos, id=max(c["id"] for c in self.categorias) + 1))
            self._auditar("Catálogo", "Categoría registrada", datos["nombre"])

    def _estado_producto(self, p: dict) -> tuple[str, str]:
        ex = self.existencia(p["id_producto"])
        if ex <= 0:
            return "Sin existencia", "rojo"
        if ex < p["stock_minimo"]:
            return "Bajo", "rojo"
        if any((r["caducidad"] - HOY).days <= 1 for _, r in self._lotes_con_existencia(p["id_producto"])):
            return "Por caducar", "naranja"
        return "Normal", "verde"

    def lista_productos(self, busqueda: str = "", id_categoria=None, existencia: str = "Todas") -> list[dict]:
        salida = []
        for p in self.productos:
            if busqueda and busqueda.lower() not in p["nombre"].lower() and busqueda not in p["codigo_barras"]:
                continue
            if id_categoria and p["id_categoria"] != id_categoria:
                continue
            estado, tono = self._estado_producto(p)
            if existencia == "Bajo el mínimo" and estado not in ("Bajo", "Sin existencia") or \
                    existencia == "Por caducar" and estado != "Por caducar":
                continue
            salida.append(dict(p, categoria=self._categoria(p["id_categoria"])["nombre"],
                               existencia=self.existencia(p["id_producto"]), estado=estado, tono=tono))
        return salida

    def guardar_producto(self, datos: dict) -> None:
        if any(p["codigo_barras"] == datos["codigo_barras"] and p["id_producto"] != datos.get("id_producto") for p in self.productos):
            raise ErrorNegocio("El código de barras ya está registrado.", "codigo")
        if datos["precio_venta"] <= 0:
            raise ErrorNegocio("El precio debe ser mayor a 0.", "precio")
        if datos.get("id_producto"):
            p = self.producto(datos["id_producto"])
            if datos["precio_venta"] != p["precio_venta"]:
                self.historial_precios.setdefault(p["id_producto"], []).insert(0, dict(
                    fecha=self._ahora(), anterior=p["precio_venta"], nuevo=datos["precio_venta"], costo=p["costo"],
                    motivo="Ajuste individual", usuario=self._usuario_actual()))
            p.update(datos)
            self._auditar("Catálogo", "Producto editado", f"{p['codigo_barras']} · {p['nombre']}")
        else:
            nuevo = dict(datos, id_producto=max(p["id_producto"] for p in self.productos) + 1, costo=D("0"),
                         es_frecuente=False, venta_diaria=D("0"), clave_sat="50300000", activo=True)
            self.productos.append(nuevo)
            self._auditar("Catálogo", "Producto registrado", f"{nuevo['codigo_barras']} · {nuevo['nombre']}")

    def _filas_existencias(self) -> list[dict]:
        filas = []
        for p in self.productos:
            if not p["activo"]:
                continue
            ex = self.existencia(p["id_producto"])
            pares = self._lotes_con_existencia(p["id_producto"])
            valor = sum(((self._queda(r) * r["costo"]).quantize(D("0.01")) for _, r in pares), D("0"))
            filas.append(dict(id_producto=p["id_producto"], id_categoria=p["id_categoria"], nombre=p["nombre"],
                              unidad="kg" if p["unidad_venta"] == "kg" else "pza",
                              existencia=ex, minimo=p["stock_minimo"], diaria=p["venta_diaria"],
                              alcanza=(ex / p["venta_diaria"]) if p["venta_diaria"] else None, lotes=len(pares),
                              valor=valor, bajo=ex < p["stock_minimo"]))
        return filas

    def existencias(self, busqueda: str = "", id_categoria=None, mostrar: str = "Todos") -> dict:
        todos = self._filas_existencias()
        filas = [f for f in todos
                 if (not busqueda or busqueda.lower() in f["nombre"].lower())
                 and (not id_categoria or f["id_categoria"] == id_categoria)
                 and not (mostrar == "Bajo el mínimo" and not f["bajo"])
                 and not (mostrar == "Sin existencia" and f["existencia"] > 0)]
        bajos = [f for f in todos if f["bajo"] and f["existencia"] > 0]
        sin = [f for f in todos if f["existencia"] <= 0]
        return dict(filas=filas, valor=sum((f["valor"] for f in todos), D("0")), con_mov=sum(1 for f in todos if f["lotes"]),
                    bajos=bajos, sin=sin, caducar=len(self.lotes_caducidad(dias=3)))

    def lotes_caducidad(self, id_producto=None, dias: int = 7, id_proveedor=None) -> list[dict]:
        filas = []
        for l in self.lotes:
            for r in l["renglones"]:
                queda = self._queda(r)
                faltan = (r["caducidad"] - HOY).days
                if queda <= 0 or faltan > dias:
                    continue
                if id_producto and r["id_producto"] != id_producto or id_proveedor and l["id_proveedor"] != id_proveedor:
                    continue
                p = self.producto(r["id_producto"])
                filas.append(dict(caducidad=r["caducidad"], dias=faltan, producto=p["nombre"], id_producto=p["id_producto"],
                                  lote=l["folio"], proveedor=self._proveedor(l["id_proveedor"])["razon_social"],
                                  recibido=r["recibido"], queda=queda, unidad=p["unidad_venta"],
                                  queda_txt=(f"{queda:.1f} kg" if p["unidad_venta"] == "kg" else f"{queda:.0f} pza"),
                                  costo=(queda * r["costo"]).quantize(D("0.01")),
                                  tono="rojo" if faltan <= 1 else "naranja" if faltan <= 3 else "gris"))
        return sorted(filas, key=lambda f: (f["caducidad"], f["lote"]))

    def lotes_de_producto(self, id_producto: int) -> list[dict]:
        return [dict(lote=l["folio"], queda=self._queda(r), caducidad=r["caducidad"], costo=r["costo"])
                for l, r in self._lotes_con_existencia(id_producto)]

    def movimientos(self, id_producto: int, desde: date, hasta: date, tipo: str = "Todos") -> dict:
        p = self.producto(id_producto)
        movs = []
        for l in self.lotes:
            for r in l["renglones"]:
                if r["id_producto"] == id_producto:
                    movs.append(dict(fecha=l["entrada"], tipo="Entrada", tono="verde", cantidad=r["recibido"],
                                     referencia=f"Lote {l['folio']} · {self._proveedor(l['id_proveedor'])['razon_social']}", usuario="alopez"))
        for m in self.mermas:
            if m["id_producto"] == id_producto:
                movs.append(dict(fecha=m["fecha"], tipo="Merma", tono="naranja", cantidad=-m["cantidad"],
                                 referencia=f"{m['motivo']} · lote {m['lote']}", usuario=m["usuario"]))
        for v in self.ventas_dia:
            if v["id_producto"] == id_producto:
                movs.append(dict(fecha=v["fecha"], tipo="Venta", tono="gris", cantidad=-v["cantidad"],
                                 referencia=f"{v['tickets']} tickets", usuario="Caja 1"))
        movs.sort(key=lambda m: (m["fecha"], {"Entrada": 0, "Merma": 1, "Venta": 2}[m["tipo"]]), reverse=True)
        saldo = self.existencia(id_producto)
        for m in movs:  # existencia después de cada movimiento, de hoy hacia atrás
            m["existencia"] = saldo
            saldo -= m["cantidad"]
        visibles = [m for m in movs if desde <= m["fecha"] <= hasta and (tipo == "Todos" or m["tipo"] == tipo.rstrip("s"))]
        entradas = sum((m["cantidad"] for m in visibles if m["tipo"] == "Entrada"), D("0"))
        ventas = -sum((m["cantidad"] for m in visibles if m["tipo"] == "Venta"), D("0"))
        mermas = -sum((m["cantidad"] for m in visibles if m["tipo"] == "Merma"), D("0"))
        ex = self.existencia(id_producto)
        return dict(producto=p, unidad=p["unidad_venta"], movimientos=visibles, entradas=entradas,
                    lotes_entrada=sum(1 for m in visibles if m["tipo"] == "Entrada"),
                    ventas=ventas, importe_ventas=(ventas * p["precio_venta"]).quantize(D("0.01")),
                    mermas=mermas, costo_mermas=(mermas * p["costo"]).quantize(D("0.01")),
                    pct_merma=(mermas / entradas * 100) if entradas else D("0"),
                    existencia=ex, minimo=p["stock_minimo"], bajo=ex < p["stock_minimo"])

    def previsualizar_precios(self, aplicar: str, id_categoria, id_producto, tipo: str, valor: D) -> list[dict]:
        if aplicar == "Una categoría":
            prods = [p for p in self.productos if p["id_categoria"] == id_categoria and p["activo"]]
        elif aplicar == "Un producto":
            prods = [self.producto(id_producto)]
        else:
            prods = [p for p in self.productos if p["activo"]]
        filas = []
        for p in prods:
            actual = p["precio_venta"]
            if tipo == "Porcentaje de aumento":
                nuevo = actual * (1 + valor / 100)
            elif tipo == "Porcentaje de descuento":
                nuevo = actual * (1 - valor / 100)
            else:
                nuevo = valor
            nuevo = nuevo.quantize(D("0.01"))
            margen = ((nuevo - p["costo"]) / nuevo * 100) if nuevo else D("0")
            filas.append(dict(id_producto=p["id_producto"], nombre=p["nombre"], unidad=p["unidad_venta"], costo=p["costo"],
                              actual=actual, nuevo=nuevo, margen=margen, perdida=nuevo < p["costo"]))
        return filas

    def aplicar_precios(self, filas: list[dict], motivo: str) -> None:
        for f in filas:
            p = self.producto(f["id_producto"])
            self.historial_precios.setdefault(p["id_producto"], []).insert(0, dict(
                fecha=self._ahora(), anterior=p["precio_venta"], nuevo=f["nuevo"], costo=p["costo"], motivo=motivo,
                usuario=self._usuario_actual()))
            p["precio_venta"] = f["nuevo"]
        self._auditar("Catálogo", "Ajuste de precios", f"{len(filas)} productos · {motivo}")

    def historial(self, id_producto: int) -> dict:
        p = self.producto(id_producto)
        cambios = self.historial_precios.get(id_producto, [])
        puntos = [(f"{c['fecha'].day:02d} {['ene','feb','mar','abr','may','jun','jul','ago','sep','oct','nov','dic'][c['fecha'].month-1]}",
                   c["nuevo"], c["costo"]) for c in reversed(cambios)]
        puntos.append(("Hoy", p["precio_venta"], p["costo"]))
        return dict(producto=p, cambios=cambios, puntos=puntos)

    def lista_mermas(self, motivo: str = "Todos") -> dict:
        filas = []
        for m in self.mermas:
            if motivo != "Todos" and m["motivo"] != motivo:
                continue
            p = self.producto(m["id_producto"])
            lote = next(l for l in self.lotes if l["folio"] == m["lote"])
            costo_u = next(r["costo"] for r in lote["renglones"] if r["id_producto"] == m["id_producto"])
            filas.append(dict(m, producto=p["nombre"], unidad=p["unidad_venta"], costo=(m["cantidad"] * costo_u).quantize(D("0.01"))))
        mes = [f for f in filas if f["fecha"].month == 10]
        return dict(filas=filas, kilos_mes=sum((f["cantidad"] for f in mes if f["unidad"] == "kg"), D("0")),
                    costo_mes=sum((f["costo"] for f in mes), D("0")))

    def registrar_merma(self, id_producto: int, lote: str, cantidad: D, motivo: str, obs: str) -> D:
        l = next(x for x in self.lotes if x["folio"] == lote)
        r = next(x for x in l["renglones"] if x["id_producto"] == id_producto)
        if cantidad <= 0:
            raise ErrorNegocio("Ingrese una cantidad válida.", "cantidad")
        if cantidad > self._queda(r):
            raise ErrorNegocio("La cantidad supera la existencia del lote.", "cantidad")
        r["merma"] += cantidad
        costo = (cantidad * r["costo"]).quantize(D("0.01"))
        self.mermas.insert(0, dict(fecha=HOY, id_producto=id_producto, lote=lote, cantidad=cantidad, motivo=motivo,
                                   usuario=self._usuario_actual(), obs=obs))
        self._auditar("Catálogo", "Merma registrada", f"{self.producto(id_producto)['nombre']} {cantidad} · {lote} · ${costo:,.2f}")
        return costo

    # ================================================================ reportes
    def cajeros(self) -> list[str]:
        return [u["nombre"] for u in self.usuarios if u["rol"] in ("Cajero", "Administrador")]

    def reporte(self, numero: int, desde: date, hasta: date, cajero: str) -> dict:
        from app.datos.reportes_demo import generar
        return generar(self, numero, desde, hasta, cajero)

    # ================================================================ administración
    def lista_usuarios(self, busqueda: str = "", rol: str = "Todos") -> list[dict]:
        return [u for u in self.usuarios
                if (rol == "Todos" or u["rol"] == rol)
                and (not busqueda or busqueda.lower() in u["nombre"].lower() or busqueda.lower() in u["usuario"])]

    def nombres_roles(self) -> list[str]:
        return list(self.permisos)

    def guardar_usuario(self, datos: dict) -> None:
        if any(u["usuario"] == datos["usuario"] and u["id"] != datos.get("id") for u in self.usuarios):
            raise ErrorNegocio("El usuario ya existe.", "usuario")
        if any(u["correo"] == datos["correo"] and u["id"] != datos.get("id") for u in self.usuarios):
            raise ErrorNegocio("El correo ya está registrado.", "correo")
        if datos.get("id"):
            u = next(x for x in self.usuarios if x["id"] == datos["id"])
            if u["id"] == self.sesion_usuario["id"] and not datos["activo"]:
                raise ErrorNegocio("No puede darse de baja a sí mismo.", "estatus")
            datos = {k: v for k, v in datos.items() if k != "password" or v}
            if not datos.get("activo", True) and u["activo"]:
                self._auditar("Administración", "Usuario desactivado", f"{u['usuario']} · rol {u['rol']}", "rojo")
            u.update({k: v for k, v in datos.items() if k != "password"})
            self._auditar("Administración", "Usuario editado", f"{u['usuario']} · rol {u['rol']}")
        else:
            nuevo = {k: v for k, v in datos.items() if k != "password"}  # en el servidor se guarda el hash
            nuevo.update(id=max(u["id"] for u in self.usuarios) + 1, ultimo=None)
            self.usuarios.append(nuevo)
            self._auditar("Administración", "Usuario registrado", f"{nuevo['usuario']} · rol {nuevo['rol']}")

    def roles(self) -> list[dict]:
        return [dict(nombre=r, usuarios=sum(1 for u in self.usuarios if u["rol"] == r), fijo=(r == "Administrador"))
                for r in self.permisos]

    def permisos_de(self, rol: str) -> dict:
        return dict(matriz={m: self.permisos[rol].get(m, (0, 0, 0, 0)) for m in
                            ("pos", "compras", "facturacion", "finanzas", "inventario", "reportes", "admin")},
                    especiales=dict(self.especiales.get(rol, {"credito": False, "devoluciones": False, "cortes": False})))

    def guardar_permisos(self, rol: str, matriz: dict, especiales: dict) -> None:
        if rol == "Administrador":
            raise ErrorNegocio("El rol Administrador no se edita.")
        self.permisos[rol] = {m: v for m, v in matriz.items() if any(v)}
        especiales["devoluciones"] = False  # solo el Administrador autoriza (SC-02)
        self.especiales[rol] = especiales
        self._auditar("Administración", "Permisos actualizados", f"Rol {rol}")

    def crear_rol(self, nombre: str) -> None:
        if nombre in self.permisos:
            raise ErrorNegocio("Ya existe un rol con ese nombre.")
        self.permisos[nombre] = {}
        self.especiales[nombre] = {"credito": False, "devoluciones": False, "cortes": False}
        self._auditar("Administración", "Rol creado", nombre)

    def lista_auditoria(self, usuario="Todos", modulo="Todos", accion="Todas", desde=None, hasta=None) -> list[dict]:
        return [a for a in self.auditoria
                if (usuario == "Todos" or a["usuario"] == usuario) and (modulo == "Todos" or a["modulo"] == modulo)
                and (accion == "Todas" or a["accion"] == accion)
                and (not desde or a["fecha"].date() >= desde) and (not hasta or a["fecha"].date() <= hasta)]

    def configuracion_cajas(self) -> dict:
        cajas = []
        for c in self.cajas:
            abierta = self.turno and self.turno["id_caja"] == c["id_caja"]
            cajas.append(dict(c, estado=f"Abierta · {self.turno['usuario']}" if abierta else "Cerrada", abierta=bool(abierta)))
        return dict(cajas=cajas, metodos=deepcopy(self.metodos), dispositivos=dict(self.dispositivos[1]))

    def agregar_caja(self, nombre: str, terminal: str, ip: str) -> None:
        if any(c["terminal"] == terminal for c in self.cajas):
            raise ErrorNegocio("Esa terminal ya tiene una caja.")
        n = len(self.cajas) + 1
        self.cajas.append(dict(id_caja=n, nombre=nombre, corto=f"Caja {n}", terminal=terminal, ip=ip))
        self._auditar("Administración", "Caja agregada", f"{nombre} · {terminal}")

    def activar_metodo(self, id_metodo: int, activo: bool) -> None:
        m = next(x for x in self.metodos if x["id_metodo"] == id_metodo)
        if m["es_efectivo"] and not activo:
            raise ErrorNegocio("El efectivo no se puede desactivar.")
        m["activo"] = activo
        self._auditar("Administración", "Método de pago " + ("activado" if activo else "desactivado"), m["nombre"])

    def guardar_dispositivos(self, datos: dict) -> None:
        self.dispositivos[1].update(datos)
        self._auditar("Administración", "Dispositivos guardados", "Caja 1")
