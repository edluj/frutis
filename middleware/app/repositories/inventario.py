"""Consultas del catálogo: categorías y productos (flujos O y P)."""
from datetime import date
from decimal import Decimal

from sqlalchemy import Connection, RowMapping, text


def listar_categorias(conn: Connection, busqueda: str | None, solo_activas: bool) -> list[RowMapping]:
    return list(
        conn.execute(
            text("""
                SELECT c.id_categoria, c.nombre, c.descripcion, c.activo,
                       COUNT(p.id_producto) AS productos_activos
                FROM categorias c
                LEFT JOIN productos p ON p.id_categoria = c.id_categoria AND p.activo = TRUE
                WHERE (:busqueda IS NULL OR c.nombre LIKE CONCAT('%', :busqueda, '%'))
                  AND (:solo_activas = FALSE OR c.activo = TRUE)
                GROUP BY c.id_categoria, c.nombre, c.descripcion, c.activo
                ORDER BY c.nombre
            """),
            {"busqueda": busqueda, "solo_activas": solo_activas},
        ).mappings()
    )


def categoria(conn: Connection, id_categoria: int, bloquear: bool = False) -> RowMapping | None:
    # FOR UPDATE: la baja revisa los productos activos sin que otro los cambie a la vez.
    return conn.execute(
        text(f"""
            SELECT id_categoria, nombre, activo FROM categorias WHERE id_categoria = :id
            {"FOR UPDATE" if bloquear else ""}
        """),
        {"id": id_categoria},
    ).mappings().first()


def nombre_categoria_en_uso(conn: Connection, nombre: str, excepto: int | None) -> bool:
    return conn.execute(
        text("SELECT 1 FROM categorias WHERE nombre = :nombre AND id_categoria <> COALESCE(:excepto, 0)"),
        {"nombre": nombre, "excepto": excepto},
    ).first() is not None


def productos_activos_de(conn: Connection, id_categoria: int) -> int:
    return conn.execute(
        text("SELECT COUNT(*) FROM productos WHERE id_categoria = :id AND activo = TRUE"),
        {"id": id_categoria},
    ).scalar_one()


def insertar_categoria(conn: Connection, nombre: str, descripcion: str | None, activo: bool) -> int:
    return conn.execute(
        text("INSERT INTO categorias (nombre, descripcion, activo) VALUES (:nombre, :descripcion, :activo)"),
        {"nombre": nombre, "descripcion": descripcion, "activo": activo},
    ).lastrowid


def actualizar_categoria(conn: Connection, id_categoria: int, nombre: str, descripcion: str | None, activo: bool) -> None:
    conn.execute(
        text("""
            UPDATE categorias SET nombre = :nombre, descripcion = :descripcion, activo = :activo
            WHERE id_categoria = :id
        """),
        {"id": id_categoria, "nombre": nombre, "descripcion": descripcion, "activo": activo},
    )


# Existencia y próxima caducidad por lotes, también para productos dados de baja
# (v_existencias solo trae los activos).
_PRODUCTOS = """
    SELECT p.id_producto, p.codigo_barras, p.nombre, p.id_categoria, c.nombre AS categoria,
           p.unidad_venta, p.precio_venta, p.costo_actual, p.tasa_iva, p.stock_minimo,
           p.es_frecuente, p.activo,
           COALESCE(i.existencia, 0) AS existencia,
           CASE
             WHEN COALESCE(i.existencia, 0) <= 0 THEN 'Sin existencia'
             WHEN i.existencia < p.stock_minimo THEN 'Bajo'
             WHEN i.proxima_caducidad <= CURDATE() + INTERVAL 1 DAY THEN 'Por caducar'
             ELSE 'Normal'
           END AS estado
    FROM productos p
    JOIN categorias c ON c.id_categoria = p.id_categoria
    LEFT JOIN (
        SELECT id_producto, SUM(cantidad_disponible) AS existencia,
               MIN(CASE WHEN cantidad_disponible > 0 THEN fecha_caducidad END) AS proxima_caducidad
        FROM inventario GROUP BY id_producto
    ) i ON i.id_producto = p.id_producto
"""


