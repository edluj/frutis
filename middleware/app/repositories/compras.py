"""Consultas de proveedores (flujo F) y lotes de compra (flujo G)."""
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Connection, RowMapping, text

# Saldo por pagar de cada proveedor: suma de sus cuentas pendientes.
_PROVEEDORES = """
    SELECT pr.id_proveedor, pr.razon_social, pr.rfc, pr.telefono, pr.correo, pr.direccion,
           pr.dias_credito, pr.activo, COALESCE(s.saldo, 0) AS saldo
    FROM proveedores pr
    LEFT JOIN (
        SELECT l.id_proveedor, SUM(c.saldo) AS saldo
        FROM cuentas_por_pagar c JOIN lotes_compras l ON l.id_lote = c.id_lote
        WHERE c.estatus = 'pendiente'
        GROUP BY l.id_proveedor
    ) s ON s.id_proveedor = pr.id_proveedor
"""


def listar_proveedores(conn: Connection, busqueda: str | None, activo: bool | None) -> list[RowMapping]:
    return list(
        conn.execute(
            text(_PROVEEDORES + """
                WHERE (:busqueda IS NULL OR pr.razon_social LIKE CONCAT('%', :busqueda, '%') OR pr.rfc = UPPER(:busqueda))
                  AND (:activo IS NULL OR pr.activo = :activo)
                ORDER BY pr.razon_social
            """),
            {"busqueda": busqueda, "activo": activo},
        ).mappings()
    )


def proveedor(conn: Connection, id_proveedor: int, bloquear: bool = False) -> RowMapping | None:
    return conn.execute(
        text(_PROVEEDORES + " WHERE pr.id_proveedor = :id" + (" FOR UPDATE" if bloquear else "")),
        {"id": id_proveedor},
    ).mappings().first()


def rfc_en_uso(conn: Connection, rfc: str, excepto: int | None) -> bool:
    return conn.execute(
        text("SELECT 1 FROM proveedores WHERE rfc = :rfc AND id_proveedor <> COALESCE(:excepto, 0)"),
        {"rfc": rfc, "excepto": excepto},
    ).first() is not None


_CAMPOS_PROVEEDOR = ("razon_social", "rfc", "telefono", "correo", "direccion", "dias_credito", "activo")


def insertar_proveedor(conn: Connection, datos: dict) -> int:
    return conn.execute(
        text(f"""
            INSERT INTO proveedores ({", ".join(_CAMPOS_PROVEEDOR)})
            VALUES ({", ".join(":" + c for c in _CAMPOS_PROVEEDOR)})
        """),
        {c: datos[c] for c in _CAMPOS_PROVEEDOR},
    ).lastrowid


def actualizar_proveedor(conn: Connection, id_proveedor: int, datos: dict) -> None:
    conn.execute(
        text(f"UPDATE proveedores SET {', '.join(f'{c} = :{c}' for c in _CAMPOS_PROVEEDOR)} WHERE id_proveedor = :id"),
        {"id": id_proveedor, **{c: datos[c] for c in _CAMPOS_PROVEEDOR}},
    )


# ---------------------------------------------------------------- lotes

def siguiente_folio(conn: Connection) -> str:
    """Vista previa: el folio definitivo se asigna al guardar (puede cambiar si otro registra antes)."""
    siguiente = conn.execute(text("SELECT COALESCE(MAX(id_lote), 0) + 1 FROM lotes_compras")).scalar_one()
    return f"L-{siguiente:08d}"


def productos_para_lote(conn: Connection, ids: list[int]) -> dict[int, RowMapping]:
    marcadores = ", ".join(f":p{i}" for i in range(len(ids)))
    filas = conn.execute(
        text(f"SELECT id_producto, nombre, unidad_venta, activo FROM productos WHERE id_producto IN ({marcadores})"),
        {f"p{i}": v for i, v in enumerate(ids)},
    ).mappings()
    return {f["id_producto"]: f for f in filas}


def insertar_lote(
    conn: Connection, id_proveedor: int, id_usuario: int, entrada: date, credito: bool,
    total: Decimal, factura: str | None,
) -> tuple[int, str]:
    # El folio sale del id: se inserta con uno temporal único y se corrige en la misma transacción.
    temporal = "T" + uuid.uuid4().hex[:16]
    id_lote = conn.execute(
        text("""
            INSERT INTO lotes_compras (folio, id_proveedor, id_usuario, fecha_entrada, condicion_pago, total, factura_proveedor)
            VALUES (:folio, :proveedor, :usuario, :entrada, :condicion, :total, :factura)
        """),
        {"folio": temporal, "proveedor": id_proveedor, "usuario": id_usuario, "entrada": entrada,
         "condicion": "credito" if credito else "contado", "total": total, "factura": factura},
    ).lastrowid
    folio = f"L-{id_lote:08d}"
    conn.execute(text("UPDATE lotes_compras SET folio = :folio WHERE id_lote = :id"), {"folio": folio, "id": id_lote})
    return id_lote, folio


def insertar_existencia(conn: Connection, id_lote: int, id_producto: int, cantidad: Decimal, costo: Decimal,
                        caducidad: date) -> None:
    conn.execute(
        text("""
            INSERT INTO inventario (id_lote, id_producto, cantidad_inicial, cantidad_disponible, costo_unitario, fecha_caducidad)
            VALUES (:lote, :producto, :cantidad, :cantidad, :costo, :caducidad)
        """),
        {"lote": id_lote, "producto": id_producto, "cantidad": cantidad, "costo": costo, "caducidad": caducidad},
    )


