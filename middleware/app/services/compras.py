"""Reglas de Compras: proveedores (HU-23), lotes de compra (HU-11) y cuentas por pagar (HU-25)."""
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import Connection
from sqlalchemy.exc import IntegrityError

from app.errores import ErrorNegocio
from app.repositories import auditoria
from app.repositories import compras as repositorio
from app.schemas.compras import (
    LoteDetalle, LoteEntrada, LoteRegistrado, PagoEntrada, PagoRegistrado, Proveedor, ProveedorEntrada,
)
from app.security.dependencias import UsuarioActual

ER_DUP_ENTRY = 1062
RFC_REPETIDO = "Ya existe un proveedor con ese RFC."
CENTAVO = Decimal("0.01")


def _auditar(conn: Connection, accion: str, detalle: str, ip: str | None, usuario: UsuarioActual) -> None:
    auditoria.registrar(conn, "compras", accion, detalle, ip, usuario.id_usuario, usuario.usuario)


def guardar_proveedor(
    conn: Connection, datos: ProveedorEntrada, usuario: UsuarioActual, ip: str | None, id_proveedor: int | None = None
) -> Proveedor:
    if id_proveedor is not None:
        actual = repositorio.proveedor(conn, id_proveedor, bloquear=True)
        if actual is None:
            raise ErrorNegocio(404, "Proveedor no encontrado.")
        if not datos.activo and actual["saldo"] > 0:
            raise ErrorNegocio(409, "No se puede dar de baja: tiene saldo por pagar.", "estatus")
    if repositorio.rfc_en_uso(conn, datos.rfc, id_proveedor):
        raise ErrorNegocio(409, RFC_REPETIDO, "rfc")
    valores = datos.model_dump()
    try:
        if id_proveedor is None:
            id_proveedor = repositorio.insertar_proveedor(conn, valores)
            accion = "proveedor_alta"
        else:
            repositorio.actualizar_proveedor(conn, id_proveedor, valores)
            accion = "proveedor_edicion"
    except IntegrityError as exc:
        conn.rollback()
        if exc.orig is not None and exc.orig.args and exc.orig.args[0] == ER_DUP_ENTRY:
            raise ErrorNegocio(409, RFC_REPETIDO, "rfc") from exc
        raise
    _auditar(conn, accion, f"{datos.razon_social} · {datos.rfc}", ip, usuario)
    salida = Proveedor(**repositorio.proveedor(conn, id_proveedor))
    conn.commit()
    return salida


def registrar_lote(conn: Connection, datos: LoteEntrada, usuario: UsuarioActual, ip: str | None) -> LoteRegistrado:
    """Entrada de mercancía en una sola transacción: lote, existencias, costos y cuenta por pagar."""
    proveedor = repositorio.proveedor(conn, datos.id_proveedor)
    if proveedor is None or not proveedor["activo"]:
        raise ErrorNegocio(409, "Elija un proveedor activo.", "proveedor")
    if datos.entrada > date.today():
        raise ErrorNegocio(409, "La fecha de entrada no puede ser futura.", "entrada")

    ids = [r.id_producto for r in datos.renglones]
    if len(set(ids)) != len(ids):
        raise ErrorNegocio(409, "Un producto aparece dos veces en el lote; junte las cantidades en un renglón.")
    productos = repositorio.productos_para_lote(conn, ids)
    for r in datos.renglones:
        p = productos.get(r.id_producto)
        if p is None or not p["activo"]:
            raise ErrorNegocio(409, "Producto no encontrado o inactivo.")
        if p["unidad_venta"] == "pieza" and r.cantidad != r.cantidad.to_integral_value():
            raise ErrorNegocio(409, f"{p['nombre']} se compra por pieza: use cantidades enteras.")
        if r.caducidad < datos.entrada:
            raise ErrorNegocio(409, f"La caducidad de {p['nombre']} es anterior a la entrada.")

    total = sum(((r.cantidad * r.costo).quantize(CENTAVO) for r in datos.renglones), Decimal("0"))
    credito = datos.dias_credito > 0
    id_lote, folio = repositorio.insertar_lote(
        conn, datos.id_proveedor, usuario.id_usuario, datos.entrada, credito, total, datos.factura
    )
    for r in datos.renglones:
        repositorio.insertar_existencia(conn, id_lote, r.id_producto, r.cantidad, r.costo, r.caducidad)
        # El costo de la última compra es el costo vigente del producto.
        repositorio.actualizar_costo(conn, r.id_producto, r.costo)
    if credito:
        repositorio.insertar_cuenta_por_pagar(conn, id_lote, total, datos.entrada + timedelta(days=datos.dias_credito))
    condicion = f"crédito {datos.dias_credito} días" if credito else "contado"
    _auditar(conn, "lote_alta", f"{folio} · {proveedor['razon_social']} · ${total} · {condicion}", ip, usuario)
    conn.commit()
    return LoteRegistrado(folio=folio, total=total)


def detalle_lote(conn: Connection, folio: str) -> LoteDetalle:
    lote = repositorio.lote(conn, folio)
    if lote is None:
        raise ErrorNegocio(404, "Lote no encontrado.")
    return LoteDetalle(
        **lote,
        productos=repositorio.renglones_de_lote(conn, lote["id_lote"]),
        mermas=repositorio.mermas_de_lote(conn, lote["id_lote"]),
    )


def pagar_lote(conn: Connection, folio: str, datos: PagoEntrada, usuario: UsuarioActual, ip: str | None) -> PagoRegistrado:
    """Abono a la cuenta por pagar de un lote; queda como egreso en gastos_operativos (HU-25)."""
    cuenta = repositorio.cuenta_de_lote(conn, folio)
    if cuenta is None:
        raise ErrorNegocio(404, "Ese lote no tiene cuenta por pagar.")
    if datos.monto > cuenta["saldo"]:
        raise ErrorNegocio(409, "El pago no puede ser mayor al saldo.", "monto")
    metodo = repositorio.id_metodo(conn, datos.metodo)
    if metodo is None:
        raise ErrorNegocio(409, "Método de pago no disponible.", "metodo")
    repositorio.registrar_pago(conn, cuenta["id_cxp"], folio, datos.monto, metodo, datos.referencia, usuario.id_usuario)
    saldo = cuenta["saldo"] - datos.monto
    _auditar(conn, "pago_proveedor", f"{folio} · ${datos.monto} · {datos.metodo} · saldo ${saldo}", ip, usuario)
    conn.commit()
    return PagoRegistrado(saldo=saldo)