def listar_productos(conn: Connection, busqueda: str | None, id_categoria: int | None) -> list[RowMapping]:
    return list(
        conn.execute(
            text(_PRODUCTOS + """
                WHERE (:busqueda IS NULL OR p.nombre LIKE CONCAT('%', :busqueda, '%')
                       OR p.codigo_barras = :busqueda)
                  AND (:categoria IS NULL OR p.id_categoria = :categoria)
                ORDER BY p.activo DESC, p.nombre
            """),
            {"busqueda": busqueda, "categoria": id_categoria},
        ).mappings()
    )


def producto(conn: Connection, id_producto: int, bloquear: bool = False) -> RowMapping | None:
    sql = "SELECT id_producto, precio_venta FROM productos WHERE id_producto = :id"
    return conn.execute(text(sql + (" FOR UPDATE" if bloquear else "")), {"id": id_producto}).mappings().first()


def producto_catalogo(conn: Connection, id_producto: int) -> RowMapping:
    return conn.execute(text(_PRODUCTOS + " WHERE p.id_producto = :id"), {"id": id_producto}).mappings().one()


def codigo_en_uso(conn: Connection, codigo: str, excepto: int | None) -> bool:
    return conn.execute(
        text("SELECT 1 FROM productos WHERE codigo_barras = :codigo AND id_producto <> COALESCE(:excepto, 0)"),
        {"codigo": codigo, "excepto": excepto},
    ).first() is not None


_CAMPOS_PRODUCTO = ("codigo_barras", "nombre", "id_categoria", "unidad_venta", "precio_venta",
                    "stock_minimo", "tasa_iva", "es_frecuente", "activo")


def insertar_producto(conn: Connection, datos: dict) -> int:
    return conn.execute(
        text(f"""
            INSERT INTO productos ({", ".join(_CAMPOS_PRODUCTO)})
            VALUES ({", ".join(":" + c for c in _CAMPOS_PRODUCTO)})
        """),
        {c: datos[c] for c in _CAMPOS_PRODUCTO},
    ).lastrowid


def actualizar_producto(conn: Connection, id_producto: int, datos: dict) -> None:
    conn.execute(
        text(f"""
            UPDATE productos SET {", ".join(f"{c} = :{c}" for c in _CAMPOS_PRODUCTO)}
            WHERE id_producto = :id
        """),
        {"id": id_producto, **{c: datos[c] for c in _CAMPOS_PRODUCTO}},
    )


def registrar_cambio_precio(
    conn: Connection, id_producto: int, anterior: Decimal, nuevo: Decimal, id_usuario: int, motivo: str
) -> None:
    conn.execute(
        text("""
            INSERT INTO historial_precios (id_producto, precio_anterior, precio_nuevo, id_usuario, motivo)
            VALUES (:producto, :anterior, :nuevo, :usuario, :motivo)
        """),
        {"producto": id_producto, "anterior": anterior, "nuevo": nuevo, "usuario": id_usuario, "motivo": motivo},
    )


# ---------------------------------------------------------------- mermas (HU-17)

def lotes_con_existencia(conn: Connection, id_producto: int) -> list[RowMapping]:
    """Lotes del producto que todavía tienen existencia, primero el que caduca antes (FEFO)."""
    return list(
        conn.execute(
            text("""
                SELECT l.folio, i.cantidad_disponible AS queda, i.fecha_caducidad AS caducidad,
                       i.costo_unitario AS costo
                FROM inventario i JOIN lotes_compras l ON l.id_lote = i.id_lote
                WHERE i.id_producto = :producto AND i.cantidad_disponible > 0
                ORDER BY i.fecha_caducidad, i.id_inventario
            """),
            {"producto": id_producto},
        ).mappings()
    )


def existencia_de_lote(conn: Connection, id_producto: int, folio: str) -> RowMapping | None:
    # FOR UPDATE: una venta o una devolución no pueden mover la misma fila a la vez.
    return conn.execute(
        text("""
            SELECT i.id_inventario, i.cantidad_disponible, i.costo_unitario, p.nombre, p.unidad_venta
            FROM inventario i
            JOIN lotes_compras l ON l.id_lote = i.id_lote
            JOIN productos p ON p.id_producto = i.id_producto
            WHERE i.id_producto = :producto AND l.folio = :folio
            FOR UPDATE
        """),
        {"producto": id_producto, "folio": folio},
    ).mappings().first()


