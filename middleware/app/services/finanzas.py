"""Reglas de los clientes de crédito (HU-39)."""
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import Connection

from app.errores import ErrorNegocio
from app.repositories import auditoria
from app.repositories import finanzas as repositorio
from app.schemas.finanzas import ClienteCredito, ClienteCreditoEntrada, ClienteCreditoPos
from app.security.dependencias import UsuarioActual


def guardar_cliente(
    conn: Connection, datos: ClienteCreditoEntrada, usuario: UsuarioActual, ip: str | None,
    id_cliente: int | None = None,
) -> ClienteCredito:
    if id_cliente is not None and repositorio.cliente(conn, id_cliente, bloquear=True) is None:
        raise ErrorNegocio(404, "Cliente de crédito no encontrado.")
    valores = datos.model_dump(exclude={"rfc_fiscal"})
    valores["id_cliente"] = None
    if datos.rfc_fiscal:
        valores["id_cliente"] = repositorio.id_fiscal(conn, datos.rfc_fiscal)
        if valores["id_cliente"] is None:
            raise ErrorNegocio(409, "No hay datos fiscales con ese RFC.", "fiscal")
    if id_cliente is None:
        id_cliente = repositorio.insertar_cliente(conn, valores)
        accion, detalle = "cliente_credito_alta", f"{datos.nombre} · límite ${datos.limite_credito}"
    else:
        repositorio.actualizar_cliente(conn, id_cliente, valores)
        estatus = "Activo" if datos.activo else "Suspendido"
        accion, detalle = "cliente_credito_edicion", f"{datos.nombre} · {estatus} · límite ${datos.limite_credito}"
    auditoria.registrar(conn, "finanzas", accion, detalle, ip, usuario.id_usuario, usuario.usuario)
    salida = ClienteCredito(**repositorio.cliente(conn, id_cliente))
    conn.commit()
    return salida


def clientes_para_pos(conn: Connection) -> list[ClienteCreditoPos]:
    # Solo activos: un cliente suspendido no compra a crédito (sp_registrar_venta también lo rechaza).
    vence = date.today()
    return [
        ClienteCreditoPos(
            **{k: c[k] for k in ("id_cliente_credito", "nombre", "limite_credito", "debe", "dias_credito", "vencido")},
            disponible=max(c["limite_credito"] - c["debe"], Decimal("0.00")), vence=vence + timedelta(days=c["dias_credito"]),
        )
        for c in repositorio.listar_clientes(conn, None, True)
    ]
