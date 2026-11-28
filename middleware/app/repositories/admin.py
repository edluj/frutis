"""Consultas de usuarios y roles (flujos T y U)."""
from sqlalchemy import Connection, RowMapping, text

_USUARIOS = """
    SELECT u.id_usuario, u.nombre_completo, u.usuario, u.correo, u.id_rol, r.nombre AS rol,
           u.ultimo_acceso, u.activo
    FROM usuarios u JOIN roles r ON r.id_rol = u.id_rol
"""


def listar_usuarios(conn: Connection, busqueda: str | None, id_rol: int | None) -> list[RowMapping]:
    return list(
        conn.execute(
            text(_USUARIOS + """
                WHERE (:busqueda IS NULL OR u.nombre_completo LIKE CONCAT('%', :busqueda, '%')
                       OR u.usuario LIKE CONCAT('%', :busqueda, '%'))
                  AND (:rol IS NULL OR u.id_rol = :rol)
                ORDER BY u.activo DESC, u.nombre_completo
            """),
            {"busqueda": busqueda, "rol": id_rol},
        ).mappings()
    )


def usuario(conn: Connection, id_usuario: int, bloquear: bool = False) -> RowMapping | None:
    return conn.execute(
        text(_USUARIOS + " WHERE u.id_usuario = :id" + (" FOR UPDATE" if bloquear else "")),
        {"id": id_usuario},
    ).mappings().first()


def en_uso(conn: Connection, columna: str, valor: str, excepto: int | None) -> bool:
    if columna not in ("usuario", "correo"):
        raise ValueError(columna)
    return conn.execute(
        text(f"SELECT 1 FROM usuarios WHERE {columna} = :valor AND id_usuario <> COALESCE(:excepto, 0)"),
        {"valor": valor, "excepto": excepto},
    ).first() is not None


def listar_roles(conn: Connection) -> list[RowMapping]:
    return list(
        conn.execute(
            text("""
                SELECT r.id_rol, r.nombre, r.es_sistema, COUNT(u.id_usuario) AS usuarios
                FROM roles r LEFT JOIN usuarios u ON u.id_rol = r.id_rol AND u.activo = TRUE
                WHERE r.activo = TRUE
                GROUP BY r.id_rol, r.nombre, r.es_sistema
                ORDER BY r.id_rol
            """)
        ).mappings()
    )


def rol(conn: Connection, id_rol: int) -> RowMapping | None:
    return conn.execute(
        text("SELECT id_rol, nombre, activo, es_sistema FROM roles WHERE id_rol = :id"), {"id": id_rol}
    ).mappings().first()


def insertar_usuario(conn: Connection, datos: dict, password_hash: str) -> int:
    return conn.execute(
        text("""
            INSERT INTO usuarios (nombre_completo, usuario, correo, password_hash, id_rol, activo)
            VALUES (:nombre_completo, :usuario, :correo, :hash, :id_rol, :activo)
        """),
        {**datos, "hash": password_hash},
    ).lastrowid


def actualizar_usuario(conn: Connection, id_usuario: int, datos: dict) -> None:
    conn.execute(
        text("""
            UPDATE usuarios
            SET nombre_completo = :nombre_completo, usuario = :usuario, correo = :correo,
                id_rol = :id_rol, activo = :activo
            WHERE id_usuario = :id
        """),
        {**datos, "id": id_usuario},
    )


def cambiar_password(conn: Connection, id_usuario: int, password_hash: str) -> None:
    # La contraseña nueva desbloquea la cuenta.
    conn.execute(
        text("""
            UPDATE usuarios SET password_hash = :hash, intentos_fallidos = 0, bloqueado_hasta = NULL
            WHERE id_usuario = :id
        """),
        {"hash": password_hash, "id": id_usuario},
    )


# ---------------------------------------------------------------- roles y permisos (HU-34)

def nombre_rol_en_uso(conn: Connection, nombre: str) -> bool:
    return conn.execute(text("SELECT 1 FROM roles WHERE nombre = :nombre"), {"nombre": nombre}).first() is not None


def insertar_rol(conn: Connection, nombre: str) -> int:
    return conn.execute(text("INSERT INTO roles (nombre) VALUES (:nombre)"), {"nombre": nombre}).lastrowid


def guardar_permiso(conn: Connection, id_rol: int, p: dict) -> None:
    # Sin DELETE: un módulo que se quita queda con los cuatro permisos en falso.
    conn.execute(
        text("""
            INSERT INTO permisos (id_rol, modulo, puede_ver, puede_crear, puede_editar, puede_eliminar)
            VALUES (:rol, :modulo, :ver, :crear, :editar, :eliminar)
            ON DUPLICATE KEY UPDATE puede_ver = VALUES(puede_ver), puede_crear = VALUES(puede_crear),
                                    puede_editar = VALUES(puede_editar), puede_eliminar = VALUES(puede_eliminar)
        """),
        {"rol": id_rol, "modulo": p["modulo"], "ver": p["puede_ver"], "crear": p["puede_crear"],
         "editar": p["puede_editar"], "eliminar": p["puede_eliminar"]},
    )


# ---------------------------------------------------------------- auditoría (HU-35)

def auditoria(conn: Connection, usuario, modulo, accion, desde, hasta) -> list[RowMapping]:
    return list(
        conn.execute(
            text("""
                SELECT fecha, usuario, modulo, accion, detalle, ip FROM auditoria
                WHERE (:usuario IS NULL OR usuario = :usuario) AND (:modulo IS NULL OR modulo = :modulo)
                  AND (:accion IS NULL OR accion = :accion)
                  AND (:desde IS NULL OR fecha >= :desde) AND (:hasta IS NULL OR fecha < :hasta + INTERVAL 1 DAY)
                ORDER BY fecha DESC, id_auditoria DESC
                LIMIT 2000
            """),
            {"usuario": usuario, "modulo": modulo, "accion": accion, "desde": desde, "hasta": hasta},
        ).mappings()
    )


# ---------------------------------------------------------------- cajas y métodos de pago (HU-41)

def terminales(conn: Connection) -> list[RowMapping]:
    """Una terminal existe desde que se abre caja con su nombre (FRUTIS_TERMINAL)."""
    return list(
        conn.execute(
            text("""
                SELECT c.terminal, MAX(c.estatus = 'abierta') AS abierta,
                       MAX(IF(c.estatus = 'abierta', u.nombre_completo, NULL)) AS cajero,
                       MAX(c.fecha_apertura) AS ultima_apertura
                FROM cajas_pos c JOIN usuarios u ON u.id_usuario = c.id_usuario
                GROUP BY c.terminal ORDER BY c.terminal
            """)
        ).mappings()
    )


def metodos_pago(conn: Connection) -> list[RowMapping]:
    return list(conn.execute(text("""
        SELECT id_metodo, nombre, clave_sat, es_efectivo, es_credito, activo FROM metodos_pago ORDER BY id_metodo
    """)).mappings())


def metodo(conn: Connection, id_metodo: int) -> RowMapping | None:
    return next((m for m in metodos_pago(conn) if m["id_metodo"] == id_metodo), None)


def activar_metodo(conn: Connection, id_metodo: int, activo: bool) -> None:
    conn.execute(text("UPDATE metodos_pago SET activo = :activo WHERE id_metodo = :id"), {"activo": activo, "id": id_metodo})