def registrar_merma(
    conn: Connection, id_inventario: int, cantidad: Decimal, motivo: str, costo: Decimal,
    observaciones: str | None, id_usuario: int,
) -> None:
    conn.execute(
        text("UPDATE inventario SET cantidad_disponible = cantidad_disponible - :cantidad WHERE id_inventario = :id"),
        {"cantidad": cantidad, "id": id_inventario},
    )
    conn.execute(
        text("""
            INSERT INTO mermas (id_inventario, cantidad, motivo, costo_total, observaciones, id_usuario)
            VALUES (:inventario, :cantidad, :motivo, :costo, :observaciones, :usuario)
        """),
        {"inventario": id_inventario, "cantidad": cantidad, "motivo": motivo, "costo": costo,
         "observaciones": observaciones, "usuario": id_usuario},
    )


def listar_mermas(conn: Connection, motivo: str | None, desde: date | None, hasta: date | None) -> list[RowMapping]:
    return list(
        conn.execute(
            text("""
                SELECT DATE(m.fecha) AS fecha, p.id_producto, p.nombre AS producto, p.unidad_venta, l.folio AS lote,
                       m.cantidad, m.motivo, m.costo_total AS costo, u.usuario, m.observaciones
                FROM mermas m
                JOIN inventario i ON i.id_inventario = m.id_inventario
                JOIN lotes_compras l ON l.id_lote = i.id_lote
                JOIN productos p ON p.id_producto = i.id_producto
                JOIN usuarios u ON u.id_usuario = m.id_usuario
                WHERE (:motivo IS NULL OR m.motivo = :motivo)
                  AND (:desde IS NULL OR m.fecha >= :desde)
                  AND (:hasta IS NULL OR m.fecha < :hasta + INTERVAL 1 DAY)
                ORDER BY m.fecha DESC, m.id_merma DESC
                LIMIT 500
            """),
            {"motivo": motivo, "desde": desde, "hasta": hasta},
        ).mappings()
    )


# ---------------------------------------------------------------- existencias y caducidades (HU-24)

def existencias(conn: Connection) -> list[RowMapping]:
    return list(
        conn.execute(
            text("""
                SELECT p.id_producto, p.id_categoria, p.nombre, p.unidad_venta, p.stock_minimo,
                       COALESCE(i.existencia, 0) AS existencia, COALESCE(i.lotes, 0) AS lotes,
                       COALESCE(i.valor, 0) AS valor, ROUND(COALESCE(v.vendido, 0) / 30, 3) AS venta_diaria
                FROM productos p
                LEFT JOIN (
                    SELECT id_producto, SUM(cantidad_disponible) AS existencia,
                           SUM(cantidad_disponible > 0) AS lotes,
                           SUM(ROUND(cantidad_disponible * costo_unitario, 2)) AS valor
                    FROM inventario GROUP BY id_producto
                ) i ON i.id_producto = p.id_producto
                LEFT JOIN (
                    SELECT d.id_producto, SUM(d.cantidad) AS vendido
                    FROM ventas_detalle d JOIN ventas_cabecera c ON c.id_venta = d.id_venta
                    WHERE c.fecha >= CURDATE() - INTERVAL 30 DAY
                    GROUP BY d.id_producto
                ) v ON v.id_producto = p.id_producto
                WHERE p.activo = TRUE
                ORDER BY p.nombre
            """)
        ).mappings()
    )


def lotes_por_caducar(conn: Connection, dias: int, id_producto: int | None, id_proveedor: int | None) -> list[RowMapping]:
    return list(
        conn.execute(
            text("""
                SELECT i.fecha_caducidad AS caducidad, DATEDIFF(i.fecha_caducidad, CURDATE()) AS dias,
                       p.id_producto, p.nombre AS producto, p.unidad_venta, l.folio AS lote,
                       pr.razon_social AS proveedor, i.cantidad_inicial AS recibido, i.cantidad_disponible AS queda,
                       ROUND(i.cantidad_disponible * i.costo_unitario, 2) AS costo
                FROM inventario i
                JOIN productos p ON p.id_producto = i.id_producto
                JOIN lotes_compras l ON l.id_lote = i.id_lote
                JOIN proveedores pr ON pr.id_proveedor = l.id_proveedor
                WHERE i.cantidad_disponible > 0
                  AND i.fecha_caducidad <= CURDATE() + INTERVAL :dias DAY
                  AND (:producto IS NULL OR i.id_producto = :producto)
                  AND (:proveedor IS NULL OR l.id_proveedor = :proveedor)
                ORDER BY i.fecha_caducidad, l.folio
            """),
            {"dias": dias, "producto": id_producto, "proveedor": id_proveedor},
        ).mappings()
    )


