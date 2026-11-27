"""Reglas de facturación: datos fiscales (HU-32), timbrado (HU-12a) y cancelación (HU-33)."""
import logging
from datetime import datetime
from decimal import Decimal
from xml.etree import ElementTree as ET

from sqlalchemy import Connection

from app.config import get_settings
from app.errores import ErrorNegocio
from app.integrations.pac import Pac, SinConexion
from app.repositories import auditoria
from app.repositories import facturacion as repositorio
from app.schemas.facturacion import (
    CancelacionEntrada, ClienteFiscal, ClienteFiscalEntrada, Concepto, Factura, FacturaEntrada, TicketParaFactura,
    Timbres,
)
from app.security.dependencias import UsuarioActual

log = logging.getLogger(__name__)

NS_CFDI = "http://www.sat.gob.mx/cfd/4"
CENTAVO = Decimal("0.01")
YA_FACTURADO = "Este ticket ya fue facturado. Un ticket solo se factura una vez."
SIN_CONEXION = "Sin conexión a internet, no es posible timbrar."
UNIDAD_SAT = {"kg": "KGM", "pieza": "H87"}


def _auditar(conn: Connection, accion: str, detalle: str, ip: str | None, usuario: UsuarioActual) -> None:
    auditoria.registrar(conn, "facturacion", accion, detalle, ip, usuario.id_usuario, usuario.usuario)


def timbres(conn: Connection) -> Timbres:
    contratados = get_settings().timbres_contratados
    return Timbres(disponibles=max(contratados - repositorio.timbres_usados(conn), 0), contratados=contratados)


# ---------------------------------------------------------------- datos fiscales (HU-32)

def guardar_cliente(
    conn: Connection, datos: ClienteFiscalEntrada, usuario: UsuarioActual, ip: str | None, id_cliente: int | None = None
) -> ClienteFiscal:
    if id_cliente is not None and repositorio.cliente(conn, id_cliente) is None:
        raise ErrorNegocio(404, "Cliente fiscal no encontrado.")
    if repositorio.rfc_en_uso(conn, datos.rfc, id_cliente):
        raise ErrorNegocio(409, "El cliente ya se encuentra registrado.", "rfc")
    if id_cliente is None:
        id_cliente = repositorio.insertar_cliente(conn, datos.model_dump())
        accion = "cliente_fiscal_alta"
    else:
        repositorio.actualizar_cliente(conn, id_cliente, datos.model_dump())
        accion = "cliente_fiscal_edicion"
    _auditar(conn, accion, f"{datos.rfc} · {datos.razon_social}", ip, usuario)
    salida = ClienteFiscal(**repositorio.cliente(conn, id_cliente))
    conn.commit()
    return salida


# ---------------------------------------------------------------- timbrado (HU-12a)

def _xml(folio: str, datos: FacturaEntrada, receptor: dict, montos: dict, conceptos: list[dict]) -> str:
    """CFDI 4.0 sin sello: los precios del ticket incluyen IVA, aquí se separa por concepto."""
    s = get_settings()
    ET.register_namespace("cfdi", NS_CFDI)
    q = lambda n: f"{{{NS_CFDI}}}{n}"  # noqa: E731
    raiz = ET.Element(q("Comprobante"), {
        "Version": "4.0", "Serie": "F", "Folio": folio.removeprefix("F-"),
        "Fecha": datetime.now().replace(microsecond=0).isoformat(),
        "FormaPago": datos.forma_pago, "SubTotal": str(montos["subtotal"]), "Moneda": "MXN",
        "Total": str(montos["total"]), "TipoDeComprobante": "I", "Exportacion": "01",
        "MetodoPago": datos.metodo_pago, "LugarExpedicion": s.emisor_cp,
    })
    ET.SubElement(raiz, q("Emisor"), {"Rfc": s.emisor_rfc, "Nombre": s.emisor_nombre, "RegimenFiscal": s.emisor_regimen})
    ET.SubElement(raiz, q("Receptor"), {
        "Rfc": receptor["rfc"], "Nombre": receptor["razon_social"].upper(), "DomicilioFiscalReceptor": datos.codigo_postal,
        "RegimenFiscalReceptor": datos.regimen_fiscal, "UsoCFDI": datos.uso_cfdi,
    })
    nodo = ET.SubElement(raiz, q("Conceptos"))
    for c in conceptos:
        tasa = Decimal(c["tasa_iva"])
        base = (c["importe"] / (1 + tasa)).quantize(CENTAVO)
        concepto = ET.SubElement(nodo, q("Concepto"), {
            "ClaveProdServ": c["clave_sat"], "Cantidad": str(c["cantidad"]), "ClaveUnidad": UNIDAD_SAT.get(c["unidad_venta"], "H87"),
            "Descripcion": c["nombre"], "ValorUnitario": str((base / c["cantidad"]).quantize(Decimal("0.000001"))),
            "Importe": str(base), "ObjetoImp": "02",
        })
        impuestos = ET.SubElement(ET.SubElement(concepto, q("Impuestos")), q("Traslados"))
        ET.SubElement(impuestos, q("Traslado"), {
            "Base": str(base), "Impuesto": "002", "TipoFactor": "Tasa", "TasaOCuota": f"{tasa:.6f}",
            "Importe": str((c["importe"] - base).quantize(CENTAVO)),
        })
    return ET.tostring(raiz, encoding="unicode")


