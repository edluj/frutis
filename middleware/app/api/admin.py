from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request, status
from sqlalchemy import Connection

from app.api.auth import ip_de
from app.db import get_conn
from app.repositories import usuarios as repo_usuarios
from app.repositories import admin as repositorio
from app.schemas.admin import (
    ActivacionEntrada, MetodoPagoConfig, PermisoModulo, PermisosEntrada, RegistroAuditoria, Rol, RolEntrada, Terminal,
    Usuario, UsuarioEntrada,
)
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


# ---------------------------------------------------------------- roles y permisos (HU-34)

IdRol = Annotated[int, Path(gt=0)]


@router.post("/roles", response_model=Rol, status_code=status.HTTP_201_CREATED)
def crear_rol(
    datos: RolEntrada, request: Request,
    actual: UsuarioActual = Depends(requiere("admin", "crear")), conn: Connection = Depends(get_conn),
):
    return servicio.crear_rol(conn, datos, actual, ip_de(request))


@router.get("/roles/{id_rol}/permisos", response_model=list[PermisoModulo],
            dependencies=[Depends(requiere("admin", "ver"))])
def permisos(id_rol: IdRol, conn: Connection = Depends(get_conn)):
    return repo_usuarios.permisos_del_rol(conn, id_rol)


@router.put("/roles/{id_rol}/permisos", status_code=status.HTTP_204_NO_CONTENT)
def guardar_permisos(
    id_rol: IdRol, datos: PermisosEntrada, request: Request,
    actual: UsuarioActual = Depends(requiere("admin", "editar")), conn: Connection = Depends(get_conn),
):
    servicio.guardar_permisos(conn, id_rol, datos, actual, ip_de(request))


# ---------------------------------------------------------------- auditoría (HU-35)

@router.get("/auditoria", response_model=list[RegistroAuditoria], dependencies=[Depends(requiere("admin", "ver"))])
def auditoria(
    usuario: Annotated[str | None, Query(max_length=50, pattern=r"^[\w.\-]+$")] = None,
    modulo: Annotated[str | None, Query(max_length=30, pattern=r"^[a-z_]+$")] = None,
    accion: Annotated[str | None, Query(max_length=40, pattern=r"^[a-z_]+$")] = None,
    desde: date | None = None,
    hasta: date | None = None,
    conn: Connection = Depends(get_conn),
):
    """Solo lectura: la tabla rechaza UPDATE y DELETE con triggers."""
    return repositorio.auditoria(conn, usuario, modulo, accion, desde, hasta)


# ---------------------------------------------------------------- cajas y métodos de pago (HU-41)

@router.get("/cajas", response_model=list[Terminal], dependencies=[Depends(requiere("admin", "ver"))])
def cajas(conn: Connection = Depends(get_conn)):
    return repositorio.terminales(conn)


@router.get("/metodos-pago", response_model=list[MetodoPagoConfig], dependencies=[Depends(requiere("admin", "ver"))])
def metodos_pago(conn: Connection = Depends(get_conn)):
    return repositorio.metodos_pago(conn)


@router.put("/metodos-pago/{id_metodo}", status_code=status.HTTP_204_NO_CONTENT)
def activar_metodo(
    id_metodo: Annotated[int, Path(gt=0)], datos: ActivacionEntrada, request: Request,
    actual: UsuarioActual = Depends(requiere("admin", "editar")), conn: Connection = Depends(get_conn),
):
    servicio.activar_metodo(conn, id_metodo, datos.activo, actual, ip_de(request))
