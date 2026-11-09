"""Inicio de sesión con límite de 5 intentos fallidos."""
from sqlalchemy import Connection

from app.config import get_settings
from app.errores import ErrorNegocio
from app.repositories import auditoria, usuarios
from app.schemas.auth import LoginSalida, Perfil, Permiso
from app.security.passwords import HASH_SENUELO, verificar_password
from app.security.tokens import crear_token

CREDENCIALES_INVALIDAS = "Usuario o contraseña incorrectos."
CUENTA_BLOQUEADA = "Cuenta bloqueada temporalmente por intentos fallidos."


def armar_perfil(conn: Connection, fila) -> Perfil:
    return Perfil(
        id_usuario=fila["id_usuario"],
        usuario=fila["usuario"],
        nombre_completo=fila["nombre_completo"],
        rol=fila["rol"],
        permisos=[Permiso(**p) for p in usuarios.permisos_del_rol(conn, fila["id_rol"])],
    )


def iniciar_sesion(conn: Connection, usuario: str, password: str, ip: str | None) -> LoginSalida:
    fila = usuarios.buscar_para_login(conn, usuario)

    if fila is None:
        verificar_password(password, HASH_SENUELO)
        auditoria.registrar(conn, "auth", "login_fallido", "Usuario inexistente o inactivo", ip, usuario=usuario)
        conn.commit()
        raise ErrorNegocio(401, CREDENCIALES_INVALIDAS)

    if fila["bloqueado"]:
        auditoria.registrar(
            conn, "auth", "login_bloqueado", "Intento con la cuenta bloqueada", ip,
            fila["id_usuario"], fila["usuario"],
        )
        conn.commit()
        raise ErrorNegocio(429, CUENTA_BLOQUEADA)

    if not verificar_password(password, fila["password_hash"]):
        usuarios.registrar_intento_fallido(conn, fila["id_usuario"])
        auditoria.registrar(
            conn, "auth", "login_fallido", "Contraseña incorrecta", ip, fila["id_usuario"], fila["usuario"]
        )
        conn.commit()
        raise ErrorNegocio(401, CREDENCIALES_INVALIDAS)

    usuarios.registrar_acceso(conn, fila["id_usuario"])
    auditoria.registrar(conn, "auth", "login", None, ip, fila["id_usuario"], fila["usuario"])
    perfil = armar_perfil(conn, fila)
    conn.commit()
    return LoginSalida(
        access_token=crear_token(fila["id_usuario"]),
        expira_minutos=get_settings().session_minutes,
        perfil=perfil,
    )
