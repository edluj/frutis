"""Reglas del punto de venta. Los cálculos y las transacciones viven en los procedimientos
de la base: sp_registrar_venta, sp_abrir_caja, sp_cerrar_caja y sp_registrar_devolucion."""
import logging
from collections.abc import Callable
from decimal import Decimal
from typing import TypeVar

from sqlalchemy import Connection
from sqlalchemy.exc import DBAPIError, SQLAlchemyError

from app.errores import ErrorNegocio
from app.repositories import auditoria, pos, usuarios
from app.schemas.pos import (
    AperturaEntrada, AutorizacionEntrada, AutorizacionSalida, Caja, CorteEntrada, CorteSalida,
    DevolucionEntrada, DevolucionSalida, ResumenCorte, Ticket, VentaEntrada, VentaSalida,
)
from app.security.dependencias import UsuarioActual
from app.security.passwords import HASH_SENUELO, verificar_password
from app.security.tokens import MINUTOS_AUTORIZACION, crear_autorizacion, leer_autorizacion
from app.services.auth import CUENTA_BLOQUEADA

log = logging.getLogger(__name__)

ER_SIGNAL_EXCEPTION = 1644
VENTA_FALLIDA = "No se pudo registrar la venta, intente de nuevo."
APERTURA_FALLIDA = "No se pudo abrir la caja, intente de nuevo."
CORTE_FALLIDO = "No se pudo cerrar la caja, intente de nuevo."
DEVOLUCION_FALLIDA = "No se pudo registrar la devolución, intente de nuevo."
CAJA_AJENA = "La caja no pertenece al usuario."
SIN_CAJA = "No hay una caja abierta."
SIN_TICKET = "No existe un ticket con ese número."
PASSWORD_ADMIN = "Contraseña del Administrador incorrecta."
SOLO_ADMIN = "Solo un Administrador puede autorizar devoluciones."
AUTORIZACION_INVALIDA = "La autorización del Administrador no es válida o ya venció. Pida que autorice de nuevo."

CENTAVO = Decimal("0.01")
T = TypeVar("T")


def _llamar_sp(
    conn: Connection, llamada: Callable[[], T], usuario: UsuarioActual, ip: str | None, rechazo: str, fallo: str
) -> T:
    """Los SIGNAL de la base llegan al cajero con su mensaje; cualquier otro error, con `fallo`."""
    try:
        return llamada()
    except DBAPIError as exc:
        conn.rollback()
        codigo = exc.orig.args[0] if exc.orig is not None and exc.orig.args else None
        if codigo == ER_SIGNAL_EXCEPTION:
            mensaje = str(exc.orig.args[1])
            auditoria.registrar(conn, "pos", rechazo, mensaje, ip, usuario.id_usuario, usuario.usuario)
            conn.commit()
            raise ErrorNegocio(409, mensaje) from exc
        log.exception("Falló el procedimiento (%s)", rechazo)
        raise ErrorNegocio(500, fallo) from exc


def _auditar(conn: Connection, accion: str, detalle: str, ip: str | None, usuario: UsuarioActual) -> None:
    # La operación ya hizo COMMIT: si la bitácora falla no se le pide al cajero repetirla.
    try:
        auditoria.registrar(conn, "pos", accion, detalle, ip, usuario.id_usuario, usuario.usuario)
        conn.commit()
    except SQLAlchemyError:
        log.exception("No se pudo auditar %s: %s", accion, detalle)


def _exigir_caja_propia(conn: Connection, id_caja: int, usuario: UsuarioActual) -> None:
    if not pos.caja_es_de_usuario(conn, id_caja, usuario.id_usuario):
        raise ErrorNegocio(403, CAJA_AJENA)


# ---------------------------------------------------------------- cobro (HU-06, HU-08)

def registrar_venta(
    conn: Connection, venta: VentaEntrada, usuario: UsuarioActual, ip: str | None
) -> VentaSalida:
    _exigir_caja_propia(conn, venta.id_caja, usuario)
    carrito = [{"id_producto": r.id_producto, "cantidad": float(r.cantidad)} for r in venta.carrito]
    fila = _llamar_sp(
        conn,
        lambda: pos.registrar_venta(
            conn, venta.id_caja, usuario.id_usuario, venta.id_metodo,
            venta.monto_recibido, venta.id_cliente_credito, carrito,
        ),
        usuario, ip, "venta_rechazada", VENTA_FALLIDA,
    )
    salida = VentaSalida(**fila)
    _auditar(conn, "venta", f"Folio {salida.folio}, total {salida.total}", ip, usuario)
    return salida


# ---------------------------------------------------------------- apertura y corte (HU-15, HU-09)

def abrir_caja(conn: Connection, datos: AperturaEntrada, usuario: UsuarioActual, ip: str | None) -> Caja:
    fila = _llamar_sp(
        conn,
        lambda: pos.abrir_caja(conn, datos.terminal, usuario.id_usuario, datos.fondo_inicial),
        usuario, ip, "apertura_rechazada", APERTURA_FALLIDA,
    )
    caja = Caja(**fila)
    _auditar(conn, "apertura", f"Caja {caja.id_caja}, terminal {caja.terminal}, fondo {caja.fondo_inicial}", ip, usuario)
    return caja


