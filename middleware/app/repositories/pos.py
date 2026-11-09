"""Consultas del punto de venta y llamada a sp_registrar_venta."""
import json
from decimal import Decimal

from sqlalchemy import Connection, RowMapping, text


def buscar_productos(
    conn: Connection, codigo: str | None, busqueda: str | None, frecuentes: bool
) -> list[RowMapping]:
    return list(
        conn.execute(
            text("""
                SELECT p.id_producto, p.codigo_barras, p.nombre, p.unidad_venta, p.precio_venta,
                       p.tasa_iva, p.es_frecuente, e.existencia
                FROM productos p JOIN v_existencias e ON e.id_producto = p.id_producto
                WHERE p.activo = TRUE
                  AND (:codigo IS NULL OR p.codigo_barras = :codigo)
                  AND (:busqueda IS NULL OR p.nombre LIKE CONCAT('%', :busqueda, '%'))
                  AND (:frecuentes = FALSE OR p.es_frecuente = TRUE)
                ORDER BY p.nombre
                LIMIT 50
            """),
            {"codigo": codigo, "busqueda": busqueda, "frecuentes": frecuentes},
        ).mappings()
    )


def metodos_pago(conn: Connection) -> list[RowMapping]:
    return list(
        conn.execute(
            text("""
                SELECT id_metodo, nombre, es_efectivo, es_credito
                FROM metodos_pago WHERE activo = TRUE ORDER BY id_metodo
            """)
        ).mappings()
    )


def caja_abierta_de(conn: Connection, id_usuario: int) -> RowMapping | None:
    return conn.execute(
        text("""
            SELECT id_caja, terminal, fondo_inicial, fecha_apertura
            FROM cajas_pos
            WHERE id_usuario = :id AND estatus = 'abierta'
            ORDER BY fecha_apertura DESC
            LIMIT 1
        """),
        {"id": id_usuario},
    ).mappings().first()


def caja_es_de_usuario(conn: Connection, id_caja: int, id_usuario: int) -> bool:
    return (
        conn.execute(
            text("SELECT 1 FROM cajas_pos WHERE id_caja = :caja AND id_usuario = :usuario"),
            {"caja": id_caja, "usuario": id_usuario},
        ).first()
        is not None
    )


def registrar_venta(
    conn: Connection,
    id_caja: int,
    id_usuario: int,
    id_metodo: int,
    monto_recibido: Decimal,
    id_cliente_credito: int | None,
    carrito: list[dict],
) -> RowMapping:
    # Los OUT viven en variables de sesión: se leen en la misma conexión.
    conn.execute(
        text("""
            CALL sp_registrar_venta(:caja, :usuario, :metodo, :monto, :cliente, :carrito,
                                    @id_venta, @folio, @total, @cambio)
        """),
        {
            "caja": id_caja,
            "usuario": id_usuario,
            "metodo": id_metodo,
            "monto": monto_recibido,
            "cliente": id_cliente_credito,
            "carrito": json.dumps(carrito),
        },
    )
    return conn.execute(
        text("SELECT @id_venta AS id_venta, @folio AS folio, @total AS total, @cambio AS cambio")
    ).mappings().one()
