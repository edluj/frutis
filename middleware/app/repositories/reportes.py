"""Consultas de los reportes (REP-01) y del resumen de inicio (ACC-02). Fechas: [desde, hasta] inclusive."""
from datetime import date

from sqlalchemy import Connection, RowMapping, text

_VENTAS = "FROM ventas_cabecera v WHERE v.estatus <> 'cancelada' AND v.fecha >= :desde AND v.fecha < :hasta + INTERVAL 1 DAY"


def _filas(conn: Connection, sql: str, **params) -> list[RowMapping]:
    return list(conn.execute(text(sql), params).mappings())


def cortes(conn: Connection, desde: date, hasta: date, cajero: str | None) -> list[RowMapping]:
    return _filas(conn, """
        SELECT c.terminal, u.nombre_completo AS cajero, c.fecha_cierre, c.efectivo_esperado, c.efectivo_contado,
               c.diferencia, c.observaciones
        FROM cajas_pos c JOIN usuarios u ON u.id_usuario = c.id_usuario
        WHERE c.estatus = 'cerrada' AND c.fecha_cierre >= :desde AND c.fecha_cierre < :hasta + INTERVAL 1 DAY
          AND (:cajero IS NULL OR u.nombre_completo = :cajero)
        ORDER BY c.fecha_cierre DESC
    """, desde=desde, hasta=hasta, cajero=cajero)


def ventas_por_producto(conn: Connection, desde: date, hasta: date) -> list[RowMapping]:
    return _filas(conn, f"""
        SELECT p.nombre, p.unidad_venta, SUM(d.cantidad) AS cantidad, SUM(d.importe) AS importe
        FROM ventas_detalle d JOIN productos p ON p.id_producto = d.id_producto
        WHERE d.id_venta IN (SELECT v.id_venta {_VENTAS})
        GROUP BY p.id_producto, p.nombre, p.unidad_venta ORDER BY importe DESC
    """, desde=desde, hasta=hasta)


def costos_de_compra(conn: Connection, desde: date, hasta: date) -> list[RowMapping]:
    return _filas(conn, """
        SELECT p.nombre, l.fecha_entrada, i.costo_unitario AS costo
        FROM inventario i JOIN lotes_compras l ON l.id_lote = i.id_lote JOIN productos p ON p.id_producto = i.id_producto
        WHERE l.fecha_entrada BETWEEN :desde AND :hasta
        ORDER BY p.nombre, l.fecha_entrada, i.id_inventario
    """, desde=desde, hasta=hasta)


def ventas_por_metodo(conn: Connection, desde: date, hasta: date) -> list[RowMapping]:
    return _filas(conn, f"""
        SELECT m.nombre AS metodo, COUNT(*) AS tickets, SUM(v.total) AS importe
        FROM (SELECT v.id_metodo, v.total {_VENTAS}) v JOIN metodos_pago m ON m.id_metodo = v.id_metodo
        GROUP BY m.id_metodo, m.nombre ORDER BY importe DESC
    """, desde=desde, hasta=hasta)


def tickets_por_hora(conn: Connection, desde: date, hasta: date) -> list[RowMapping]:
    return _filas(conn, f"SELECT HOUR(v.fecha) AS hora, COUNT(*) AS tickets {_VENTAS} GROUP BY HOUR(v.fecha)",
                  desde=desde, hasta=hasta)


def ventas_por_cajero(conn: Connection, desde: date, hasta: date, cajero: str | None) -> list[RowMapping]:
    return _filas(conn, f"""
        SELECT u.nombre_completo AS cajero, COUNT(*) AS tickets, SUM(v.total) AS importe
        FROM (SELECT v.id_usuario, v.total {_VENTAS}) v JOIN usuarios u ON u.id_usuario = v.id_usuario
        WHERE (:cajero IS NULL OR u.nombre_completo = :cajero)
        GROUP BY u.id_usuario, u.nombre_completo ORDER BY importe DESC
    """, desde=desde, hasta=hasta, cajero=cajero)


def saldos_por_proveedor(conn: Connection, desde: date, hasta: date) -> list[RowMapping]:
    # Pagos = abonos a cuentas por pagar + lotes de contado, que se pagan al recibirlos.
    return _filas(conn, """
        SELECT pr.razon_social,
               COALESCE((SELECT SUM(l.total) FROM lotes_compras l WHERE l.id_proveedor = pr.id_proveedor
                         AND l.fecha_entrada BETWEEN :desde AND :hasta), 0) AS compras,
               COALESCE((SELECT SUM(g.monto) FROM gastos_operativos g JOIN cuentas_por_pagar c ON c.id_cxp = g.id_cxp
                         JOIN lotes_compras l ON l.id_lote = c.id_lote
                         WHERE l.id_proveedor = pr.id_proveedor AND g.fecha BETWEEN :desde AND :hasta), 0)
               + COALESCE((SELECT SUM(l.total) FROM lotes_compras l WHERE l.id_proveedor = pr.id_proveedor
                           AND l.condicion_pago = 'contado' AND l.fecha_entrada BETWEEN :desde AND :hasta), 0) AS pagos,
               COALESCE((SELECT SUM(c.saldo) FROM cuentas_por_pagar c JOIN lotes_compras l ON l.id_lote = c.id_lote
                         WHERE l.id_proveedor = pr.id_proveedor), 0) AS saldo,
               COALESCE((SELECT SUM(c.saldo) FROM cuentas_por_pagar c JOIN lotes_compras l ON l.id_lote = c.id_lote
                         WHERE l.id_proveedor = pr.id_proveedor AND c.fecha_vencimiento < CURDATE()), 0) AS vencido
        FROM proveedores pr ORDER BY pr.razon_social
    """, desde=desde, hasta=hasta)


def costo_mermas(conn: Connection, desde: date, hasta: date):
    return conn.execute(text("""
        SELECT COALESCE(SUM(costo_total), 0) FROM mermas WHERE fecha >= :desde AND fecha < :hasta + INTERVAL 1 DAY
    """), {"desde": desde, "hasta": hasta}).scalar_one()


def cajeros(conn: Connection) -> list[str]:
    """Usuarios activos que pueden cobrar, más quien ya cobró aunque hoy esté inactivo."""
    return list(conn.execute(text("""
        SELECT DISTINCT u.nombre_completo FROM usuarios u
        LEFT JOIN permisos p ON p.id_rol = u.id_rol AND p.modulo = 'pos' AND p.puede_crear = TRUE
        WHERE (p.id_permiso IS NOT NULL AND u.activo = TRUE)
           OR EXISTS (SELECT 1 FROM ventas_cabecera v WHERE v.id_usuario = u.id_usuario)
        ORDER BY u.nombre_completo
    """)).scalars())


def ventas_de_hoy(conn: Connection, id_usuario: int | None) -> RowMapping:
    return conn.execute(text("""
        SELECT COUNT(*) AS tickets, COALESCE(SUM(total), 0) AS importe FROM ventas_cabecera
        WHERE estatus <> 'cancelada' AND fecha >= CURDATE() AND (:usuario IS NULL OR id_usuario = :usuario)
    """), {"usuario": id_usuario}).mappings().one()
