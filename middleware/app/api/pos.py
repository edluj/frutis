from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request, status
from sqlalchemy import Connection

from app.api.auth import ip_de
from app.db import get_conn
from app.errores import ErrorNegocio
from app.repositories import pos as repositorio
from app.repositories import usuarios
from app.schemas.pos import (
    PATRON_FOLIO_VENTA, PATRON_TERMINAL, Administrador, AperturaEntrada, AutorizacionEntrada, AutorizacionSalida,
    Caja, CorteEntrada, CorteSalida, DevolucionEntrada, DevolucionSalida, MetodoPago, Producto, ResumenCorte,
    Ticket, UltimoCorte, VentaEntrada, VentaSalida,
)
from app.security.dependencias import UsuarioActual, requiere
from app.security.sanitizar import PATRON_TEXTO_SEGURO
from app.services import pos as servicio

router = APIRouter(prefix="/pos", tags=["pos"])


@router.get("/productos", response_model=list[Producto], dependencies=[Depends(requiere("pos", "ver"))])
def productos(
    codigo: Annotated[str | None, Query(max_length=32, pattern=PATRON_TEXTO_SEGURO)] = None,
    busqueda: Annotated[str | None, Query(max_length=120, pattern=PATRON_TEXTO_SEGURO)] = None,
    frecuentes: bool = False,
    conn: Connection = Depends(get_conn),
):
    return repositorio.buscar_productos(conn, codigo, busqueda, frecuentes)


@router.get("/metodos-pago", response_model=list[MetodoPago], dependencies=[Depends(requiere("pos", "ver"))])
def metodos_pago(conn: Connection = Depends(get_conn)):
    return repositorio.metodos_pago(conn)


# ---------------------------------------------------------------- caja (HU-15)

@router.get("/cajas/actual", response_model=Caja)
def caja_actual(
    usuario: UsuarioActual = Depends(requiere("pos", "ver")),
    conn: Connection = Depends(get_conn),
):
    caja = repositorio.caja_abierta_de(conn, usuario.id_usuario)
    if caja is None:
        raise ErrorNegocio(404, servicio.SIN_CAJA)
    return caja


@router.post("/cajas", response_model=Caja, status_code=status.HTTP_201_CREATED)
def abrir_caja(
    datos: AperturaEntrada,
    request: Request,
    usuario: UsuarioActual = Depends(requiere("pos", "crear")),
    conn: Connection = Depends(get_conn),
):
    return servicio.abrir_caja(conn, datos, usuario, ip_de(request))


# ---------------------------------------------------------------- cobro (HU-06, HU-08)

@router.post("/ventas", response_model=VentaSalida, status_code=status.HTTP_201_CREATED)
def registrar_venta(
    venta: VentaEntrada,
    request: Request,
    usuario: UsuarioActual = Depends(requiere("pos", "crear")),
    conn: Connection = Depends(get_conn),
):
    return servicio.registrar_venta(conn, venta, usuario, ip_de(request))


@router.get("/ventas/{folio}", response_model=Ticket, dependencies=[Depends(requiere("pos", "ver"))])
def ticket(
    folio: Annotated[str, Path(pattern=PATRON_FOLIO_VENTA)],
    conn: Connection = Depends(get_conn),
):
    return servicio.ticket(conn, folio)


# ---------------------------------------------------------------- corte (HU-09)

@router.get("/cortes/actual", response_model=ResumenCorte)
def resumen_corte(
    usuario: UsuarioActual = Depends(requiere("pos", "ver")),
    conn: Connection = Depends(get_conn),
):
    return servicio.resumen_corte(conn, usuario)


@router.get("/cortes/ultimo", response_model=UltimoCorte, dependencies=[Depends(requiere("pos", "ver"))])
def ultimo_corte(
    terminal: Annotated[str, Query(min_length=1, max_length=30, pattern=PATRON_TERMINAL)],
    conn: Connection = Depends(get_conn),
):
    corte = repositorio.ultimo_corte(conn, terminal)
    if corte is None:
        raise ErrorNegocio(404, "Esta terminal todavía no tiene cortes.")
    return corte


@router.post("/cortes", response_model=CorteSalida, status_code=status.HTTP_201_CREATED)
def cerrar_caja(
    datos: CorteEntrada,
    request: Request,
    usuario: UsuarioActual = Depends(requiere("pos", "crear")),
    conn: Connection = Depends(get_conn),
):
    return servicio.cerrar_caja(conn, datos, usuario, ip_de(request))


# ---------------------------------------------------------------- devoluciones (HU-30, SC-02)

@router.get(
    "/devoluciones/administradores",
    response_model=list[Administrador],
    dependencies=[Depends(requiere("pos", "crear"))],
)
def administradores(conn: Connection = Depends(get_conn)):
    return usuarios.administradores(conn)


@router.post("/devoluciones/autorizacion", response_model=AutorizacionSalida)
def autorizar_devolucion(
    datos: AutorizacionEntrada,
    request: Request,
    usuario: UsuarioActual = Depends(requiere("pos", "crear")),
    conn: Connection = Depends(get_conn),
):
    return servicio.autorizar_devolucion(conn, datos, usuario, ip_de(request))


@router.post("/devoluciones", response_model=DevolucionSalida, status_code=status.HTTP_201_CREATED)
def registrar_devolucion(
    datos: DevolucionEntrada,
    request: Request,
    usuario: UsuarioActual = Depends(requiere("pos", "crear")),
    conn: Connection = Depends(get_conn),
):
    return servicio.registrar_devolucion(conn, datos, usuario, ip_de(request))
