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


# ---------------------------------------------------------------- cuentas por cobrar y cobros (HU-38b)

def cuentas_por_cobrar(conn: Connection, id_cliente: int | None) -> list[RowMapping]:
    return list(
        conn.execute(
            text("""
                SELECT v.folio AS ticket, c.id_cliente_credito AS id_cliente, cc.nombre AS cliente,
                       DATE(v.fecha) AS venta, c.fecha_vencimiento AS vence, c.monto_total AS total, c.saldo
                FROM cuentas_por_cobrar c
                JOIN ventas_cabecera v ON v.id_venta = c.id_venta
                JOIN clientes_credito cc ON cc.id_cliente_credito = c.id_cliente_credito
                WHERE (:cliente IS NULL OR c.id_cliente_credito = :cliente)
                ORDER BY v.fecha
            """),
            {"cliente": id_cliente},
        ).mappings()
    )


def id_cxc(conn: Connection, ticket: str) -> int | None:
    return conn.execute(
        text("SELECT c.id_cxc FROM cuentas_por_cobrar c JOIN ventas_cabecera v ON v.id_venta = c.id_venta WHERE v.folio = :t"),
        {"t": ticket},
    ).scalar()


def id_metodo(conn: Connection, nombre: str) -> int | None:
    return conn.execute(
        text("SELECT id_metodo FROM metodos_pago WHERE nombre = :nombre AND es_credito = FALSE"), {"nombre": nombre}
    ).scalar()


def cajas_abiertas(conn: Connection) -> list[RowMapping]:
    return list(conn.execute(text("SELECT id_caja, terminal FROM cajas_pos WHERE estatus = 'abierta' ORDER BY terminal"))
                .mappings())


def registrar_cobro(conn: Connection, id_cxc: int, monto, id_metodo: int, id_caja: int | None, id_usuario: int):
    conn.execute(
        text("CALL sp_registrar_cobro(:cxc, :monto, :metodo, :caja, :usuario, @saldo)"),
        {"cxc": id_cxc, "monto": monto, "metodo": id_metodo, "caja": id_caja, "usuario": id_usuario},
    )
    return conn.execute(text("SELECT @saldo")).scalar_one()


def movimientos_cliente(conn: Connection, id_cliente: int) -> list[RowMapping]:
    """Compras a crédito (cargos), cobros y devoluciones abonadas al crédito (abonos)."""
    return list(
        conn.execute(
            text("""
                SELECT DATE(v.fecha) AS fecha, 'Compra a crédito' AS movimiento, CONCAT('Ticket ', v.folio) AS referencia,
                       c.monto_total AS cargo, 0 AS abono, v.fecha AS momento
                FROM cuentas_por_cobrar c JOIN ventas_cabecera v ON v.id_venta = c.id_venta
                WHERE c.id_cliente_credito = :cliente
                UNION ALL
                SELECT DATE(co.fecha),
                       IF(m.es_efectivo, CONCAT('Cobro en efectivo', COALESCE(CONCAT(' · ', cj.terminal), '')),
                          CONCAT('Cobro por ', LOWER(m.nombre))),
                       CONCAT('Ticket ', v.folio), 0, co.monto, co.fecha
                FROM cobros_clientes co
                JOIN cuentas_por_cobrar c ON c.id_cxc = co.id_cxc
                JOIN ventas_cabecera v ON v.id_venta = c.id_venta
                JOIN metodos_pago m ON m.id_metodo = co.id_metodo
                LEFT JOIN cajas_pos cj ON cj.id_caja = co.id_caja
                WHERE c.id_cliente_credito = :cliente
                UNION ALL
                SELECT DATE(MIN(d.fecha)), CONCAT('Devolución ', d.folio), CONCAT('Ticket ', v.folio), 0, SUM(d.importe),
                       MIN(d.fecha)
                FROM devoluciones d
                JOIN cuentas_por_cobrar c ON c.id_venta = d.id_venta
                JOIN ventas_cabecera v ON v.id_venta = d.id_venta
                WHERE c.id_cliente_credito = :cliente AND d.reembolso = 'credito'
                GROUP BY d.folio, v.folio
                ORDER BY momento
            """),
            {"cliente": id_cliente},
        ).mappings()
    )


