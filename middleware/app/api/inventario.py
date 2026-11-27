from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Path, Query, Request, status
from sqlalchemy import Connection

from app.api.auth import ip_de
from app.db import get_conn
from app.repositories import inventario as repositorio
from app.schemas.inventario import Categoria, CategoriaEntrada, ProductoCatalogo, ProductoEntrada
from app.security.dependencias import UsuarioActual, requiere
from app.security.sanitizar import PATRON_TEXTO_SEGURO
from app.services import inventario as servicio

router = APIRouter(prefix="/inventario", tags=["inventario"])

Busqueda = Annotated[str | None, Query(max_length=120, pattern=PATRON_TEXTO_SEGURO)]
Id = Annotated[int, Path(gt=0)]

# Filtro "Existencia" de la pantalla de productos (CAT-02).
FILTRO_ESTADOS = {"bajo": {"Bajo", "Sin existencia"}, "por_caducar": {"Por caducar"}}


# ---------------------------------------------------------------- categorías (HU-22)

@router.get("/categorias", response_model=list[Categoria], dependencies=[Depends(requiere("inventario", "ver"))])
def categorias(busqueda: Busqueda = None, activas: bool = False, conn: Connection = Depends(get_conn)):
    return repositorio.listar_categorias(conn, busqueda, activas)


@router.post("/categorias", response_model=Categoria, status_code=status.HTTP_201_CREATED)
def alta_categoria(
    datos: CategoriaEntrada,
    request: Request,
    usuario: UsuarioActual = Depends(requiere("inventario", "crear")),
    conn: Connection = Depends(get_conn),
):
    return servicio.guardar_categoria(conn, datos, usuario, ip_de(request))


@router.put("/categorias/{id_categoria}", response_model=Categoria)
def editar_categoria(
    id_categoria: Id,
    datos: CategoriaEntrada,
    request: Request,
    usuario: UsuarioActual = Depends(requiere("inventario", "editar")),
    conn: Connection = Depends(get_conn),
):
    return servicio.guardar_categoria(conn, datos, usuario, ip_de(request), id_categoria)


# ---------------------------------------------------------------- productos (HU-10)

@router.get("/productos", response_model=list[ProductoCatalogo], dependencies=[Depends(requiere("inventario", "ver"))])
def productos(
    busqueda: Busqueda = None,
    id_categoria: Annotated[int | None, Query(gt=0)] = None,
    existencia: Literal["todas", "bajo", "por_caducar"] = "todas",
    conn: Connection = Depends(get_conn),
):
    filas = repositorio.listar_productos(conn, busqueda, id_categoria)
    if existencia == "todas":
        return filas
    return [f for f in filas if f["activo"] and f["estado"] in FILTRO_ESTADOS[existencia]]


@router.post("/productos", response_model=ProductoCatalogo, status_code=status.HTTP_201_CREATED)
def alta_producto(
    datos: ProductoEntrada,
    request: Request,
    usuario: UsuarioActual = Depends(requiere("inventario", "crear")),
    conn: Connection = Depends(get_conn),
):
    return servicio.guardar_producto(conn, datos, usuario, ip_de(request))


@router.put("/productos/{id_producto}", response_model=ProductoCatalogo)
def editar_producto(
    id_producto: Id,
    datos: ProductoEntrada,
    request: Request,
    usuario: UsuarioActual = Depends(requiere("inventario", "editar")),
    conn: Connection = Depends(get_conn),
):
    return servicio.guardar_producto(conn, datos, usuario, ip_de(request), id_producto)
