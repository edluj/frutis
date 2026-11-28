"""Reglas de Administración: usuarios (HU-18), roles y permisos (HU-34) y métodos de pago (HU-41)."""
from sqlalchemy import Connection
from sqlalchemy.exc import IntegrityError

from app.errores import ErrorNegocio
from app.repositories import admin as repositorio
from app.repositories import auditoria, usuarios
from app.schemas.admin import MODULOS, PermisosEntrada, Rol, RolEntrada, Usuario, UsuarioEntrada
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


# ---------------------------------------------------------------- roles y permisos (HU-34)

def _rol_editable(conn: Connection, id_rol: int):
    rol = repositorio.rol(conn, id_rol)
    if rol is None or not rol["activo"]:
        raise ErrorNegocio(404, "Rol no encontrado.")
    if rol["es_sistema"]:
        raise ErrorNegocio(409, "El rol Administrador no se edita.")
    return rol


def guardar_permisos(conn: Connection, id_rol: int, datos: PermisosEntrada, actual: UsuarioActual, ip: str | None) -> None:
    rol = _rol_editable(conn, id_rol)
    recibidos = {p.modulo: p for p in datos.permisos}
    if len(recibidos) != len(datos.permisos):
        raise ErrorNegocio(409, "Un módulo aparece dos veces.")
    for modulo in MODULOS:
        p = recibidos.get(modulo)
        repositorio.guardar_permiso(conn, id_rol, p.model_dump() if p else
                                    {"modulo": modulo, "puede_ver": False, "puede_crear": False,
                                     "puede_editar": False, "puede_eliminar": False})
    resumen = ", ".join(f"{p.modulo} " + "".join(l for l, v in zip("VCEB", (p.puede_ver, p.puede_crear, p.puede_editar,
                                                                           p.puede_eliminar)) if v)
                        for p in datos.permisos if any((p.puede_ver, p.puede_crear, p.puede_editar, p.puede_eliminar)))
    auditoria.registrar(conn, "admin", "permisos_edicion", f"Rol {rol['nombre']}: {resumen or 'sin permisos'}",
                        ip, actual.id_usuario, actual.usuario)
    conn.commit()


def crear_rol(conn: Connection, datos: RolEntrada, actual: UsuarioActual, ip: str | None) -> Rol:
    if repositorio.nombre_rol_en_uso(conn, datos.nombre):
        raise ErrorNegocio(409, "Ya existe un rol con ese nombre.", "nombre")
    try:
        id_rol = repositorio.insertar_rol(conn, datos.nombre)
    except IntegrityError as exc:
        conn.rollback()
        raise ErrorNegocio(409, "Ya existe un rol con ese nombre.", "nombre") from exc
    auditoria.registrar(conn, "admin", "rol_alta", datos.nombre, ip, actual.id_usuario, actual.usuario)
    conn.commit()
    return Rol(id_rol=id_rol, nombre=datos.nombre)


# ---------------------------------------------------------------- métodos de pago (HU-41)

def activar_metodo(conn: Connection, id_metodo: int, activo: bool, actual: UsuarioActual, ip: str | None) -> None:
    metodo = repositorio.metodo(conn, id_metodo)
    if metodo is None:
        raise ErrorNegocio(404, "Método de pago no encontrado.")
    if metodo["es_efectivo"] and not activo:
        raise ErrorNegocio(409, "El efectivo no se puede desactivar.")
    repositorio.activar_metodo(conn, id_metodo, activo)
    auditoria.registrar(conn, "admin", "metodo_activado" if activo else "metodo_desactivado", metodo["nombre"],
                        ip, actual.id_usuario, actual.usuario)
    conn.commit()