def movimientos(conn: Connection, id_producto: int) -> list[RowMapping]:
    """Toda la historia del producto: la pantalla calcula la existencia después de cada movimiento."""
    return list(
        conn.execute(
            text("""
                SELECT l.fecha_entrada AS fecha, 'Entrada' AS tipo, i.cantidad_inicial AS cantidad,
                       CONCAT('Lote ', l.folio, ' · ', pr.razon_social) AS referencia, u.usuario, 0 AS orden
                FROM inventario i
                JOIN lotes_compras l ON l.id_lote = i.id_lote
                JOIN proveedores pr ON pr.id_proveedor = l.id_proveedor
                JOIN usuarios u ON u.id_usuario = l.id_usuario
                WHERE i.id_producto = :producto
                UNION ALL
                SELECT DATE(m.fecha), 'Merma', -m.cantidad,
                       CONCAT(CASE m.motivo WHEN 'maduracion' THEN 'Maduración' WHEN 'golpe' THEN 'Golpe'
                                            WHEN 'plaga' THEN 'Plaga u hongo' WHEN 'caducidad' THEN 'Caducidad'
                                            WHEN 'devolucion' THEN 'Devolución en mal estado' ELSE 'Otro' END,
                              ' · lote ', l.folio), u.usuario, 1
                FROM mermas m
                JOIN inventario i ON i.id_inventario = m.id_inventario
                JOIN lotes_compras l ON l.id_lote = i.id_lote
                JOIN usuarios u ON u.id_usuario = m.id_usuario
                WHERE i.id_producto = :producto
                UNION ALL
                SELECT DATE(dv.fecha), 'Devolución', dv.cantidad,
                       CONCAT('Devolución ', dv.folio, ' · ticket ', v.folio), u.usuario, 2
                FROM devoluciones dv
                JOIN ventas_detalle d ON d.id_detalle = dv.id_detalle
                JOIN ventas_cabecera v ON v.id_venta = dv.id_venta
                JOIN usuarios u ON u.id_usuario = dv.id_usuario
                WHERE d.id_producto = :producto AND dv.estado_producto = 'bueno'
                UNION ALL
                SELECT DATE(v.fecha), 'Venta', -SUM(d.cantidad),
                       CONCAT(COUNT(DISTINCT v.id_venta), ' tickets'), c.terminal, 3
                FROM ventas_detalle d
                JOIN ventas_cabecera v ON v.id_venta = d.id_venta
                JOIN cajas_pos c ON c.id_caja = v.id_caja
                WHERE d.id_producto = :producto
                GROUP BY DATE(v.fecha), c.terminal
                ORDER BY fecha DESC, orden DESC
            """),
            {"producto": id_producto},
        ).mappings()
    )


# ---------------------------------------------------------------- precios (HU-31)

def precios_para_ajuste(conn: Connection, ids: list[int]) -> dict[int, RowMapping]:
    marcadores = ", ".join(f":p{i}" for i in range(len(ids)))
    filas = conn.execute(
        text(f"SELECT id_producto, nombre, precio_venta, activo FROM productos WHERE id_producto IN ({marcadores}) FOR UPDATE"),
        {f"p{i}": v for i, v in enumerate(ids)},
    ).mappings()
    return {f["id_producto"]: f for f in filas}


def cambiar_precio(conn: Connection, id_producto: int, precio: Decimal) -> None:
    conn.execute(text("UPDATE productos SET precio_venta = :precio WHERE id_producto = :id"),
                 {"precio": precio, "id": id_producto})


def historial_precios(conn: Connection, id_producto: int) -> list[RowMapping]:
    return list(
        conn.execute(
            text("""
                SELECT h.fecha, h.precio_anterior AS anterior, h.precio_nuevo AS nuevo, u.usuario, h.motivo
                FROM historial_precios h JOIN usuarios u ON u.id_usuario = h.id_usuario
                WHERE h.id_producto = :producto
                ORDER BY h.fecha DESC, h.id_historial DESC
            """),
            {"producto": id_producto},
        ).mappings()
    )
