"""Consultas de datos fiscales de clientes (flujo K) y facturas CFDI (flujos I y J)."""
from datetime import date, datetime

from sqlalchemy import Connection, RowMapping, text

# Las facturas anteriores a esta versión no tienen folio: se muestra el que les corresponde.
FOLIO = "COALESCE(f.folio, CONCAT('F-', LPAD(f.id_factura, 6, '0')))"
ESTATUS = "CASE f.estatus WHEN 'borrador' THEN 'Borrador' WHEN 'timbrada' THEN 'Vigente' ELSE 'Cancelada' END"


def listar_clientes(conn: Connection, busqueda: str | None) -> list[RowMapping]:
    return list(
        conn.execute(
            text("""
                SELECT c.id_cliente, c.rfc, c.razon_social, c.regimen_fiscal, c.codigo_postal, c.correo,
                       COUNT(f.id_factura) AS facturas
                FROM clientes_fiscales c
                LEFT JOIN facturas_cfdi f ON f.id_cliente = c.id_cliente AND f.estatus <> 'borrador'
                WHERE c.activo = TRUE
                  AND (:busqueda IS NULL OR c.rfc = UPPER(:busqueda) OR c.razon_social LIKE CONCAT('%', :busqueda, '%'))
                GROUP BY c.id_cliente
                ORDER BY c.razon_social
            """),
            {"busqueda": busqueda},
        ).mappings()
    )


def cliente_por_rfc(conn: Connection, rfc: str) -> RowMapping | None:
    return conn.execute(
        text("""
            SELECT id_cliente, rfc, razon_social, regimen_fiscal, codigo_postal, correo, 0 AS facturas
            FROM clientes_fiscales WHERE rfc = :rfc AND activo = TRUE
        """),
        {"rfc": rfc},
    ).mappings().first()


def cliente(conn: Connection, id_cliente: int) -> RowMapping | None:
    return next((c for c in listar_clientes(conn, None) if c["id_cliente"] == id_cliente), None)


def rfc_en_uso(conn: Connection, rfc: str, excepto: int | None) -> bool:
    return conn.execute(
        text("SELECT 1 FROM clientes_fiscales WHERE rfc = :rfc AND id_cliente <> COALESCE(:excepto, 0)"),
        {"rfc": rfc, "excepto": excepto},
    ).first() is not None


def insertar_cliente(conn: Connection, datos: dict) -> int:
    return conn.execute(
        text("""
            INSERT INTO clientes_fiscales (rfc, razon_social, regimen_fiscal, codigo_postal, correo)
            VALUES (:rfc, :razon_social, :regimen_fiscal, :codigo_postal, :correo)
        """),
        datos,
    ).lastrowid


def actualizar_cliente(conn: Connection, id_cliente: int, datos: dict) -> None:
    conn.execute(
        text("""
            UPDATE clientes_fiscales
            SET rfc = :rfc, razon_social = :razon_social, regimen_fiscal = :regimen_fiscal,
                codigo_postal = :codigo_postal, correo = :correo
            WHERE id_cliente = :id
        """),
        {**datos, "id": id_cliente},
    )


# ---------------------------------------------------------------- facturas

def venta_para_factura(conn: Connection, folio_venta: str, bloquear: bool = True) -> RowMapping | None:
    # FOR UPDATE: dos contadores no pueden facturar el mismo ticket a la vez.
    return conn.execute(
        text("""
            SELECT v.id_venta, v.folio, v.subtotal, v.iva, v.total, v.estatus,
                   (SELECT m.nombre FROM metodos_pago m WHERE m.id_metodo = v.id_metodo) AS metodo,
                   EXISTS (SELECT 1 FROM facturas_cfdi f
                           WHERE f.id_venta = v.id_venta AND f.estatus = 'timbrada') AS facturado,
                   (SELECT f.id_factura FROM facturas_cfdi f
                    WHERE f.id_venta = v.id_venta AND f.estatus = 'borrador') AS id_borrador
            FROM ventas_cabecera v WHERE v.folio = :folio
        """ + (" FOR UPDATE" if bloquear else "")),
        {"folio": folio_venta},
    ).mappings().first()


def conceptos_de_venta(conn: Connection, id_venta: int) -> list[RowMapping]:
    # Los productos no guardan clave del SAT: 01010101 es "No existe en el catálogo" (válida en CFDI 4.0).
    return list(
        conn.execute(
            text("""
                SELECT p.nombre, p.unidad_venta, SUM(d.cantidad) AS cantidad, MAX(d.precio_unitario) AS precio_unitario,
                       SUM(d.importe) AS importe, MAX(d.tasa_iva) AS tasa_iva, '01010101' AS clave_sat
                FROM ventas_detalle d JOIN productos p ON p.id_producto = d.id_producto
                WHERE d.id_venta = :venta
                GROUP BY d.id_producto, p.nombre, p.unidad_venta
                ORDER BY MIN(d.id_detalle)
            """),
            {"venta": id_venta},
        ).mappings()
    )


