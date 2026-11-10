from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import Connection

from app.db import get_conn
from app.repositories import auditoria, usuarios
from app.schemas.auth import LoginEntrada, LoginSalida, Perfil
from app.security.dependencias import UsuarioActual, usuario_actual
from app.services import auth as servicio

router = APIRouter(prefix="/auth", tags=["auth"])


def ip_de(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.post("/login", response_model=LoginSalida)
def login(datos: LoginEntrada, request: Request, conn: Connection = Depends(get_conn)):
    return servicio.iniciar_sesion(conn, datos.usuario, datos.password, ip_de(request))


@router.get("/me", response_model=Perfil)
def me(usuario: UsuarioActual = Depends(usuario_actual), conn: Connection = Depends(get_conn)):
    return servicio.armar_perfil(conn, usuarios.buscar_activo(conn, usuario.id_usuario))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    usuario: UsuarioActual = Depends(usuario_actual),
    conn: Connection = Depends(get_conn),
):
    usuarios.cerrar_sesiones(conn, usuario.id_usuario)
    auditoria.registrar(conn, "auth", "logout", None, ip_de(request), usuario.id_usuario, usuario.usuario)
    conn.commit()
