"""Consultas de clientes de crédito (SC-03, HU-39)."""
from sqlalchemy import Connection, RowMapping, text

# Lo que debe cada cliente y si tiene alguna cuenta vencida.
_CLIENTES = """
    SELECT cc.id_cliente_credito, cc.nombre, cc.telefono, cc.correo, cc.limite_credito, cc.dias_credito,
           cc.activo, f.rfc AS rfc_fiscal,
           COALESCE(s.debe, 0) AS debe, COALESCE(s.vencido, FALSE) AS vencido
    FROM clientes_credito cc
    LEFT JOIN clientes_fiscales f ON f.id_cliente = cc.id_cliente
    LEFT JOIN (
        SELECT id_cliente_credito, SUM(saldo) AS debe, MAX(fecha_vencimiento < CURDATE()) AS vencido
        FROM cuentas_por_cobrar WHERE estatus = 'pendiente'
        GROUP BY id_cliente_credito
    ) s ON s.id_cliente_credito = cc.id_cliente_credito
"""


def listar_clientes(conn: Connection, busqueda: str | None, activo: bool | None) -> list[RowMapping]:
    return list(
        conn.execute(
            text(_CLIENTES + """
                WHERE (:busqueda IS NULL OR cc.nombre LIKE CONCAT('%', :busqueda, '%'))
                  AND (:activo IS NULL OR cc.activo = :activo)
                ORDER BY cc.nombre
            """),
            {"busqueda": busqueda, "activo": activo},
        ).mappings()
    )


def cliente(conn: Connection, id_cliente: int, bloquear: bool = False) -> RowMapping | None:
    return conn.execute(
        text(_CLIENTES + " WHERE cc.id_cliente_credito = :id" + (" FOR UPDATE" if bloquear else "")),
        {"id": id_cliente},
    ).mappings().first()


def id_fiscal(conn: Connection, rfc: str) -> int | None:
    return conn.execute(text("SELECT id_cliente FROM clientes_fiscales WHERE rfc = :rfc"), {"rfc": rfc}).scalar()


_CAMPOS = ("nombre", "telefono", "correo", "limite_credito", "dias_credito", "activo", "id_cliente")


def insertar_cliente(conn: Connection, datos: dict) -> int:
    return conn.execute(
        text(f"INSERT INTO clientes_credito ({', '.join(_CAMPOS)}) VALUES ({', '.join(':' + c for c in _CAMPOS)})"),
        {c: datos[c] for c in _CAMPOS},
    ).lastrowid


def actualizar_cliente(conn: Connection, id_cliente: int, datos: dict) -> None:
    conn.execute(
        text(f"UPDATE clientes_credito SET {', '.join(f'{c} = :{c}' for c in _CAMPOS)} WHERE id_cliente_credito = :id"),
        {"id": id_cliente, **{c: datos[c] for c in _CAMPOS}},
    )