# ---------------------------------------------------------------- gastos (HU-26)

def listar_gastos(conn: Connection, desde, hasta) -> list[RowMapping]:
    # El detalle va en el concepto ("Luz · bimestre"): gastos_operativos no tiene otra columna.
    return list(
        conn.execute(
            text("""
                SELECT g.fecha, SUBSTRING_INDEX(g.concepto, ' · ', 1) AS concepto,
                       IF(LOCATE(' · ', g.concepto) > 0, SUBSTRING(g.concepto, LOCATE(' · ', g.concepto) + 3), '') AS detalle,
                       m.nombre AS metodo, g.monto, g.comprobante_path IS NOT NULL AS comprobante, u.usuario
                FROM gastos_operativos g
                JOIN metodos_pago m ON m.id_metodo = g.id_metodo
                JOIN usuarios u ON u.id_usuario = g.id_usuario
                WHERE g.tipo = 'operativo'
                  AND (:desde IS NULL OR g.fecha >= :desde) AND (:hasta IS NULL OR g.fecha <= :hasta)
                ORDER BY g.fecha DESC, g.id_gasto DESC
            """),
            {"desde": desde, "hasta": hasta},
        ).mappings()
    )


def registrar_gasto(conn: Connection, fecha, concepto: str, monto, id_metodo: int, id_usuario: int) -> None:
    conn.execute(
        text("""
            INSERT INTO gastos_operativos (tipo, concepto, monto, fecha, id_metodo, id_usuario)
            VALUES ('operativo', :concepto, :monto, :fecha, :metodo, :usuario)
        """),
        {"concepto": concepto[:120], "monto": monto, "fecha": fecha, "metodo": id_metodo, "usuario": id_usuario},
    )


# ---------------------------------------------------------------- dashboard y flujo (HU-27, HU-37)

def eventos(conn: Connection, desde, hasta) -> list[RowMapping]:
    """Montos del periodo [desde, hasta) por clase. `desde` None = desde el inicio (saldo inicial del flujo)."""
    return list(
        conn.execute(
            text("""
                SELECT DATE(v.fecha) AS fecha, IF(m.es_credito, 'venta_credito', 'venta_cobrada') AS clase,
                       '' AS concepto, v.total AS monto
                FROM ventas_cabecera v JOIN metodos_pago m ON m.id_metodo = v.id_metodo
                WHERE v.estatus <> 'cancelada' AND (:desde IS NULL OR v.fecha >= :desde) AND v.fecha < :hasta
                UNION ALL
                SELECT DATE(d.fecha), IF(d.reembolso = 'credito', 'devolucion_credito', 'devolucion_pagada'), '', d.importe
                FROM devoluciones d WHERE (:desde IS NULL OR d.fecha >= :desde) AND d.fecha < :hasta
                UNION ALL
                SELECT DATE(co.fecha), 'cobro', '', co.monto
                FROM cobros_clientes co WHERE (:desde IS NULL OR co.fecha >= :desde) AND co.fecha < :hasta
                UNION ALL
                SELECT g.fecha, IF(g.tipo = 'pago_proveedor', 'pago_proveedor', 'gasto'),
                       SUBSTRING_INDEX(g.concepto, ' · ', 1), g.monto
                FROM gastos_operativos g WHERE (:desde IS NULL OR g.fecha >= :desde) AND g.fecha < :hasta
                UNION ALL
                SELECT l.fecha_entrada, IF(l.condicion_pago = 'contado', 'compra_contado', 'compra_credito'), '', l.total
                FROM lotes_compras l WHERE (:desde IS NULL OR l.fecha_entrada >= :desde) AND l.fecha_entrada < :hasta
            """),
            {"desde": desde, "hasta": hasta},
        ).mappings()
    )
