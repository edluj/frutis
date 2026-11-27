"""Consultas del catálogo: categorías y productos (flujos O y P)."""
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