def insertar_borrador(conn: Connection, id_venta: int, id_cliente: int, datos: dict, montos: dict,
                      id_usuario: int) -> tuple[int, str]:
    id_factura = conn.execute(
        text("""
            INSERT INTO facturas_cfdi (id_venta, id_cliente, serie, uso_cfdi, forma_pago, metodo_pago,
                                       subtotal, iva, total, id_usuario)
            VALUES (:venta, :cliente, 'F', :uso, :forma, :metodo, :subtotal, :iva, :total, :usuario)
        """),
        {"venta": id_venta, "cliente": id_cliente, "uso": datos["uso_cfdi"], "forma": datos["forma_pago"],
         "metodo": datos["metodo_pago"], "usuario": id_usuario, **montos},
    ).lastrowid
    folio = f"F-{id_factura:06d}"
    conn.execute(text("UPDATE facturas_cfdi SET folio = :folio WHERE id_factura = :id"), {"folio": folio, "id": id_factura})
    return id_factura, folio


def actualizar_borrador(conn: Connection, id_factura: int, id_cliente: int, datos: dict, id_usuario: int) -> str:
    """Reintento de un borrador que no se pudo timbrar: toma el cliente y los datos nuevos."""
    conn.execute(
        text("""
            UPDATE facturas_cfdi SET id_cliente = :cliente, uso_cfdi = :uso, forma_pago = :forma, metodo_pago = :metodo,
                                     id_usuario = :usuario
            WHERE id_factura = :id AND estatus = 'borrador'
        """),
        {"cliente": id_cliente, "uso": datos["uso_cfdi"], "forma": datos["forma_pago"], "metodo": datos["metodo_pago"],
         "usuario": id_usuario, "id": id_factura},
    )
    return conn.execute(text(f"SELECT {FOLIO} FROM facturas_cfdi f WHERE f.id_factura = :id"), {"id": id_factura}).scalar_one()


def marcar_timbrada(conn: Connection, id_factura: int, uuid: str, fecha: datetime, xml_path: str) -> None:
    conn.execute(
        text("""
            UPDATE facturas_cfdi SET uuid = :uuid, fecha_timbrado = :fecha, xml_path = :xml, estatus = 'timbrada'
            WHERE id_factura = :id
        """),
        {"uuid": uuid, "fecha": fecha, "xml": xml_path, "id": id_factura},
    )


_FACTURAS = f"""
    SELECT f.id_factura, {FOLIO} AS folio, v.folio AS folio_venta, f.uuid, {ESTATUS} AS estatus,
           c.rfc, c.razon_social, c.codigo_postal, c.correo, f.uso_cfdi, f.forma_pago, f.metodo_pago,
           f.subtotal, f.iva, f.total, f.fecha_timbrado, f.fecha_cancelacion, f.motivo_cancelacion,
           f.id_venta, f.xml_path
    FROM facturas_cfdi f
    JOIN ventas_cabecera v ON v.id_venta = f.id_venta
    JOIN clientes_fiscales c ON c.id_cliente = f.id_cliente
"""


def factura(conn: Connection, folio: str, bloquear: bool = False) -> RowMapping | None:
    return conn.execute(
        text(_FACTURAS + f" WHERE {FOLIO} = :folio" + (" FOR UPDATE" if bloquear else "")), {"folio": folio}
    ).mappings().first()


def listar_facturas(conn: Connection, texto: str | None, desde: date | None, hasta: date | None) -> list[RowMapping]:
    return list(
        conn.execute(
            text(_FACTURAS + f"""
                WHERE (:texto IS NULL OR {FOLIO} = UPPER(:texto) OR c.rfc = UPPER(:texto)
                       OR c.razon_social LIKE CONCAT('%', :texto, '%'))
                  AND (:desde IS NULL OR COALESCE(f.fecha_timbrado, f.creado_en) >= :desde)
                  AND (:hasta IS NULL OR COALESCE(f.fecha_timbrado, f.creado_en) < :hasta + INTERVAL 1 DAY)
                ORDER BY f.id_factura DESC
                LIMIT 500
            """),
            {"texto": texto, "desde": desde, "hasta": hasta},
        ).mappings()
    )


def marcar_cancelada(conn: Connection, id_factura: int, motivo: str, uuid_sustituto: str | None, fecha: datetime) -> None:
    conn.execute(
        text("""
            UPDATE facturas_cfdi
            SET estatus = 'cancelada', motivo_cancelacion = :motivo, uuid_sustituto = :sustituto, fecha_cancelacion = :fecha
            WHERE id_factura = :id
        """),
        {"motivo": motivo, "sustituto": uuid_sustituto, "fecha": fecha, "id": id_factura},
    )


def timbres_usados(conn: Connection) -> int:
    return conn.execute(text("SELECT COUNT(*) FROM facturas_cfdi WHERE uuid IS NOT NULL")).scalar_one()
