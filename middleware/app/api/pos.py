from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import Connection

from app.api.auth import ip_de
from app.db import get_conn
from app.errores import ErrorNegocio
from app.repositories import pos as repositorio
from app.schemas.pos import Caja, MetodoPago, Producto, VentaEntrada, VentaSalida
from app.security.dependencias import UsuarioActual, requiere
from app.services import pos as servicio

router = APIRouter(prefix="/pos", tags=["pos"])


@router.get("/productos", response_model=list[Producto], dependencies=[Depends(requiere("pos", "ver"))])
def productos(
    codigo: Annotated[str | None, Query(max_length=32)] = None,
    busqueda: Annotated[str | None, Query(max_length=120)] = None,
    frecuentes: bool = False,
    conn: Connection = Depends(get_conn),
):
    return repositorio.buscar_productos(conn, codigo, busqueda, frecuentes)


@router.get("/metodos-pago", response_model=list[MetodoPago], dependencies=[Depends(requiere("pos", "ver"))])
def metodos_pago(conn: Connection = Depends(get_conn)):
    return repositorio.metodos_pago(conn)


@router.get("/cajas/actual", response_model=Caja)
def caja_actual(
    usuario: UsuarioActual = Depends(requiere("pos", "ver")),
    conn: Connection = Depends(get_conn),
):
    caja = repositorio.caja_abierta_de(conn, usuario.id_usuario)
    if caja is None:
        raise ErrorNegocio(404, "No hay una caja abierta.")
    return caja


@router.post("/ventas", response_model=VentaSalida, status_code=status.HTTP_201_CREATED)
def registrar_venta(
    venta: VentaEntrada,
    request: Request,
    usuario: UsuarioActual = Depends(requiere("pos", "crear")),
    conn: Connection = Depends(get_conn),
):
    return servicio.registrar_venta(conn, venta, usuario, ip_de(request))
