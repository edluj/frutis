"""Bitácora de movimientos (flujo V). La tabla es de solo inserción."""
from sqlalchemy import Connection, text


def registrar(
    conn: Connection,
    modulo: str,
    accion: str,
    detalle: str | None,
    ip: str | None,
    id_usuario: int | None = None,
    usuario: str | None = None,
) -> None:
    conn.execute(
        text("""
            INSERT INTO auditoria (id_usuario, usuario, modulo, accion, detalle, ip)
            VALUES (:id_usuario, :usuario, :modulo, :accion, :detalle, :ip)
        """),
        {
            "id_usuario": id_usuario,
            "usuario": usuario,
            "modulo": modulo,
            "accion": accion,
            "detalle": detalle[:1000] if detalle else None,
            "ip": ip,
        },
    )
