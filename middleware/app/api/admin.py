from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request, status
from sqlalchemy import Connection

from app.api.auth import ip_de
from app.db import get_conn
from app.repositories import admin as repositorio
from app.schemas.admin import Rol, Usuario, UsuarioEntrada
from app.security.dependencias import UsuarioActual, requiere
from app.security.sanitizar import PATRON_TEXTO_SEGURO
from app.services import admin as servicio

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/roles", response_model=list[Rol], dependencies=[Depends(requiere("admin", "ver"))])
def roles(conn: Connection = Depends(get_conn)):
    return repositorio.listar_roles(conn)


# ---------------------------------------------------------------- usuarios (HU-18)

@router.get("/usuarios", response_model=list[Usuario], dependencies=[Depends(requiere("admin", "ver"))])
def usuarios(
    busqueda: Annotated[str | None, Query(max_length=150, pattern=PATRON_TEXTO_SEGURO)] = None,
    id_rol: Annotated[int | None, Query(gt=0)] = None,
    conn: Connection = Depends(get_conn),
):
    return repositorio.listar_usuarios(conn, busqueda, id_rol)


@router.post("/usuarios", response_model=Usuario, status_code=status.HTTP_201_CREATED)
def alta_usuario(
    datos: UsuarioEntrada,
    request: Request,
    actual: UsuarioActual = Depends(requiere("admin", "crear")),
    conn: Connection = Depends(get_conn),
):
    return servicio.guardar_usuario(conn, datos, actual, ip_de(request))


@router.put("/usuarios/{id_usuario}", response_model=Usuario)
def editar_usuario(
    id_usuario: Annotated[int, Path(gt=0)],
    datos: UsuarioEntrada,
    request: Request,
    actual: UsuarioActual = Depends(requiere("admin", "editar")),
    conn: Connection = Depends(get_conn),
):
    return servicio.guardar_usuario(conn, datos, actual, ip_de(request), id_usuario)
