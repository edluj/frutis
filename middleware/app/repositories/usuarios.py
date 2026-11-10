"""Consultas de usuarios, roles y permisos."""
from sqlalchemy import Connection, RowMapping, text

MAX_INTENTOS = 5
MINUTOS_BLOQUEO = 5

_COLUMNAS = """
    u.id_usuario, u.usuario, u.nombre_completo, u.password_hash, u.id_rol,
    r.nombre AS rol, u.sesion_version, u.activo AND r.activo AS activo,
    COALESCE(u.bloqueado_hasta > NOW(), FALSE) AS bloqueado
"""


def buscar_para_login(conn: Connection, usuario: str) -> RowMapping | None:
    return conn.execute(
        text(f"""
            SELECT {_COLUMNAS}
            FROM usuarios u JOIN roles r ON r.id_rol = u.id_rol
            WHERE u.usuario = :usuario
        """),
        {"usuario": usuario},
    ).mappings().first()


def buscar_activo(conn: Connection, id_usuario: int) -> RowMapping | None:
    return conn.execute(
        text(f"""
            SELECT {_COLUMNAS}
            FROM usuarios u JOIN roles r ON r.id_rol = u.id_rol
            WHERE u.id_usuario = :id AND u.activo = TRUE AND r.activo = TRUE
        """),
        {"id": id_usuario},
    ).mappings().first()


def registrar_intento_fallido(conn: Connection, id_usuario: int) -> None:
    # MySQL evalúa SET de izquierda a derecha: el segundo IF ya ve el contador nuevo.
    conn.execute(
        text("""
            UPDATE usuarios
            SET intentos_fallidos = IF(bloqueado_hasta IS NOT NULL AND bloqueado_hasta <= NOW(),
                                       1, intentos_fallidos + 1),
                bloqueado_hasta = IF(intentos_fallidos >= :maximo,
                                     NOW() + INTERVAL :minutos MINUTE, NULL)
            WHERE id_usuario = :id
        """),
        {"id": id_usuario, "maximo": MAX_INTENTOS, "minutos": MINUTOS_BLOQUEO},
    )


def registrar_acceso(conn: Connection, id_usuario: int) -> None:
    conn.execute(
        text("""
            UPDATE usuarios
            SET intentos_fallidos = 0, bloqueado_hasta = NULL, ultimo_acceso = NOW()
            WHERE id_usuario = :id
        """),
        {"id": id_usuario},
    )


def cerrar_sesiones(conn: Connection, id_usuario: int) -> None:
    """Invalida todos los tokens emitidos al usuario, en cualquier terminal (SC-04)."""
    conn.execute(
        text("UPDATE usuarios SET sesion_version = sesion_version + 1 WHERE id_usuario = :id"),
        {"id": id_usuario},
    )


def permisos_del_rol(conn: Connection, id_rol: int) -> list[RowMapping]:
    return list(
        conn.execute(
            text("""
                SELECT modulo, puede_ver, puede_crear, puede_editar, puede_eliminar
                FROM permisos WHERE id_rol = :rol ORDER BY modulo
            """),
            {"rol": id_rol},
        ).mappings()
    )
