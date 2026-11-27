"""Consultas del punto de venta y llamadas a sus procedimientos (venta, apertura, corte y devolución)."""
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


# ---------------------------------------------------------------- apertura y corte (HU-15, HU-09)

def abrir_caja(conn: Connection, terminal: str, id_usuario: int, fondo: Decimal) -> RowMapping:
    conn.execute(
        text("CALL sp_abrir_caja(:terminal, :usuario, :fondo, @id_caja)"),
        {"terminal": terminal, "usuario": id_usuario, "fondo": fondo},
    )
    return conn.execute(
        text("""
            SELECT id_caja, terminal, fondo_inicial, fecha_apertura
            FROM cajas_pos WHERE id_caja = @id_caja
        """)
    ).mappings().one()


def ultimo_corte(conn: Connection, terminal: str) -> RowMapping | None:
    return conn.execute(
        text("""
            SELECT c.id_caja, c.terminal, u.nombre_completo AS cajero, c.fecha_cierre,
                   c.efectivo_esperado, c.efectivo_contado, c.diferencia, c.observaciones
            FROM cajas_pos c JOIN usuarios u ON u.id_usuario = c.id_usuario
            WHERE c.terminal = :terminal AND c.estatus = 'cerrada'
            ORDER BY c.fecha_cierre DESC, c.id_caja DESC
            LIMIT 1
        """),
        {"terminal": terminal},
    ).mappings().first()


def resumen_corte(conn: Connection, id_caja: int) -> dict:
    """Lo que entró y salió del turno; el esperado sale de fn_efectivo_esperado, igual que en el cierre."""
    parametros = {"caja": id_caja}
    ventas = conn.execute(
        text("""
            SELECT m.nombre AS metodo, m.es_efectivo, m.es_credito,
                   COUNT(v.id_venta) AS tickets, COALESCE(SUM(v.total), 0) AS importe
            FROM metodos_pago m
            LEFT JOIN ventas_cabecera v
              ON v.id_metodo = m.id_metodo AND v.id_caja = :caja AND v.estatus <> 'cancelada'
            GROUP BY m.id_metodo, m.nombre, m.es_efectivo, m.es_credito, m.activo
            HAVING m.activo = TRUE OR COUNT(v.id_venta) > 0
            ORDER BY m.id_metodo
        """),
        parametros,
    ).mappings().all()
    cobros = conn.execute(
        text("""
            SELECT COUNT(*) AS cantidad, COALESCE(SUM(c.monto), 0) AS importe
            FROM cobros_clientes c JOIN metodos_pago m ON m.id_metodo = c.id_metodo
            WHERE c.id_caja = :caja AND m.es_efectivo = TRUE
        """),
        parametros,
    ).mappings().one()
    devoluciones = conn.execute(
        text("""
            SELECT COUNT(DISTINCT folio) AS cantidad, COALESCE(SUM(importe), 0) AS importe
            FROM devoluciones
            WHERE id_caja = :caja AND reembolso = 'efectivo'
        """),
        parametros,
    ).mappings().one()
    esperado = conn.execute(text("SELECT fn_efectivo_esperado(:caja)"), parametros).scalar_one()
    return {
        "ventas": list(ventas),
        "cobros_efectivo": cobros,
        "devoluciones_efectivo": devoluciones,
        "efectivo_esperado": esperado,
    }


def cerrar_caja(
    conn: Connection, id_caja: int, id_usuario: int, contado: Decimal, observaciones: str | None
) -> RowMapping:
    conn.execute(
        text("CALL sp_cerrar_caja(:caja, :usuario, :contado, :observaciones, @esperado, @diferencia)"),
        {"caja": id_caja, "usuario": id_usuario, "contado": contado, "observaciones": observaciones},
    )
    return conn.execute(
        text("SELECT @esperado AS efectivo_esperado, @diferencia AS diferencia")
    ).mappings().one()


# ---------------------------------------------------------------- ticket y devoluciones (HU-30)

def ticket(conn: Connection, folio: str) -> dict | None:
    cabecera = conn.execute(
        text("""
            SELECT v.id_venta, v.folio, v.fecha, v.total, v.estatus, m.nombre AS metodo, m.es_credito,
                   EXISTS (SELECT 1 FROM facturas_cfdi f
                           WHERE f.id_venta = v.id_venta AND f.estatus = 'timbrada') AS facturado,
                   cc.nombre AS cliente
            FROM ventas_cabecera v
            JOIN metodos_pago m ON m.id_metodo = v.id_metodo
            LEFT JOIN cuentas_por_cobrar x ON x.id_venta = v.id_venta
            LEFT JOIN clientes_credito cc ON cc.id_cliente_credito = x.id_cliente_credito
            WHERE v.folio = :folio
        """),
        {"folio": folio},
    ).mappings().first()
    if cabecera is None:
        return None
    # Una venta guarda un renglón por lote; aquí se agrupan por producto.
    renglones = conn.execute(
        text("""
            SELECT d.id_producto, p.nombre, p.unidad_venta, SUM(d.cantidad) AS cantidad,
                   MAX(d.precio_unitario) AS precio_unitario, SUM(d.importe) AS importe,
                   COALESCE(SUM(x.devuelto), 0) AS devuelto
            FROM ventas_detalle d
            JOIN productos p ON p.id_producto = d.id_producto
            LEFT JOIN (
              SELECT id_detalle, SUM(cantidad) AS devuelto
              FROM devoluciones WHERE id_venta = :venta GROUP BY id_detalle
            ) x ON x.id_detalle = d.id_detalle
            WHERE d.id_venta = :venta
            GROUP BY d.id_producto, p.nombre, p.unidad_venta
            ORDER BY MIN(d.id_detalle)
        """),
        {"venta": cabecera["id_venta"]},
    ).mappings().all()
    return {**cabecera, "renglones": list(renglones)}


def registrar_devolucion(
    conn: Connection,
    folio_venta: str,
    id_caja: int,
    id_usuario: int,
    id_autoriza: int,
    motivo: str,
    reembolso: str,
    renglones: list[dict],
) -> RowMapping:
    conn.execute(
        text("""
            CALL sp_registrar_devolucion(:folio, :caja, :usuario, :autoriza, :motivo, :reembolso, :renglones,
                                         @folio_devolucion, @total_devolucion)
        """),
        {
            "folio": folio_venta,
            "caja": id_caja,
            "usuario": id_usuario,
            "autoriza": id_autoriza,
            "motivo": motivo,
            "reembolso": reembolso,
            "renglones": json.dumps(renglones),
        },
    )
    return conn.execute(
        text("SELECT @folio_devolucion AS folio, @total_devolucion AS total")
    ).mappings().one()