def resumen_corte(conn: Connection, usuario: UsuarioActual) -> ResumenCorte:
    caja = pos.caja_abierta_de(conn, usuario.id_usuario)
    if caja is None:
        raise ErrorNegocio(404, SIN_CAJA)
    return ResumenCorte(**caja, **pos.resumen_corte(conn, caja["id_caja"]))


def cerrar_caja(conn: Connection, datos: CorteEntrada, usuario: UsuarioActual, ip: str | None) -> CorteSalida:
    _exigir_caja_propia(conn, datos.id_caja, usuario)
    observaciones = (datos.observaciones or "").strip() or None
    fila = _llamar_sp(
        conn,
        lambda: pos.cerrar_caja(conn, datos.id_caja, usuario.id_usuario, datos.efectivo_contado, observaciones),
        usuario, ip, "corte_rechazado", CORTE_FALLIDO,
    )
    contado = datos.efectivo_contado.quantize(CENTAVO)
    salida = CorteSalida(id_caja=datos.id_caja, efectivo_contado=contado, **fila)
    _auditar(
        conn, "corte",
        f"Caja {salida.id_caja}, esperado {salida.efectivo_esperado}, contado {salida.efectivo_contado}, "
        f"diferencia {salida.diferencia}",
        ip, usuario,
    )
    return salida


# ---------------------------------------------------------------- devoluciones (HU-30, SC-02)

def ticket(conn: Connection, folio: str) -> Ticket:
    fila = pos.ticket(conn, folio)
    if fila is None:
        raise ErrorNegocio(404, SIN_TICKET)
    return Ticket(**fila)


def autorizar_devolucion(
    conn: Connection, datos: AutorizacionEntrada, cajero: UsuarioActual, ip: str | None
) -> AutorizacionSalida:
    """El Administrador escribe su contraseña en la terminal del cajero; cuenta para el bloqueo
    de 5 intentos igual que el login."""
    fila = usuarios.buscar_para_login(conn, datos.usuario)

    def rechazar(status: int, mensaje: str, detalle: str) -> ErrorNegocio:
        auditoria.registrar(
            conn, "pos", "autorizacion_rechazada",
            f"{detalle}. Ticket {datos.folio_venta}, solicitó {cajero.usuario}, usuario {datos.usuario}",
            ip, cajero.id_usuario, cajero.usuario,
        )
        conn.commit()
        return ErrorNegocio(status, mensaje)

    if fila is None:
        verificar_password(datos.password, HASH_SENUELO)
        raise rechazar(403, PASSWORD_ADMIN, "Usuario inexistente")
    if fila["bloqueado"]:
        raise rechazar(429, CUENTA_BLOQUEADA, "Cuenta bloqueada")
    if not verificar_password(datos.password, fila["password_hash"]):
        usuarios.registrar_intento_fallido(conn, fila["id_usuario"])
        raise rechazar(403, PASSWORD_ADMIN, "Contraseña incorrecta")
    if not fila["activo"] or not fila["es_administrador"]:
        raise rechazar(403, SOLO_ADMIN, "El usuario no es un Administrador activo")

    usuarios.limpiar_intentos(conn, fila["id_usuario"])
    auditoria.registrar(
        conn, "pos", "autorizacion",
        f"{fila['usuario']} autorizó una devolución del ticket {datos.folio_venta} a {cajero.usuario}",
        ip, fila["id_usuario"], fila["usuario"],
    )
    conn.commit()
    return AutorizacionSalida(
        autorizacion=crear_autorizacion(fila["id_usuario"], fila["usuario"], cajero.id_usuario, datos.folio_venta),
        autorizado_por=fila["nombre_completo"],
        expira_minutos=MINUTOS_AUTORIZACION,
    )


def registrar_devolucion(
    conn: Connection, datos: DevolucionEntrada, usuario: UsuarioActual, ip: str | None
) -> DevolucionSalida:
    _exigir_caja_propia(conn, datos.id_caja, usuario)
    admin = leer_autorizacion(datos.autorizacion, usuario.id_usuario, datos.folio_venta)
    if admin is None:
        raise ErrorNegocio(403, AUTORIZACION_INVALIDA)
    id_admin, usuario_admin = admin

    renglones = [
        {"id_producto": r.id_producto, "cantidad": float(r.cantidad), "estado": r.estado} for r in datos.renglones
    ]
    fila = _llamar_sp(
        conn,
        lambda: pos.registrar_devolucion(
            conn, datos.folio_venta, datos.id_caja, usuario.id_usuario, id_admin,
            datos.motivo.strip(), datos.reembolso, renglones,
        ),
        usuario, ip, "devolucion_rechazada", DEVOLUCION_FALLIDA,
    )
    salida = DevolucionSalida(folio=fila["folio"], total=fila["total"], reembolso=datos.reembolso)
    _auditar(
        conn, "devolucion",
        f"Folio {salida.folio} del ticket {datos.folio_venta}, total {salida.total}, "
        f"reembolso {salida.reembolso}, autorizó {usuario_admin}",
        ip, usuario,
    )
    return salida