def actualizar_costo(conn: Connection, id_producto: int, costo: Decimal) -> None:
    conn.execute(text("UPDATE productos SET costo_actual = :costo WHERE id_producto = :id"),
                 {"costo": costo, "id": id_producto})


def insertar_cuenta_por_pagar(conn: Connection, id_lote: int, total: Decimal, vence: date) -> None:
    conn.execute(
        text("""
            INSERT INTO cuentas_por_pagar (id_lote, monto_total, saldo, fecha_vencimiento)
            VALUES (:lote, :total, :total, :vence)
        """),
        {"lote": id_lote, "total": total, "vence": vence},
    )


_ESTADO_PAGO = """
    CASE WHEN c.id_cxp IS NULL OR c.estatus = 'pagada' THEN 'Pagado'
         WHEN c.fecha_vencimiento < CURDATE() THEN 'Vencido'
         ELSE 'Pendiente' END
"""


def listar_lotes(conn: Connection, id_proveedor: int | None, desde: date | None, hasta: date | None) -> list[RowMapping]:
    return list(
        conn.execute(
            text(f"""
                SELECT l.folio, l.id_proveedor, pr.razon_social AS proveedor, l.fecha_entrada AS entrada,
                       COUNT(i.id_inventario) AS productos, l.total,
                       COALESCE(SUM(CASE WHEN p.unidad_venta = 'kg' THEN i.cantidad_inicial END), 0) AS kilos,
                       COALESCE(DATEDIFF(c.fecha_vencimiento, l.fecha_entrada), 0) AS dias_credito,
                       {_ESTADO_PAGO} AS pago, COALESCE(c.saldo, 0) AS saldo,
                       MIN(i.fecha_caducidad) AS caducidad
                FROM lotes_compras l
                JOIN proveedores pr ON pr.id_proveedor = l.id_proveedor
                JOIN inventario i ON i.id_lote = l.id_lote
                JOIN productos p ON p.id_producto = i.id_producto
                LEFT JOIN cuentas_por_pagar c ON c.id_lote = l.id_lote
                WHERE (:proveedor IS NULL OR l.id_proveedor = :proveedor)
                  AND (:desde IS NULL OR l.fecha_entrada >= :desde)
                  AND (:hasta IS NULL OR l.fecha_entrada <= :hasta)
                GROUP BY l.id_lote, l.folio, l.id_proveedor, pr.razon_social, l.fecha_entrada, l.total,
                         c.id_cxp, c.estatus, c.fecha_vencimiento, c.saldo
                ORDER BY l.id_lote DESC
            """),
            {"proveedor": id_proveedor, "desde": desde, "hasta": hasta},
        ).mappings()
    )


def lote(conn: Connection, folio: str) -> RowMapping | None:
    return conn.execute(
        text(f"""
            SELECT l.id_lote, l.folio, pr.razon_social AS proveedor, l.fecha_entrada AS entrada,
                   l.factura_proveedor AS factura, l.total,
                   COALESCE(DATEDIFF(c.fecha_vencimiento, l.fecha_entrada), 0) AS dias_credito,
                   c.fecha_vencimiento AS vence,
                   COALESCE(c.monto_total - c.saldo, l.total) AS pagado, COALESCE(c.saldo, 0) AS saldo,
                   {_ESTADO_PAGO} AS pago
            FROM lotes_compras l
            JOIN proveedores pr ON pr.id_proveedor = l.id_proveedor
            LEFT JOIN cuentas_por_pagar c ON c.id_lote = l.id_lote
            WHERE l.folio = :folio
        """),
        {"folio": folio},
    ).mappings().first()


def renglones_de_lote(conn: Connection, id_lote: int) -> list[RowMapping]:
    # Lo vendido es lo que salió del lote sin contar mermas: recibido = vendido + merma + existencia.
    return list(
        conn.execute(
            text("""
                SELECT p.id_producto, p.nombre, p.unidad_venta, i.cantidad_inicial AS recibido,
                       i.costo_unitario AS costo, COALESCE(m.merma, 0) AS merma, i.cantidad_disponible AS existencia,
                       GREATEST(i.cantidad_inicial - i.cantidad_disponible - COALESCE(m.merma, 0), 0) AS vendido,
                       i.fecha_caducidad AS caducidad, DATEDIFF(i.fecha_caducidad, CURDATE()) AS dias
                FROM inventario i
                JOIN productos p ON p.id_producto = i.id_producto
                LEFT JOIN (SELECT id_inventario, SUM(cantidad) AS merma FROM mermas GROUP BY id_inventario) m
                       ON m.id_inventario = i.id_inventario
                WHERE i.id_lote = :lote
                ORDER BY p.nombre
            """),
            {"lote": id_lote},
        ).mappings()
    )


def mermas_de_lote(conn: Connection, id_lote: int) -> list[RowMapping]:
    return list(
        conn.execute(
            text("""
                SELECT DATE(m.fecha) AS fecha, p.nombre AS producto, m.cantidad, m.motivo, m.costo_total AS costo
                FROM mermas m
                JOIN inventario i ON i.id_inventario = m.id_inventario
                JOIN productos p ON p.id_producto = i.id_producto
                WHERE i.id_lote = :lote
                ORDER BY m.fecha
            """),
            {"lote": id_lote},
        ).mappings()
    )