def _venta_facturable(conn: Connection, folio_venta: str, bloquear: bool = True):
    venta = repositorio.venta_para_factura(conn, folio_venta, bloquear)
    if venta is None:
        raise ErrorNegocio(404, "Ticket no encontrado.", "ticket")
    if venta["facturado"]:
        raise ErrorNegocio(409, YA_FACTURADO, "ticket")
    if venta["estatus"] != "pagada":
        raise ErrorNegocio(409, "El ticket tiene devoluciones: no se puede facturar.", "ticket")
    return venta


def ticket(conn: Connection, folio_venta: str) -> TicketParaFactura:
    venta = _venta_facturable(conn, folio_venta, bloquear=False)
    return TicketParaFactura(folio=venta["folio"], total=venta["total"], metodo=venta["metodo"],
                             conceptos=repositorio.conceptos_de_venta(conn, venta["id_venta"]))


def timbrar(conn: Connection, datos: FacturaEntrada, usuario: UsuarioActual, ip: str | None, pac: Pac) -> Factura:
    venta = _venta_facturable(conn, datos.folio_venta)
    receptor = repositorio.cliente_por_rfc(conn, datos.rfc)
    if receptor is None:
        raise ErrorNegocio(409, "Registre primero los datos fiscales de ese RFC.", "rfc")
    if timbres(conn).disponibles <= 0:
        raise ErrorNegocio(409, "No quedan timbres disponibles.")

    montos = {k: venta[k] for k in ("subtotal", "iva", "total")}
    valores = datos.model_dump()
    if venta["id_borrador"]:
        id_factura = venta["id_borrador"]
        folio = repositorio.actualizar_borrador(conn, id_factura, receptor["id_cliente"], valores, usuario.id_usuario)
    else:
        id_factura, folio = repositorio.insertar_borrador(
            conn, venta["id_venta"], receptor["id_cliente"], valores, montos, usuario.id_usuario
        )
    # El borrador se confirma antes de llamar al PAC: si no responde, se conserva para reintentar.
    conn.commit()

    conceptos = repositorio.conceptos_de_venta(conn, venta["id_venta"])
    try:
        timbre = pac.timbrar(_xml(folio, datos, receptor, montos, conceptos))
    except SinConexion as exc:
        _auditar(conn, "factura_borrador", f"{folio} · ticket {datos.folio_venta} · PAC sin respuesta", ip, usuario)
        conn.commit()
        raise ErrorNegocio(503, SIN_CONEXION) from exc

    carpeta = get_settings().cfdi_dir
    carpeta.mkdir(parents=True, exist_ok=True)
    archivo = carpeta / f"{folio}_{timbre.uuid}.xml"
    archivo.write_text(timbre.xml, encoding="utf-8")
    repositorio.marcar_timbrada(conn, id_factura, timbre.uuid, timbre.fecha, str(archivo))
    # El PAC simulado no envía correos (SC-05): queda registrado a quién se habría enviado.
    _auditar(conn, "factura_timbrada",
             f"{folio} · ticket {datos.folio_venta} · ${venta['total']} · UUID {timbre.uuid} · para {datos.correo}",
             ip, usuario)
    conn.commit()
    return detalle(conn, folio)


def detalle(conn: Connection, folio: str) -> Factura:
    fila = repositorio.factura(conn, folio)
    if fila is None:
        raise ErrorNegocio(404, "Factura no encontrada.")
    conceptos = [Concepto(**c) for c in repositorio.conceptos_de_venta(conn, fila["id_venta"])]
    return Factura(**fila, conceptos=conceptos)


def xml(conn: Connection, folio: str) -> str:
    fila = repositorio.factura(conn, folio)
    if fila is None or not fila["xml_path"]:
        raise ErrorNegocio(404, "La factura no tiene XML timbrado.")
    try:
        with open(fila["xml_path"], encoding="utf-8") as f:
            return f.read()
    except OSError as exc:
        log.error("No se encontró el XML de %s", folio)
        raise ErrorNegocio(404, "La factura no tiene XML timbrado.") from exc


# ---------------------------------------------------------------- cancelación (HU-33)

def cancelar(conn: Connection, folio: str, datos: CancelacionEntrada, usuario: UsuarioActual, ip: str | None,
             pac: Pac) -> Factura:
    fila = repositorio.factura(conn, folio, bloquear=True)
    if fila is None:
        raise ErrorNegocio(404, "Factura no encontrada.")
    if fila["estatus"] != "Vigente":
        raise ErrorNegocio(409, "Solo se cancelan facturas vigentes.")
    uuid_sustituto = None
    if datos.motivo == "01":
        if not datos.folio_sustituto:
            raise ErrorNegocio(409, "El motivo 01 requiere el folio que la sustituye.", "sustituto")
        sustituta = repositorio.factura(conn, datos.folio_sustituto)
        if sustituta is None or sustituta["estatus"] != "Vigente" or sustituta["folio"] == folio:
            raise ErrorNegocio(409, "No existe una factura vigente con ese folio.", "sustituto")
        uuid_sustituto = sustituta["uuid"]
    try:
        fecha = pac.cancelar(fila["uuid"], datos.motivo, uuid_sustituto)
    except SinConexion as exc:
        raise ErrorNegocio(503, "Sin conexión a internet, no es posible cancelar.") from exc
    repositorio.marcar_cancelada(conn, fila["id_factura"], datos.motivo, uuid_sustituto, fecha)
    _auditar(conn, "factura_cancelada",
             f"{folio} · motivo {datos.motivo} · sustituye {datos.folio_sustituto or '—'}", ip, usuario)
    conn.commit()
    return detalle(conn, folio)
