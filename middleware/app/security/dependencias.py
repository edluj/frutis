"""Autenticación y autorización de cada petición."""
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from fastapi import Depends, HTTPException, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import Connection

from app.db import get_conn
from app.repositories import usuarios
from app.security.tokens import crear_token, leer_token

CABECERA_RENOVADO = "X-Token-Renovado"

_bearer = HTTPBearer(auto_error=False)
Accion = Literal["ver", "crear", "editar", "eliminar"]


@dataclass(frozen=True)
class UsuarioActual:
    id_usuario: int
    usuario: str
    nombre_completo: str
    id_rol: int
    rol: str


def usuario_actual(
    response: Response,
    credenciales: HTTPAuthorizationCredentials | None = Depends(_bearer),
    conn: Connection = Depends(get_conn),
) -> UsuarioActual:
    id_usuario = leer_token(credenciales.credentials) if credenciales else None
    fila = usuarios.buscar_activo(conn, id_usuario) if id_usuario is not None else None
    if fila is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Sesión inválida o expirada.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # Cada petición válida renueva la sesión: expira por inactividad.
    response.headers[CABECERA_RENOVADO] = crear_token(id_usuario)
    return UsuarioActual(
        id_usuario=fila["id_usuario"],
        usuario=fila["usuario"],
        nombre_completo=fila["nombre_completo"],
        id_rol=fila["id_rol"],
        rol=fila["rol"],
    )


def requiere(modulo: str, accion: Accion) -> Callable[..., UsuarioActual]:
    """Compara el rol con la matriz de permisos vigente en la tabla `permisos`."""

    def verificar(
        usuario: UsuarioActual = Depends(usuario_actual),
        conn: Connection = Depends(get_conn),
    ) -> UsuarioActual:
        permiso = next(
            (p for p in usuarios.permisos_del_rol(conn, usuario.id_rol) if p["modulo"] == modulo),
            None,
        )
        if permiso is None or not permiso[f"puede_{accion}"]:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "No tiene permiso para esta acción.")
        return usuario

    return verificar
