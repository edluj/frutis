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
    return list(conn.execute(text("SELECT id_rol, nombre FROM roles WHERE activo = TRUE ORDER BY id_rol")).mappings())


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
