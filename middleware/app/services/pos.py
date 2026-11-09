"""Reglas del cobro; el cálculo y la transacción viven en sp_registrar_venta."""
import logging

from sqlalchemy import Connection
from sqlalchemy.exc import DBAPIError, SQLAlchemyError

from app.errores import ErrorNegocio
from app.repositories import auditoria, pos
from app.schemas.pos import VentaEntrada, VentaSalida
from app.security.dependencias import UsuarioActual

log = logging.getLogger(__name__)

ER_SIGNAL_EXCEPTION = 1644
VENTA_FALLIDA = "No se pudo registrar la venta, intente de nuevo."


def registrar_venta(
    conn: Connection, venta: VentaEntrada, usuario: UsuarioActual, ip: str | None
) -> VentaSalida:
    if not pos.caja_es_de_usuario(conn, venta.id_caja, usuario.id_usuario):
        raise ErrorNegocio(403, "La caja no pertenece al usuario.")

    carrito = [{"id_producto": r.id_producto, "cantidad": float(r.cantidad)} for r in venta.carrito]
    try:
        fila = pos.registrar_venta(
            conn, venta.id_caja, usuario.id_usuario, venta.id_metodo,
            venta.monto_recibido, venta.id_cliente_credito, carrito,
        )
    except DBAPIError as exc:
        conn.rollback()
        codigo = exc.orig.args[0] if exc.orig is not None and exc.orig.args else None
        if codigo == ER_SIGNAL_EXCEPTION:
            mensaje = str(exc.orig.args[1])
            auditoria.registrar(
                conn, "pos", "venta_rechazada", mensaje, ip, usuario.id_usuario, usuario.usuario
            )
            conn.commit()
            raise ErrorNegocio(409, mensaje) from exc
        log.exception("Falló sp_registrar_venta")
        raise ErrorNegocio(500, VENTA_FALLIDA) from exc

    salida = VentaSalida(**fila)
    # La venta ya hizo COMMIT: si la bitácora falla no se le dice al cajero
    # que cobre otra vez.
    try:
        auditoria.registrar(
            conn, "pos", "venta", f"Folio {salida.folio}, total {salida.total}", ip,
            usuario.id_usuario, usuario.usuario,
        )
        conn.commit()
    except SQLAlchemyError:
        log.exception("No se pudo auditar la venta %s", salida.folio)
    return salida
