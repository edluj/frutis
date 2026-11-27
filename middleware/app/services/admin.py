"""Reglas de la administración de usuarios (HU-18)."""
from sqlalchemy import Connection
from sqlalchemy.exc import IntegrityError

from app.errores import ErrorNegocio
from app.repositories import admin as repositorio
from app.repositories import auditoria, usuarios
from app.schemas.admin import Usuario, UsuarioEntrada
from app.security.dependencias import UsuarioActual
from app.security.passwords import hash_password

ER_DUP_ENTRY = 1062
MIN_PASSWORD = 8
ROL_ADMINISTRADOR = "Administrador"
USUARIO_REPETIDO = "El usuario ya existe."


def guardar_usuario(
    conn: Connection, datos: UsuarioEntrada, actual: UsuarioActual, ip: str | None, id_usuario: int | None = None
) -> Usuario:
    anterior = None
    if id_usuario is not None:
        anterior = repositorio.usuario(conn, id_usuario, bloquear=True)
        if anterior is None:
            raise ErrorNegocio(404, "Usuario no encontrado.")
    if datos.password is not None and datos.password != "" and len(datos.password) < MIN_PASSWORD:
        raise ErrorNegocio(422, f"Usa al menos {MIN_PASSWORD} caracteres.", "password")
    if anterior is None and not datos.password:
        raise ErrorNegocio(422, "La contraseña temporal es obligatoria.", "password")

    rol = repositorio.rol(conn, datos.id_rol)
    if rol is None or not rol["activo"]:
        raise ErrorNegocio(409, "Elija un rol activo.", "rol")
    if id_usuario == actual.id_usuario:
        # Quien administra no puede dejarse fuera del sistema.
        if not datos.activo:
            raise ErrorNegocio(409, "No puede darse de baja a sí mismo.", "estatus")
        if anterior["rol"] == ROL_ADMINISTRADOR and rol["nombre"] != ROL_ADMINISTRADOR:
            raise ErrorNegocio(409, "No puede quitarse a sí mismo el rol de Administrador.", "rol")
    if repositorio.en_uso(conn, "usuario", datos.usuario, id_usuario):
        raise ErrorNegocio(409, USUARIO_REPETIDO, "usuario")
    if repositorio.en_uso(conn, "correo", datos.correo, id_usuario):
        raise ErrorNegocio(409, "El correo ya está registrado.", "correo")

    valores = datos.model_dump(exclude={"password"})
    try:
        if anterior is None:
            id_usuario = repositorio.insertar_usuario(conn, valores, hash_password(datos.password))
            accion, detalle = "usuario_alta", f"{datos.usuario} · rol {rol['nombre']}"
        else:
            repositorio.actualizar_usuario(conn, id_usuario, valores)
            cambios = []
            if datos.password:
                repositorio.cambiar_password(conn, id_usuario, hash_password(datos.password))
                cambios.append("contraseña cambiada")
            if anterior["rol"] != rol["nombre"]:
                cambios.append(f"rol {anterior['rol']} -> {rol['nombre']}")
            if anterior["activo"] and not datos.activo:
                cambios.append("desactivado")
            # Contraseña nueva o baja: las sesiones abiertas de ese usuario dejan de servir (SC-04).
            if datos.password or (anterior["activo"] and not datos.activo):
                usuarios.cerrar_sesiones(conn, id_usuario)
            accion = "usuario_baja" if "desactivado" in cambios else "usuario_edicion"
            detalle = f"{datos.usuario} · " + (", ".join(cambios) or f"rol {rol['nombre']}")
    except IntegrityError as exc:
        conn.rollback()
        if exc.orig is not None and exc.orig.args and exc.orig.args[0] == ER_DUP_ENTRY:
            raise ErrorNegocio(409, USUARIO_REPETIDO, "usuario") from exc
        raise
    auditoria.registrar(conn, "admin", accion, detalle, ip, actual.id_usuario, actual.usuario)
    salida = Usuario(**repositorio.usuario(conn, id_usuario))
    conn.commit()
    return salida
